"""Settings helpers to trigger a BCV rate update from the configuration form."""

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Expose BCV status fields and the update action in settings."""

    _inherit = "res.config.settings"

    currency_rate_bcv_last_sync = fields.Datetime(
        related="company_id.currency_rate_bcv_last_sync",
        readonly=True,
    )
    currency_rate_bcv_last_status = fields.Selection(
        related="company_id.currency_rate_bcv_last_status",
        readonly=True,
    )
    currency_rate_bcv_last_message = fields.Text(
        related="company_id.currency_rate_bcv_last_message",
        readonly=True,
    )
    currency_rate_bcv_last_rate = fields.Float(
        related="company_id.currency_rate_bcv_last_rate",
        readonly=True,
    )
    currency_rate_bcv_last_rate_date = fields.Date(
        related="company_id.currency_rate_bcv_last_rate_date",
        readonly=True,
    )

    def action_update_bcv_rate(self) -> dict[str, object]:
        """Run the BCV update in the context of the configured company."""
        return self.env["res.currency.rate"].with_company(self.company_id).action_update_bcv_rate()
