from odoo import api, fields, models


class PosConfig(models.Model):
    """Allow a BCV currency and payment methods in the point of sale."""

    _inherit = "pos.config"

    bcv_enabled = fields.Boolean(
        string="Habilitar cobro en bolívares",
        default=True,
        help="Permite usar métodos de pago y una caja en la moneda BCV.",
    )
    bcv_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda BCV",
        default=lambda self: self.env.ref("base.VES", raise_if_not_found=False),
        ondelete="restrict",
    )

    def _bcv_payment_allowed(self, payment_method: models.Model) -> bool:
        """Return whether a payment method may use a non-config currency."""
        self.ensure_one()
        journal_currency = payment_method.journal_id.currency_id
        return bool(
            journal_currency
            and journal_currency != self.currency_id
            and self.bcv_enabled
            and self.bcv_currency_id
            and payment_method.currency_id == self.bcv_currency_id
            and journal_currency == payment_method.currency_id
        )

    @api.constrains(
        "pricelist_id",
        "use_pricelist",
        "available_pricelist_ids",
        "journal_id",
        "invoice_journal_id",
        "payment_method_ids",
        "bcv_enabled",
        "bcv_currency_id",
    )
    def _check_currencies(self) -> None:
        """Run the core currency checks plus the BCV exception rule."""
        for config in self:
            allowed_methods = config.payment_method_ids.filtered(config._bcv_payment_allowed)
            config_to_check = config
            if allowed_methods:
                config_to_check = config.new(
                    {
                        "pricelist_id": config.pricelist_id.id,
                        "use_pricelist": config.use_pricelist,
                        "available_pricelist_ids": [(6, 0, config.available_pricelist_ids.ids)],
                        "journal_id": config.journal_id.id,
                        "invoice_journal_id": config.invoice_journal_id.id,
                        "company_id": config.company_id.id,
                        "payment_method_ids": [
                            (6, 0, (config.payment_method_ids - allowed_methods).ids)
                        ],
                    }
                )
            super(PosConfig, config_to_check)._check_currencies()
