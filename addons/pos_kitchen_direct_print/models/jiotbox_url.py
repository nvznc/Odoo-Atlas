"""Validation and normalization helpers for jIotBox agent URLs."""

from __future__ import annotations

import re
from urllib.parse import SplitResult, urlsplit

from odoo import _

MAX_URL_LENGTH = 512
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_EXPLICIT_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class JiotBoxUrlError(ValueError):
    """Raised when a jIotBox URL cannot be normalized or validated."""


def _check_text(url: str | None) -> str:
    """Return the stripped URL or raise if it is empty, unsafe or too long."""
    if url is None:
        raise JiotBoxUrlError(_("A jIotBox URL is required."))
    text = str(url).strip()
    if not text:
        raise JiotBoxUrlError(_("A jIotBox URL is required."))
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127 for character in text
    ):
        raise JiotBoxUrlError(
            _("The jIotBox URL must not contain whitespace or control characters.")
        )
    if len(text) > MAX_URL_LENGTH:
        raise JiotBoxUrlError(
            _("The jIotBox URL must not exceed %(length)s characters.", length=MAX_URL_LENGTH)
        )
    return text


def _split_url(text: str) -> SplitResult:
    """Split the URL and reject unsupported schemes, credentials and delimiters."""
    if not _EXPLICIT_SCHEME.match(text):
        text = f"https://{text}"
    try:
        parts = urlsplit(text)
    except ValueError as error:
        raise JiotBoxUrlError(_("The jIotBox URL is not a valid URL.")) from error
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise JiotBoxUrlError(_("Only HTTP and HTTPS jIotBox URLs are supported."))
    if parts.username is not None or parts.password is not None:
        raise JiotBoxUrlError(_("The jIotBox URL must not contain credentials."))
    if parts.query or parts.fragment:
        raise JiotBoxUrlError(_("The jIotBox URL must not contain a query string or fragment."))
    return parts


def _format_netloc(host: str, port: int | None) -> str:
    """Return a lower-case netloc, bracketing IPv6 hosts when needed."""
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return netloc


def normalize_jiotbox_url(url: str | None) -> str:
    """Normalize a jIotBox agent URL.

    The scheme defaults to HTTPS, scheme and host are lower-cased, a trailing
    slash is removed and an optional base path is preserved. Invalid or unsafe
    URLs raise :class:`JiotBoxUrlError`.

    :param url: URL or bare host provided by the user.
    :return: The normalized URL.
    """
    text = _check_text(url)
    parts = _split_url(text)
    try:
        host = parts.hostname
        port = parts.port
    except ValueError as error:
        raise JiotBoxUrlError(_("The jIotBox URL contains an invalid port.")) from error
    if not host:
        raise JiotBoxUrlError(_("The jIotBox URL must contain a host."))
    path = parts.path.rstrip("/")
    normalized = f"{parts.scheme.lower()}://{_format_netloc(host.lower(), port)}{path}"
    if len(normalized) > MAX_URL_LENGTH:
        raise JiotBoxUrlError(
            _("The jIotBox URL must not exceed %(length)s characters.", length=MAX_URL_LENGTH)
        )
    return normalized


def validate_jiotbox_url(url: str | None) -> str:
    """Validate and normalize a mandatory jIotBox agent URL.

    :param url: URL or bare host provided by the user.
    :return: The normalized URL.
    """
    if url is None or not str(url).strip():
        raise JiotBoxUrlError(_("A jIotBox URL is required."))
    return normalize_jiotbox_url(url)
