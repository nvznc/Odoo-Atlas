"""Cliente para obtener la tasa oficial USD/VES desde el BCV."""

import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import TypedDict

from lxml import etree
from lxml import html as lxml_html

_logger = logging.getLogger(__name__)

BCV_URL = "https://www.bcv.org.ve/"
BCV_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
HTTP_TIMEOUT = 25
_CERT_DIR = os.path.join(os.path.dirname(__file__), "certs")
_ROOT_CERT = os.path.join(_CERT_DIR, "SectigoPublicServerAuthenticationRootR46.pem")
_INTERMEDIATE_CERT = os.path.join(_CERT_DIR, "SectigoPublicServerAuthenticationCADVR36.pem")
_NUMERIC_RE = re.compile(r"^\d+(?:\.\d+)?$")


class BCVError(Exception):
    """Error al consultar o interpretar la tasa del BCV."""


class BCVRate(TypedDict):
    """Resultado normalizado de una consulta al BCV."""

    usd: Decimal
    date: date | None
    url: str
    fetched_at: datetime


def _ssl_context() -> ssl.SSLContext:
    """Construye el contexto SSL con la cadena de certificados del BCV."""
    context = ssl.create_default_context()
    for cert in (_ROOT_CERT, _INTERMEDIATE_CERT):
        if not os.path.exists(cert):
            _logger.warning("Certificado no encontrado: %s", cert)
            continue
        context.load_verify_locations(cafile=cert)
    return context


def _invalid_rate(raw: str | None) -> BCVError:
    """Build a consistent error for an unparseable BCV rate."""
    return BCVError(f"Valor de tasa inválido: {raw!r}")


def _normalize_separators(value: str) -> str:
    """Normalize Venezuelan/US thousands and decimal separators."""
    has_dot = "." in value
    has_comma = "," in value
    if has_dot and has_comma:
        if value.rfind(",") > value.rfind("."):
            return value.replace(".", "").replace(",", ".")
        return value.replace(",", "")
    if has_comma:
        if value.count(",") > 1:
            return value.replace(",", "")
        return value.replace(",", ".")
    return value.replace(".", "") if value.count(".") > 1 else value


def _parse_decimal(raw: str | None) -> Decimal:
    """Convierte un valor del BCV a Decimal positivo."""
    value = "".join((raw or "").split())
    if not value:
        raise BCVError("La página del BCV no contiene el valor del dólar.")

    value = _normalize_separators(value)
    if not _NUMERIC_RE.match(value):
        raise _invalid_rate(raw)
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise _invalid_rate(raw) from exc
    if not number.is_finite() or number <= 0:
        raise _invalid_rate(raw)
    return number


def _parse_date(tree: lxml_html.HtmlElement) -> date | None:
    """Extrae la fecha de publicación del BCV, o None si no es posible."""
    nodes = tree.xpath(
        '//*[@id="dolar"]/following::span[contains(@class, "date-display-single")][1]/@content'
    )
    if not nodes:
        nodes = tree.xpath('//span[contains(@class, "date-display-single")]/@content')
    if not nodes:
        _logger.warning("No se encontró la fecha del BCV en la página.")
        return None
    raw = nodes[0].strip()
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return datetime.strptime(raw, BCV_DATE_FORMAT).date()
        except ValueError:
            _logger.warning("No se pudo interpretar la fecha del BCV: %r", nodes[0])
            return None


def fetch_bcv_rates() -> BCVRate:
    """Consulta la página del BCV y devuelve la tasa USD normalizada."""
    request = urllib.request.Request(
        BCV_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Odoo BCV rate updater)",
            "Accept-Language": "es-VE,es;q=0.9",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(
            request, timeout=HTTP_TIMEOUT, context=_ssl_context()
        ) as response:
            body = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise BCVError(f"Error de conexión con bcv.org.ve: {exc}") from exc

    try:
        tree = lxml_html.fromstring(body)
    except (ValueError, etree.ParserError) as exc:
        raise BCVError("No se pudo interpretar la página del BCV.") from exc

    values = tree.xpath('//*[@id="dolar"]//strong[contains(@class, "strong-tb")]/text()')
    if not values:
        values = tree.xpath('//*[@id="dolar"]//strong/text()')
    if not values:
        raise BCVError("No se encontró el valor del dólar en la página del BCV.")

    return {
        "usd": _parse_decimal(values[0]),
        "date": _parse_date(tree),
        "url": BCV_URL,
        "fetched_at": datetime.now(UTC),
    }
