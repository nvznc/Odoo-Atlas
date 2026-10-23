from odoo import api, fields, models


class PosOrder(models.Model):
    """Store the BCV rate and bolivar amounts for each point-of-sale order."""

    _inherit = "pos.order"

    bcv_currency_id = fields.Many2one(
        related="config_id.bcv_currency_id",
        store=True,
        readonly=True,
    )
    bcv_rate = fields.Float(
        string="Tasa BCV (Bs por USD)",
        digits=(12, 6),
        readonly=True,
        copy=False,
    )
    bcv_rate_date = fields.Date(
        string="Fecha de la tasa BCV",
        readonly=True,
        copy=False,
    )
    bcv_amount_total = fields.Monetary(
        string="Total en Bs",
        currency_field="bcv_currency_id",
        compute="_compute_bcv_amount_total",
        store=True,
        readonly=True,
    )
    bcv_payment_amount = fields.Monetary(
        string="Pagado en Bs",
        currency_field="bcv_currency_id",
        compute="_compute_bcv_payment_amount",
        readonly=True,
    )
    bcv_change = fields.Monetary(
        string="Cambio en Bs",
        currency_field="bcv_currency_id",
        compute="_compute_bcv_change",
        readonly=True,
    )

    def _to_bcv(self, amount: float) -> float:
        """Convert an amount from the order currency to BCV currency."""
        self.ensure_one()
        currency = self.bcv_currency_id
        if not currency:
            return 0.0
        return currency.round(amount * (self.bcv_rate or 0.0))

    @api.depends("amount_total", "bcv_rate", "bcv_currency_id")
    def _compute_bcv_amount_total(self):
        for order in self:
            order.bcv_amount_total = order._to_bcv(order.amount_total)

    @api.depends(
        "bcv_currency_id",
        "payment_ids.payment_amount",
        "payment_ids.payment_currency_id",
    )
    def _compute_bcv_payment_amount(self):
        for order in self:
            currency = order.bcv_currency_id
            if not currency:
                order.bcv_payment_amount = 0.0
                continue
            order.bcv_payment_amount = currency.round(
                sum(
                    payment.payment_amount
                    for payment in order.payment_ids
                    if payment.payment_currency_id == currency
                )
            )

    @api.depends("amount_return", "bcv_rate", "bcv_currency_id")
    def _compute_bcv_change(self):
        for order in self:
            order.bcv_change = order._to_bcv(order.amount_return)

    @api.model_create_multi
    def create(self, vals_list):
        """Freeze the session BCV rate on newly created orders."""
        for vals in vals_list:
            session_id = vals.get("session_id")
            if not session_id:
                continue
            session = self.env["pos.session"].browse(session_id)
            if not session.config_id.bcv_enabled:
                continue
            if not vals.get("bcv_rate") and session.bcv_rate:
                vals["bcv_rate"] = session.bcv_rate
                vals["bcv_rate_date"] = session.bcv_rate_date
        return super().create(vals_list)

    def _prepare_refund_values(self, current_session):
        vals = super()._prepare_refund_values(current_session)
        vals.update(
            {
                "bcv_rate": self.bcv_rate,
                "bcv_rate_date": self.bcv_rate_date,
            }
        )
        return vals
