from odoo import api, models


class ReportPointOfSaleSaleDetails(models.AbstractModel):
    """Add the bolivar payment breakdown and BCV rate to the session report."""

    _inherit = "report.point_of_sale.report_saledetails"

    def _get_bcv_payment_amount(self, payment, session):
        """Return the payment amount in bolivars for a BCV session."""
        currency = session.bcv_currency_id
        if not currency:
            return 0.0
        if payment.payment_currency_id == currency and payment.payment_amount:
            return payment.payment_amount
        rate = session.bcv_rate or payment.payment_rate or 1.0
        return currency.round((payment.amount or 0.0) * rate)

    @api.model
    def get_sale_details(
        self,
        date_start=False,
        date_stop=False,
        config_ids=False,
        session_ids=False,
        **kwargs,
    ):
        """Expose BCV payment methods and the rate used in the report."""
        data = super().get_sale_details(date_start, date_stop, config_ids, session_ids, **kwargs)
        domain = self._get_domain(date_start, date_stop, config_ids, session_ids, **kwargs)
        orders = self.env["pos.order"].search(domain)
        if session_ids:
            sessions = self.env["pos.session"].browse(session_ids).exists()
        else:
            sessions = orders.session_id

        bcv_payments = []
        for session in sessions:
            currency = session.bcv_currency_id
            if not currency:
                continue
            session_payments = orders.filtered(
                lambda order, session=session: order.session_id == session
            ).payment_ids
            methods = session.payment_method_ids.filtered(
                lambda method, currency=currency: method.currency_id == currency
            )
            for method in methods:
                method_payments = session_payments.filtered(
                    lambda payment, method=method: payment.payment_method_id == method
                )
                if not method_payments:
                    continue
                bcv_payments.append(
                    {
                        "name": method.name,
                        "session_name": session.name,
                        "amount": sum(
                            self._get_bcv_payment_amount(payment, session)
                            for payment in method_payments
                        ),
                        "amount_company": sum(method_payments.mapped("amount")),
                        "number": len(method_payments),
                        "rate": session.bcv_rate,
                        "rate_date": session.bcv_rate_date,
                        "currency_id": currency.id,
                    }
                )

        rates = {rate for rate in sessions.mapped("bcv_rate") if rate}
        dates = {date for date in sessions.mapped("bcv_rate_date") if date}
        currencies = sessions.mapped("bcv_currency_id")
        currency = currencies[:1] or self.env.company.currency_id
        data.update(
            {
                "bcv_payments": bcv_payments,
                "bcv_payments_total": sum(row["amount"] for row in bcv_payments),
                "bcv_rate": rates.pop() if len(rates) == 1 else False,
                "bcv_rate_date": dates.pop() if len(dates) == 1 else False,
                "bcv_currency": {
                    "symbol": currency.symbol,
                    "position": currency.position == "after",
                    "precision": currency.decimal_places,
                },
                "show_bcv_session": len(sessions) > 1,
            }
        )
        return data
