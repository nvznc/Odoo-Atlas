import unittest

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosBcv(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env["res.currency"].search([("name", "=", "USD")], limit=1)
        cls.ves = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not cls.usd or not cls.ves:
            raise unittest.SkipTest("Se requieren las monedas USD y VES para las pruebas POS BCV.")
        if not cls.ves.active:
            cls.ves.active = True
        if cls.env.company.currency_id != cls.usd:
            cls.env.company.currency_id = cls.usd

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.today = fields.Date.context_today(self.env["res.currency.rate"])
        self.rate = self.env["res.currency.rate"].search(
            [
                ("name", "=", self.today),
                ("currency_id", "=", self.ves.id),
                ("company_id", "=", self.company.root_id.id),
            ],
            limit=1,
        )
        if self.rate:
            self.rate.write({"company_rate": 884.75, "source": "bcv"})
        else:
            self.rate = self.env["res.currency.rate"].create(
                {
                    "name": self.today,
                    "currency_id": self.ves.id,
                    "company_id": self.company.root_id.id,
                    "company_rate": 884.75,
                    "source": "bcv",
                }
            )
        self.config = self.env["pos.config"].create({"name": "BCV Test"})
        self.base_journal = self.env["account.journal"].search(
            [("type", "=", "cash"), ("company_id", "=", self.company.id)], limit=1
        )
        self.journal = self.env["account.journal"].create(
            {
                "name": "Caja Bs Test",
                "code": "CSHT",
                "type": "cash",
                "company_id": self.company.id,
                "currency_id": self.ves.id,
                "default_account_id": self.base_journal.default_account_id.id,
                "loss_account_id": self.base_journal.loss_account_id.id,
                "profit_account_id": self.base_journal.profit_account_id.id,
            }
        )
        self.method = self.env["pos.payment.method"].create(
            {
                "name": "Efectivo Bs Test",
                "journal_id": self.journal.id,
                "currency_id": self.ves.id,
            }
        )
        self.card_method = self.env["pos.payment.method"].create(
            {
                "name": "Tarjeta Bs Test",
                "currency_id": self.ves.id,
            }
        )
        self.config.payment_method_ids = [
            (4, self.method.id),
            (4, self.card_method.id),
        ]
        self.session = self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.uid}
        )
        self.session.set_opening_control(0.0, "", 0.0)

    def test_rate_lookup(self):
        data = self.env["pos.session"]._get_bcv_rate_data(config=self.config)
        self.assertAlmostEqual(data["rate"], 884.75, places=6)
        self.assertEqual(data["source"], "bcv")
        self.assertAlmostEqual(self.session.bcv_rate, 884.75, places=6)

    def test_payment_in_ves(self):
        order = self.env["pos.order"].create(
            {
                "session_id": self.session.id,
                "amount_total": 19.0,
                "amount_paid": 19.0,
                "amount_tax": 0.0,
                "amount_return": 0.0,
            }
        )
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": self.method.id,
                "amount": 10.0,
                "payment_currency_id": self.ves.id,
            }
        )
        self.assertAlmostEqual(payment.payment_rate, 884.75, places=6)
        self.assertAlmostEqual(payment.payment_amount, 8847.50, places=2)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.bcv_amount_total, 16810.25, places=2)
        self.assertAlmostEqual(order.bcv_payment_amount, 8847.50, places=2)

    def test_non_cash_ves_payment_uses_order_rate(self):
        order = self.env["pos.order"].create(
            {
                "session_id": self.session.id,
                "amount_total": 19.0,
                "amount_paid": 10.0,
                "amount_tax": 0.0,
                "amount_return": 0.0,
            }
        )
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": self.card_method.id,
                "amount": 10.0,
                "payment_currency_id": self.ves.id,
                "payment_rate": 1.0,
                "payment_amount": 10.0,
            }
        )
        self.assertAlmostEqual(payment.payment_rate, 884.75, places=6)
        self.assertAlmostEqual(payment.payment_amount, 8847.50, places=2)

    def test_non_cash_ves_payment_keeps_exact_bs_amount(self):
        order = self.env["pos.order"].create(
            {
                "session_id": self.session.id,
                "amount_total": 19.0,
                "amount_paid": 10.0,
                "amount_tax": 0.0,
                "amount_return": 0.0,
            }
        )
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": self.card_method.id,
                "amount": 10.0,
                "payment_currency_id": self.ves.id,
                "payment_rate": 884.75,
                "payment_amount": 8847.50,
            }
        )
        self.assertAlmostEqual(payment.payment_rate, 884.75, places=6)
        self.assertAlmostEqual(payment.payment_amount, 8847.50, places=2)
        self.assertAlmostEqual(payment.amount, 10.0, places=2)

    def test_session_report_shows_bs_payments_and_rate(self):
        order = self.env["pos.order"].create(
            {
                "session_id": self.session.id,
                "amount_total": 19.0,
                "amount_paid": 10.0,
                "amount_tax": 0.0,
                "amount_return": 0.0,
                "state": "paid",
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": self.card_method.id,
                "amount": 10.0,
                "payment_currency_id": self.ves.id,
            }
        )
        data = self.env["report.point_of_sale.report_saledetails"].get_sale_details(
            session_ids=[self.session.id]
        )
        self.assertAlmostEqual(data["bcv_rate"], 884.75, places=6)
        rows = {row["name"]: row for row in data["bcv_payments"]}
        self.assertIn(self.card_method.name, rows)
        self.assertAlmostEqual(rows[self.card_method.name]["amount"], 8847.50, places=2)
        self.assertAlmostEqual(data["bcv_payments_total"], 8847.50, places=2)

    def test_closing_control_data_separates_cash_currencies(self):
        usd_journal = self.env["account.journal"].create(
            {
                "name": "Caja USD Test",
                "code": "CSHU",
                "type": "cash",
                "company_id": self.company.id,
                "currency_id": self.usd.id,
                "default_account_id": self.base_journal.default_account_id.id,
                "loss_account_id": self.base_journal.loss_account_id.id,
                "profit_account_id": self.base_journal.profit_account_id.id,
            }
        )
        bcv_journal = self.env["account.journal"].create(
            {
                "name": "Caja Bs Cierre Test",
                "code": "CSHV",
                "type": "cash",
                "company_id": self.company.id,
                "currency_id": self.ves.id,
                "default_account_id": self.base_journal.default_account_id.id,
                "loss_account_id": self.base_journal.loss_account_id.id,
                "profit_account_id": self.base_journal.profit_account_id.id,
            }
        )
        usd_method = self.env["pos.payment.method"].create(
            {
                "name": "Efectivo USD Cierre Test",
                "journal_id": usd_journal.id,
                "currency_id": self.usd.id,
            }
        )
        bcv_method = self.env["pos.payment.method"].create(
            {
                "name": "Efectivo Bs Cierre Test",
                "journal_id": bcv_journal.id,
                "currency_id": self.ves.id,
            }
        )
        config = self.env["pos.config"].create({"name": "BCV Closing Test"})
        config.payment_method_ids = [(6, 0, [usd_method.id, bcv_method.id, self.card_method.id])]
        session = self.env["pos.session"].create({"config_id": config.id, "user_id": self.env.uid})
        session.set_opening_control(100.0, "", 1000.0)
        orders = self.env["pos.order"].create(
            [
                {
                    "session_id": session.id,
                    "amount_total": 10.0,
                    "amount_paid": 10.0,
                    "amount_tax": 0.0,
                    "amount_return": 0.0,
                    "state": "paid",
                }
                for _index in range(3)
            ]
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": orders[0].id,
                "payment_method_id": usd_method.id,
                "amount": 10.0,
                "payment_currency_id": self.usd.id,
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": orders[1].id,
                "payment_method_id": bcv_method.id,
                "amount": 10.0,
                "payment_currency_id": self.ves.id,
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": orders[2].id,
                "payment_method_id": self.card_method.id,
                "amount": 10.0,
                "payment_currency_id": self.ves.id,
            }
        )

        data = session.get_closing_control_data()

        default_cash = data["default_cash_details"]
        self.assertEqual(default_cash["id"], usd_method.id)
        self.assertEqual(default_cash["currency_id"], self.usd.id)
        self.assertAlmostEqual(default_cash["payment_amount"], 10.0, places=2)
        self.assertAlmostEqual(default_cash["amount"], 110.0, places=2)

        bcv_cash = data["bcv_cash_details"]
        self.assertEqual(bcv_cash["id"], bcv_method.id)
        self.assertEqual(bcv_cash["currency_id"], self.ves.id)
        self.assertAlmostEqual(bcv_cash["opening"], 1000.0, places=2)
        self.assertAlmostEqual(bcv_cash["payment_amount"], 8847.50, places=2)
        self.assertAlmostEqual(bcv_cash["amount"], 9847.50, places=2)

        non_cash = {row["id"]: row for row in data["non_cash_payment_methods"]}
        self.assertIn(self.card_method.id, non_cash)
        self.assertEqual(non_cash[self.card_method.id]["currency_id"], self.ves.id)
        self.assertAlmostEqual(non_cash[self.card_method.id]["amount"], 8847.50, places=2)

    def test_core_currency_checks_are_preserved(self):
        usd_pricelist = self.env["product.pricelist"].create(
            {"name": "USD Test", "currency_id": self.usd.id}
        )
        ves_pricelist = self.env["product.pricelist"].create(
            {"name": "VES Test", "currency_id": self.ves.id}
        )
        with self.assertRaises(ValidationError):
            self.config.write(
                {
                    "use_pricelist": True,
                    "pricelist_id": usd_pricelist.id,
                    "available_pricelist_ids": [(6, 0, [ves_pricelist.id])],
                }
            )

    def test_duplicate_cash_payment_rejected(self):
        order = self.env["pos.order"].create(
            {
                "session_id": self.session.id,
                "amount_total": 19.0,
                "amount_paid": 19.0,
                "amount_tax": 0.0,
                "amount_return": 0.0,
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": self.method.id,
                "amount": 10.0,
                "payment_currency_id": self.ves.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["pos.payment"].create(
                {
                    "pos_order_id": order.id,
                    "payment_method_id": self.method.id,
                    "amount": 9.0,
                    "payment_currency_id": self.ves.id,
                }
            )
