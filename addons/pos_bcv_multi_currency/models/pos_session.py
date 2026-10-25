"""Sesiones de PdV con control de caja en bolívares y tasa BCV."""

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class PosSession(models.Model):
    """Añade una caja secundaria en bolívares y el manejo de la tasa BCV."""

    _inherit = "pos.session"

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
    bcv_rate_source = fields.Char(
        string="Origen de la tasa BCV",
        readonly=True,
        copy=False,
    )
    bcv_cash_journal_id = fields.Many2one(
        "account.journal",
        string="Caja Bs",
        compute="_compute_cash_journal",
        store=True,
        readonly=True,
    )
    bcv_cash_control = fields.Boolean(
        string="Control de caja Bs",
        compute="_compute_bcv_cash_control",
    )
    cash_register_balance_start_bcv = fields.Monetary(
        string="Saldo inicial Bs",
        currency_field="bcv_currency_id",
        readonly=True,
        copy=False,
    )
    cash_register_balance_end_real_bcv = fields.Monetary(
        string="Saldo final contado Bs",
        currency_field="bcv_currency_id",
        readonly=True,
    )
    cash_register_balance_end_bcv = fields.Monetary(
        string="Saldo teórico Bs",
        currency_field="bcv_currency_id",
        compute="_compute_cash_balance",
        readonly=True,
    )
    cash_register_difference_bcv = fields.Monetary(
        string="Diferencia de caja Bs",
        currency_field="bcv_currency_id",
        compute="_compute_cash_balance",
        readonly=True,
    )
    cash_real_transaction_bcv = fields.Monetary(
        string="Movimientos de caja Bs",
        currency_field="bcv_currency_id",
        readonly=True,
        copy=False,
    )

    @api.depends("config_id", "payment_method_ids", "currency_id")
    def _compute_cash_journal(self) -> None:
        """Determina los diarios de caja principal y secundario en Bs."""
        for session in self:
            cash_methods = session.payment_method_ids.filtered("is_cash_count")
            primary = (
                cash_methods.filtered(
                    lambda method, session=session: method.currency_id == session.currency_id
                )[:1]
                or cash_methods[:1]
            )
            session.cash_journal_id = primary.journal_id
            secondary = cash_methods.filtered(
                lambda method, session=session, primary=primary: (
                    method.journal_id
                    and method.journal_id != primary.journal_id
                    and method.currency_id == session.bcv_currency_id
                )
            )[:1]
            if session.config_id.bcv_enabled and session.bcv_currency_id:
                session.bcv_cash_journal_id = secondary.journal_id
            else:
                session.bcv_cash_journal_id = False

    @api.depends(
        "bcv_cash_journal_id",
        "config_id.cash_control",
        "config_id.bcv_enabled",
    )
    def _compute_bcv_cash_control(self) -> None:
        """Indica si la sesión debe controlar una caja secundaria en Bs."""
        for session in self:
            session.bcv_cash_control = bool(
                session.config_id.bcv_enabled
                and session.config_id.cash_control
                and session.bcv_cash_journal_id
            )

    @api.depends(
        "payment_method_ids",
        "order_ids",
        "cash_register_balance_start",
        "cash_register_balance_end_real",
        "statement_line_ids",
        "cash_real_transaction",
        "bcv_cash_journal_id",
        "cash_register_balance_start_bcv",
        "cash_register_balance_end_real_bcv",
        "cash_real_transaction_bcv",
    )
    def _compute_cash_balance(self) -> None:
        """Calcula los saldos y diferencias de ambas cajas de la sesión."""
        for session in self:
            end, difference = session._compute_cash_balance_for_journal(
                session.cash_journal_id,
                session.cash_register_balance_start,
                session.cash_register_balance_end_real,
                session.cash_real_transaction,
                "amount",
            )
            session.cash_register_balance_end = end
            session.cash_register_difference = difference

            if session.bcv_cash_journal_id:
                end_bcv, difference_bcv = session._compute_cash_balance_for_journal(
                    session.bcv_cash_journal_id,
                    session.cash_register_balance_start_bcv,
                    session.cash_register_balance_end_real_bcv,
                    session.cash_real_transaction_bcv,
                    "payment_amount",
                )
            else:
                end_bcv, difference_bcv = 0.0, 0.0
            session.cash_register_balance_end_bcv = end_bcv
            session.cash_register_difference_bcv = difference_bcv

    def _compute_cash_balance_for_journal(
        self,
        journal: models.Model,
        start: float,
        end_real: float,
        real_transaction: float,
        amount_field: str,
    ) -> tuple[float, float]:
        """Calcula el saldo teórico y la diferencia de un diario de caja."""
        method = self.payment_method_ids.filtered(
            lambda payment_method: (
                payment_method.is_cash_count and payment_method.journal_id == journal
            )
        )[:1]
        if not method:
            return 0.0, 0.0
        domain = [("payment_method_id", "=", method.id)]
        domain += self._get_captured_payments_domain()
        total_payment = self._sum_payments(domain, amount_field)
        if self.state == "closed":
            total_cash = real_transaction + total_payment
        else:
            lines = self.sudo().statement_line_ids.filtered(lambda line: line.journal_id == journal)
            total_cash = sum(lines.mapped("amount")) + total_payment
        end = start + total_cash
        return end, end_real - end

    def _sum_payments(self, domain: list, field_name: str) -> float:
        """Suma un campo monetario de los pagos que cumplen el dominio."""
        result = self.env["pos.payment"]._read_group(
            domain,
            aggregates=[f"{field_name}:sum"],
        )
        return result[0][0] or 0.0 if result else 0.0

    @api.model
    def _get_bcv_rate_data(
        self,
        config: models.Model | None = None,
        company: models.Model | None = None,
        date: date | None = None,
    ) -> dict:
        """Obtiene la tasa BCV aplicable a la configuración y fecha dadas."""
        config = config or (self[:1].config_id if self else False)
        company = company or (self[:1].company_id if self else self.env.company)
        currency = (
            config.bcv_currency_id if config else self.env.ref("base.VES", raise_if_not_found=False)
        )
        if not currency:
            return {
                "rate": 0.0,
                "date": False,
                "source": False,
                "currency_id": False,
            }

        date = date or fields.Date.context_today(self)
        rate = (
            self.env["res.currency.rate"]
            .sudo()
            .search(
                [
                    ("currency_id", "=", currency.id),
                    ("company_id", "in", [False, company.root_id.id]),
                    ("name", "<=", date),
                ],
                order="name desc, id desc",
                limit=1,
            )
        )
        if not rate:
            return {
                "rate": 0.0,
                "date": False,
                "source": False,
                "currency_id": currency.id,
            }
        return {
            "rate": rate.company_rate,
            "date": rate.name,
            "source": rate.source or "manual",
            "currency_id": currency.id,
        }

    def _set_bcv_rate(self) -> dict:
        """Escribe en la sesión la tasa BCV vigente y devuelve sus datos."""
        self.ensure_one()
        data = self._get_bcv_rate_data(
            config=self.config_id,
            company=self.company_id,
        )
        self.write(
            {
                "bcv_rate": data["rate"],
                "bcv_rate_date": data["date"],
                "bcv_rate_source": data["source"],
            }
        )
        return data

    def action_refresh_bcv_rate(self) -> dict:
        """Actualiza la tasa BCV desde la acción del formulario de sesión."""
        self.ensure_one()
        if not self.config_id.bcv_enabled:
            raise UserError(_("El cobro en bolívares no está habilitado en esta configuración."))
        if self.state not in ("opening_control", "opened"):
            raise UserError(_("Solo se puede actualizar la tasa en una sesión abierta."))
        data = self._set_bcv_rate()
        message = (
            _(
                "Tasa BCV actualizada: Bs %(rate).6f por USD.",
                rate=data["rate"],
            )
            if data["rate"]
            else _("No se encontró una tasa BCV para la fecha actual.")
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Tasa BCV"),
                "message": message,
                "type": "success" if data["rate"] else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> models.Model:
        """Inicializa la tasa BCV al crear sesiones con bolívares habilitados."""
        sessions = super().create(vals_list)
        for session in sessions:
            if session.config_id.bcv_enabled and not session.bcv_rate:
                session._set_bcv_rate()
        return sessions

    def action_pos_session_open(self) -> object:
        """Actualiza la tasa e inicializa el saldo de apertura en Bs."""
        for session in self.filtered(
            lambda session: session.state == "opening_control" and session.config_id.bcv_enabled
        ):
            session._set_bcv_rate()
        result = super().action_pos_session_open()
        for session in self:
            if session.config_id.bcv_enabled and session.bcv_cash_control:
                last_session = self.search(
                    [
                        ("config_id", "=", session.config_id.id),
                        ("id", "!=", session.id),
                    ],
                    order="id desc",
                    limit=1,
                )
                session.cash_register_balance_start_bcv = (
                    last_session.cash_register_balance_end_real_bcv
                )
        return result

    def set_opening_control(
        self,
        cashbox_value: float,
        notes: str,
        cashbox_value_bcv: float = None,
    ) -> None:
        """Abre la sesión y registra el saldo inicial contado en bolívares."""
        was_opening_control = self.state == "opening_control"
        result = super().set_opening_control(cashbox_value, notes)
        if was_opening_control and self.bcv_cash_control and cashbox_value_bcv is not None:
            self.cash_register_balance_start_bcv = cashbox_value_bcv
        return result

    def post_closing_cash_details(
        self,
        counted_cash: float,
        counted_cash_bcv: float = None,
    ) -> dict:
        """Registra el efectivo contado al cierre, incluido el de bolívares."""
        result = super().post_closing_cash_details(counted_cash)
        if counted_cash_bcv is not None and self.bcv_cash_control:
            self.cash_register_balance_end_real_bcv = counted_cash_bcv
        return result

    def _get_cash_payment_methods(self) -> models.Model:
        """Devuelve los métodos de pago configurados como efectivo."""
        return self.payment_method_ids.filtered("is_cash_count")

    def _get_default_cash_method(self) -> models.Model:
        """Elige la caja principal, priorizando la moneda de la sesión."""
        cash_methods = self._get_cash_payment_methods()
        return (
            cash_methods.filtered(lambda method: method.currency_id == self.currency_id)[:1]
            or cash_methods[:1]
        )

    def _get_bcv_cash_method(self) -> models.Model:
        """Devuelve el método de efectivo asociado al diario en bolívares."""
        cash_methods = self._get_cash_payment_methods()
        if not self.bcv_cash_journal_id:
            return cash_methods.browse()
        return cash_methods.filtered(lambda method: method.journal_id == self.bcv_cash_journal_id)[
            :1
        ]

    def _get_cash_lines(self, journal: models.Model) -> models.Model:
        """Devuelve las líneas de extracto de un diario concreto."""
        if not journal:
            return self.statement_line_ids.browse()
        return (
            self.sudo()
            .statement_line_ids.filtered(lambda line: line.journal_id == journal)
            .sorted("create_date")
        )

    def _get_cash_moves(self, journal: models.Model) -> list[dict]:
        """Devuelve los movimientos de caja de un diario concreto."""
        cash_in_count = 0
        cash_out_count = 0
        cash_in_out_list = []
        for line in self._get_cash_lines(journal):
            if line.amount > 0:
                cash_in_count += 1
                name = f"Cash in {cash_in_count}"
            else:
                cash_out_count += 1
                name = f"Cash out {cash_out_count}"
            cash_in_out_list.append(
                {
                    "name": line.payment_ref or name,
                    "amount": line.amount,
                    "id": line.id,
                    "date": line.create_date,
                    "cashier_name": self._get_cash_move_cashier_name(line),
                }
            )
        return cash_in_out_list

    def _to_bcv_amount(self, payment: models.Model, currency: models.Model) -> float:
        """Convierte un pago a bolívares usando el importe guardado en Bs."""
        if payment.payment_currency_id == currency:
            return payment.payment_amount or 0.0
        rate = self.bcv_rate or payment.payment_rate or 1.0
        return currency.round((payment.amount or 0.0) * rate)

    def get_closing_control_data(self) -> dict:
        """Añade monedas por método y los detalles de la caja en Bs."""
        data = super().get_closing_control_data()
        orders = self._get_closed_orders()
        payments = orders.payment_ids.filtered(
            lambda payment: payment.payment_method_id.type != "pay_later"
        )
        bcv_currency = self.bcv_currency_id
        default_cash_method = self._get_default_cash_method()
        bcv_cash_method = self._get_bcv_cash_method()

        if default_cash_method:
            cash_payments = payments.filtered(
                lambda payment, method=default_cash_method: payment.payment_method_id == method
            )
            default_cash_lines = self._get_cash_lines(default_cash_method.journal_id)
            data["default_cash_details"] = {
                "name": default_cash_method.name,
                "amount": self.cash_register_balance_start
                + sum(cash_payments.mapped("amount"))
                + sum(default_cash_lines.mapped("amount")),
                "opening": self.cash_register_balance_start,
                "payment_amount": sum(cash_payments.mapped("amount")),
                "moves": self._get_cash_moves(default_cash_method.journal_id),
                "id": default_cash_method.id,
                "currency_id": default_cash_method.currency_id.id or self.currency_id.id,
            }
        else:
            data["default_cash_details"] = {}

        non_cash_methods = (
            self.payment_method_ids - default_cash_method
            if default_cash_method
            else self.payment_method_ids
        )
        non_cash_payment_methods = []
        for method in non_cash_methods:
            if self.bcv_cash_control and bcv_cash_method and method == bcv_cash_method:
                continue
            method_payments = orders.payment_ids.filtered(
                lambda payment, method=method: payment.payment_method_id == method
            )
            currency = method.currency_id or method.journal_id.currency_id or self.currency_id
            if bcv_currency and currency == bcv_currency:
                amount = sum(
                    self._to_bcv_amount(payment, bcv_currency) for payment in method_payments
                )
            else:
                amount = sum(method_payments.mapped("amount"))
            non_cash_payment_methods.append(
                {
                    "name": method.name,
                    "amount": amount,
                    "amount_company": sum(method_payments.mapped("amount")),
                    "number": len(method_payments),
                    "id": method.id,
                    "type": method.type,
                    "currency_id": currency.id,
                }
            )
        data["non_cash_payment_methods"] = non_cash_payment_methods

        if self.bcv_cash_control and bcv_cash_method:
            bcv_payments = payments.filtered(
                lambda payment, method=bcv_cash_method: payment.payment_method_id == method
            )
            data["bcv_cash_details"] = {
                "name": bcv_cash_method.name,
                "amount": self.cash_register_balance_end_bcv,
                "opening": self.cash_register_balance_start_bcv,
                "payment_amount": sum(
                    self._to_bcv_amount(payment, bcv_currency) for payment in bcv_payments
                ),
                "moves": self._get_cash_moves(self.bcv_cash_journal_id),
                "id": bcv_cash_method.id,
                "currency_id": bcv_currency.id,
            }
        return data

    def _validate_session(
        self,
        balancing_account=False,
        amount_to_balance=0,
        bank_payment_method_diffs=None,
    ) -> bool:
        """Calcula los movimientos reales en Bs antes de validar la sesión."""
        bcv_lines = self.sudo().statement_line_ids.filtered(
            lambda line: line.journal_id == self.bcv_cash_journal_id
        )
        self.cash_real_transaction_bcv = sum(bcv_lines.mapped("amount"))
        return super()._validate_session(
            balancing_account,
            amount_to_balance,
            bank_payment_method_diffs,
        )

    def _get_bcv_cash_difference(self) -> float:
        """Devuelve la diferencia de caja en Bs redondeada a su moneda."""
        method = self.payment_method_ids.filtered(
            lambda payment_method: (
                payment_method.is_cash_count
                and payment_method.journal_id == self.bcv_cash_journal_id
            )
        )[:1]
        if not method:
            return 0.0
        domain = [("payment_method_id", "=", method.id)]
        domain += self._get_captured_payments_domain()
        total_payment = self._sum_payments(domain, "payment_amount")
        expected = self.cash_register_balance_start_bcv + total_payment
        difference = self.cash_register_balance_end_real_bcv - expected
        currency = self.bcv_currency_id or self.company_id.currency_id
        return currency.round(difference)

    def _post_statement_difference(self, amount: float) -> None:
        """Contabiliza la diferencia de caja del diario principal y del de Bs."""
        self._post_statement_difference_for_journal(amount, self.cash_journal_id)
        if self.bcv_cash_journal_id and self.bcv_cash_journal_id != self.cash_journal_id:
            self._post_statement_difference_for_journal(
                self._get_bcv_cash_difference(),
                self.bcv_cash_journal_id,
            )

    def _post_statement_difference_for_journal(
        self,
        amount: float,
        journal: models.Model,
    ) -> None:
        """Crea el extracto de diferencia de caja para el diario indicado."""
        if not amount or not journal:
            return
        date = self.statement_line_ids.sorted()[-1:].date or fields.Date.context_today(self)
        st_line_vals = {
            "journal_id": journal.id,
            "amount": amount,
            "date": date,
            "pos_session_id": self.id,
        }

        if amount < 0.0:
            if not journal.loss_account_id:
                raise UserError(
                    _(
                        "Please go on the %s journal and define a Loss Account. "
                        "This account will be used to record cash difference.",
                        journal.name,
                    )
                )
            st_line_vals["payment_ref"] = _(
                "Cash difference observed during the counting (Loss) - closing"
            )
            counterpart_account = journal.loss_account_id
        else:
            if not journal.profit_account_id:
                raise UserError(
                    _(
                        "Please go on the %s journal and define a Profit Account. "
                        "This account will be used to record cash difference.",
                        journal.name,
                    )
                )
            st_line_vals["payment_ref"] = _(
                "Cash difference observed during the counting (Profit) - closing"
            )
            counterpart_account = journal.profit_account_id

        if counterpart_account.tax_ids:
            st_line_vals["line_ids"] = self._prepare_cash_diff_line_ids(
                amount,
                counterpart_account,
                counterpart_account.tax_ids,
                st_line_vals["payment_ref"],
                st_line_vals["date"],
                journal=journal,
            )
        else:
            st_line_vals["counterpart_account_id"] = counterpart_account.id

        created_line = (
            self.env["account.bank.statement.line"]
            .with_context(no_retrieve_partner=True)
            .create(st_line_vals)
        )
        if created_line:
            created_line.move_id.message_post(
                body=_(
                    "Related Session: %(link)s",
                    link=self._get_html_link(),
                )
            )

    def _prepare_cash_diff_line_ids(
        self,
        amount: float,
        counterpart_account: models.Model,
        taxes: models.Model,
        name: str,
        date: date,
        journal: models.Model | None = None,
    ) -> list:
        """Prepara las líneas de diferencia reutilizando el core si aplica."""
        if journal is None or journal == self.cash_journal_id:
            return super()._prepare_cash_diff_line_ids(
                amount,
                counterpart_account,
                taxes,
                name,
                date,
            )
        return self._prepare_cash_diff_line_ids_for_journal(
            amount,
            counterpart_account,
            taxes,
            name,
            date,
            journal,
        )

    def _prepare_cash_diff_line_ids_for_journal(
        self,
        amount: float,
        counterpart_account: models.Model,
        taxes: models.Model,
        name: str,
        date: date,
        journal: models.Model,
    ) -> list:
        """Prepara las líneas de diferencia para un diario distinto al core."""
        company = self.company_id
        company_currency = company.currency_id
        journal_currency = journal.currency_id or company_currency

        def to_company_currency(amount_in_journal_currency: float) -> float:
            if journal_currency == company_currency:
                return amount_in_journal_currency
            return journal_currency._convert(
                amount_in_journal_currency,
                company_currency,
                company,
                date,
            )

        taxes_res = taxes.with_context(force_price_include=True).compute_all(
            abs(amount),
            currency=journal_currency,
            quantity=1.0,
        )
        sign = 1.0 if amount > 0 else -1.0
        cash_amount = sign * taxes_res["total_included"]
        base_amount = -sign * taxes_res["total_excluded"]

        line_ids = [
            Command.create(
                {
                    "name": name,
                    "account_id": journal.default_account_id.id,
                    "currency_id": journal_currency.id,
                    "amount_currency": cash_amount,
                    "balance": to_company_currency(cash_amount),
                }
            ),
            Command.create(
                {
                    "name": name,
                    "account_id": counterpart_account.id,
                    "currency_id": journal_currency.id,
                    "amount_currency": base_amount,
                    "balance": to_company_currency(base_amount),
                    "tax_ids": [Command.set(taxes.ids)],
                    "tax_tag_ids": [Command.set(taxes_res["base_tags"])],
                }
            ),
        ]
        for tax_res in taxes_res["taxes"]:
            tax_amount = -sign * tax_res["amount"]
            line_ids.append(
                Command.create(
                    {
                        "name": tax_res["name"],
                        "account_id": (tax_res["account_id"] or counterpart_account.id),
                        "currency_id": journal_currency.id,
                        "amount_currency": tax_amount,
                        "balance": to_company_currency(tax_amount),
                        "tax_base_amount": to_company_currency(taxes_res["total_excluded"]),
                        "tax_repartition_line_id": (tax_res["tax_repartition_line_id"]),
                        "tax_tag_ids": [Command.set(tax_res["tag_ids"])],
                        "display_type": "tax",
                    }
                )
            )
        return line_ids

    def _load_pos_data_fields(self, config: models.Model) -> list[str]:
        """Añade los campos BCV que necesita el frontend del PdV."""
        fields_list = super()._load_pos_data_fields(config)
        return fields_list + [
            "bcv_rate",
            "bcv_rate_date",
            "bcv_currency_id",
            "bcv_cash_journal_id",
            "bcv_cash_control",
            "cash_register_balance_start_bcv",
        ]
