from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

RATE_EPSILON = 1e-6


class PosPayment(models.Model):
    """Support payments in a currency different from the order currency."""

    _inherit = "pos.payment"

    payment_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda de pago",
        default=lambda self: self.pos_order_id.currency_id or self.env.company.currency_id,
        ondelete="restrict",
    )
    payment_amount = fields.Monetary(
        string="Importe en moneda de pago",
        currency_field="payment_currency_id",
        default=0.0,
    )
    payment_rate = fields.Float(
        string="Tasa de pago",
        digits=(12, 6),
        default=1.0,
    )

    def _payment_currency(
        self, order: models.Model | bool, currency_id: int | None
    ) -> models.Model:
        """Resolve the payment currency from values, order or company."""
        if currency_id:
            return self.env["res.currency"].browse(currency_id)
        if order:
            return order.currency_id
        return self.env.company.currency_id

    def _resolve_payment_rate(
        self,
        order: models.Model | bool,
        currency: models.Model,
        client_rate: float,
    ) -> float:
        """Resolve the effective payment rate preserving the legacy rules."""
        is_ves = bool(order and currency == order.bcv_currency_id)
        rate = client_rate
        if is_ves and order.bcv_rate:
            rate = order.bcv_rate
        if not rate and order:
            rate = order.bcv_rate if is_ves else (order.currency_rate or 1.0)
        return rate or 1.0

    def _normalize_payment_amounts(
        self,
        vals: dict,
        order_currency: models.Model,
        currency: models.Model,
        rate: float,
        client_rate: float,
    ) -> None:
        """Normalize the amount and payment_amount values in place."""
        amount = vals.get("amount")
        payment_amount = vals.get("payment_amount")

        if currency == order_currency:
            if payment_amount is None:
                vals["payment_amount"] = amount or 0.0
            return

        same_rate = bool(client_rate and abs(client_rate - rate) < RATE_EPSILON)
        if amount is not None and payment_amount is not None and same_rate:
            vals["amount"] = order_currency.round(payment_amount / rate)
            return
        if amount is not None:
            vals["payment_amount"] = currency.round(amount * rate)
            return
        if payment_amount is not None and rate:
            vals["amount"] = order_currency.round(payment_amount / rate)

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> models.Model:
        """Create payments, resolving currency, rate and amounts first."""
        for vals in vals_list:
            order = (
                self.env["pos.order"].browse(vals["pos_order_id"])
                if vals.get("pos_order_id")
                else False
            )
            order_currency = order.currency_id if order else self.env.company.currency_id
            currency = self._payment_currency(order, vals.get("payment_currency_id"))
            client_rate = float(vals.get("payment_rate") or 0.0)
            rate = self._resolve_payment_rate(order, currency, client_rate)
            vals["payment_currency_id"] = currency.id
            vals["payment_rate"] = rate
            self._normalize_payment_amounts(vals, order_currency, currency, rate, client_rate)
        return super().create(vals_list)

    @api.constrains("pos_order_id", "payment_method_id", "is_change")
    def _check_single_cash_payment(self):
        for payment in self:
            if payment.is_change or not payment.payment_method_id.is_cash_count:
                continue
            cash_payments = payment.pos_order_id.payment_ids.filtered(
                lambda item: not item.is_change and item.payment_method_id.is_cash_count
            )
            if len(cash_payments) > 1:
                raise ValidationError(
                    _(
                        "Solo se permite un pago en efectivo por pedido. "
                        "Use otro método para el resto del importe."
                    )
                )
