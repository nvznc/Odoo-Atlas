from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    """Require a payment method currency consistent with its journal."""

    _inherit = "pos.payment.method"

    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
        ondelete="restrict",
    )

    @api.constrains("currency_id", "journal_id")
    def _check_currency_journal(self):
        """Ensure the payment method and its journal share a currency."""
        for method in self:
            journal_currency = method.journal_id.currency_id
            if journal_currency and journal_currency != method.currency_id:
                raise ValidationError(
                    _(
                        "El método de pago %(method)s y su diario %(journal)s "
                        "deben usar la misma moneda.",
                        method=method.name,
                        journal=method.journal_id.name,
                    )
                )

    def _load_pos_data_fields(self, config: models.Model) -> list[str]:
        """Expose the payment method currency to the POS frontend."""
        fields_list = super()._load_pos_data_fields(config)
        return fields_list + ["currency_id"]
