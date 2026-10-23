"""Currency rate extensions for BCV synchronization."""

import logging
from datetime import date
from decimal import Decimal

from odoo import _, api, fields, models
from odoo.addons.currency_rate_bcv.lib.bcv import BCVError, fetch_bcv_rates
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_BASE_CURRENCY = "USD"
_VES_CURRENCY = "VES"
_RATE_DECIMALS = 6
_DATE_FORMAT = "%d/%m/%Y"
_STATUS_SUCCESS = "success"
_STATUS_WARNING = "warning"
_STATUS_ERROR = "error"
_NOTIFICATION_DANGER = "danger"
_ACTION_CREATED = "creada"
_ACTION_UPDATED = "actualizada"
_ACTION_SKIPPED = "omitida"


class ResCurrencyRate(models.Model):
    """Add BCV as a source for currency rates and keep manual rates intact."""

    _inherit = "res.currency.rate"

    source = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("bcv", "BCV"),
        ],
        string="Origen",
        default="manual",
        required=True,
        copy=False,
        help="BCV: generada por la actualización automática. Manual: no se sobrescribe.",
    )

    @api.model
    def action_update_bcv_rate(self) -> dict[str, object]:
        """Update the BCV rate from a user action and return a notification."""
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Solo un administrador contable puede actualizar la tasa BCV."))
        result = self._update_bcv_rate()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Tasa BCV",
                "message": result["message"],
                "type": result["notification_type"],
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    @api.model
    def _cron_update_bcv_rate(self) -> None:
        """Update the BCV rate from the scheduled action without raising."""
        self._update_bcv_rate(raise_on_error=False)

    @api.model
    def _update_bcv_rate(
        self,
        company: "models.Model | None" = None,
        raise_on_error: bool = True,
    ) -> dict[str, str]:
        """Fetch, validate and persist the BCV rate for ``company``.

        Expected errors (``BCVError`` and ``UserError``) are stored on the
        company and either re-raised as ``UserError`` or returned as an error
        result. Unexpected errors are left to propagate to the caller.
        """
        company = company or self.env.company
        try:
            ves = self._validate_bcv_company_currency(company)
            rate_value, rate_date = self._fetch_bcv_rate()
            rate_number = float(rate_value)
            _action, message, status, notification_type = self._persist_bcv_rate(
                company, ves, rate_number, rate_date
            )
        except (BCVError, UserError) as exc:
            message = str(exc) or exc.__class__.__name__
            self._set_bcv_status(company, _STATUS_ERROR, message)
            _logger.warning("No se pudo actualizar la tasa BCV: %s", message)
            if raise_on_error:
                raise UserError(message) from exc
            return {
                "status": _STATUS_ERROR,
                "message": message,
                "notification_type": _NOTIFICATION_DANGER,
            }
        self._set_bcv_status(company, status, message, rate_number, rate_date)
        return {
            "status": status,
            "message": message,
            "notification_type": notification_type,
        }

    def _validate_bcv_company_currency(self, company: "models.Model") -> "models.Model":
        """Return the active VES currency or raise ``UserError``."""
        if company.currency_id.name != _BASE_CURRENCY:
            raise UserError(_("La moneda base de la compañía debe ser USD para usar la tasa BCV."))

        ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", _VES_CURRENCY)], limit=1)
        )
        if not ves:
            raise UserError(_("No se encontró la moneda VES."))
        if not ves.active:
            raise UserError(
                _("La moneda VES está inactiva. Actívala antes de actualizar la tasa BCV.")
            )
        return ves

    def _fetch_bcv_rate(self) -> tuple[Decimal, date]:
        """Fetch the BCV USD rate and normalize its date to today's maximum."""
        data = fetch_bcv_rates()
        rate_value = data["usd"]
        if rate_value <= 0:
            raise UserError(_("El BCV devolvió una tasa inválida."))

        today = fields.Date.context_today(self)
        rate_date = data.get("date") or today
        if rate_date > today:
            rate_date = today
        return rate_value, rate_date

    def _persist_bcv_rate(
        self,
        company: "models.Model",
        ves: "models.Model",
        rate_value: float,
        rate_date: date,
    ) -> tuple[str, str, str, str]:
        """Create or update the BCV rate, skipping manual rate overrides.

        Returns the performed action, user message, status and notification
        type so the caller can update the company status.
        """
        Rate = self.sudo()
        domain = [
            ("name", "=", rate_date),
            ("currency_id", "=", ves.id),
            ("company_id", "in", [False, company.root_id.id]),
        ]
        manual_rate = Rate.search(domain + [("source", "=", "manual")], limit=1)
        if manual_rate:
            message = self._build_bcv_message(_ACTION_SKIPPED, rate_value, rate_date)
            return _ACTION_SKIPPED, message, _STATUS_WARNING, _STATUS_WARNING

        existing = Rate.search(domain, order="company_id desc, id desc", limit=1)
        vals = {
            "company_rate": rate_value,
            "source": "bcv",
        }
        if existing:
            existing.write(vals)
            action = _ACTION_UPDATED
        else:
            vals.update(
                {
                    "name": rate_date,
                    "currency_id": ves.id,
                    "company_id": company.root_id.id,
                }
            )
            Rate.create(vals)
            action = _ACTION_CREATED

        message = self._build_bcv_message(action, rate_value, rate_date)
        return action, message, _STATUS_SUCCESS, _STATUS_SUCCESS

    def _build_bcv_message(
        self,
        action: str,
        rate_value: Decimal | float,
        rate_date: date,
    ) -> str:
        """Build the user-facing message for a BCV rate operation."""
        date_label = rate_date.strftime(_DATE_FORMAT)
        rate_label = _format_rate(rate_value)
        if action == _ACTION_SKIPPED:
            return _(
                "Ya existe una tasa manual para VES del %s. "
                "No se modificó. La tasa BCV consultada fue %s."
            ) % (date_label, rate_label)
        return _("Tasa BCV %s: 1 USD = %s VES (%s).") % (
            action,
            rate_label,
            date_label,
        )

    @api.model
    def _set_bcv_status(
        self,
        company: "models.Model",
        status: str,
        message: str,
        rate: float | None = None,
        rate_date: date | None = None,
    ) -> None:
        """Store the last BCV synchronization status on the company."""
        vals = {
            "currency_rate_bcv_last_sync": fields.Datetime.now(),
            "currency_rate_bcv_last_status": status,
            "currency_rate_bcv_last_message": message,
        }
        if rate is not None:
            vals["currency_rate_bcv_last_rate"] = rate
            vals["currency_rate_bcv_last_rate_date"] = rate_date
        company.sudo().write(vals)


def _format_rate(value: Decimal | float) -> str:
    """Format a rate with six decimals, trimming trailing zeros."""
    return f"{value:.{_RATE_DECIMALS}f}".rstrip("0").rstrip(".")
