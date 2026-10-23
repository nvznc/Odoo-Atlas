import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from lxml import html as lxml_html
from odoo import fields
from odoo.addons.currency_rate_bcv.lib.bcv import (
    BCVError,
    _parse_date,
    _parse_decimal,
)
from odoo.tests import TransactionCase, tagged

_UNSET = object()


@tagged("post_install", "-at_install")
class TestBCVParsing(TransactionCase):
    def test_parse_decimal_formats(self):
        cases = [
            ("884,7496", Decimal("884.7496")),
            ("1.234,56", Decimal("1234.56")),
            ("884.7496", Decimal("884.7496")),
            ("1,234.56", Decimal("1234.56")),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(_parse_decimal(raw), expected)

    def test_parse_decimal_invalid_values(self):
        for raw in ("", "   ", "abc", "12a", "1e3", "0", "0,00", "-1"):
            with self.subTest(raw=raw), self.assertRaises(BCVError):
                _parse_decimal(raw)

    def test_parse_date_returns_iso_date(self):
        tree = lxml_html.fromstring(
            "<html><body><span class='date-display-single' "
            "content='2024-05-03T00:00:00-04:00'>03/05/2024</span></body></html>"
        )
        self.assertEqual(_parse_date(tree), date(2024, 5, 3))


@tagged("post_install", "-at_install")
class TestBCVCurrencyRate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        usd = cls.env["res.currency"].search([("name", "=", "USD")], limit=1)
        if not usd:
            raise unittest.SkipTest("La moneda USD no está disponible.")
        cls.ves = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not cls.ves:
            raise unittest.SkipTest("La moneda VES no está disponible.")
        if cls.company.currency_id != usd:
            cls.company.currency_id = usd
        if not cls.ves.active:
            cls.ves.active = True
        cls.rate_model = cls.env["res.currency.rate"]
        cls.test_date = date(2000, 1, 1)

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.rate_model = self.env["res.currency.rate"]
        self.rate_model.search(
            [("name", "=", self.test_date), ("currency_id", "=", self.ves.id)]
        ).unlink()

    def _mock_fetch(self, usd, rate_date=_UNSET):
        if rate_date is _UNSET:
            rate_date = self.test_date
        return patch(
            "odoo.addons.currency_rate_bcv.models.res_currency_rate.fetch_bcv_rates",
            return_value={
                "usd": usd,
                "date": rate_date,
                "url": "https://www.bcv.org.ve/",
            },
        )

    def _rate_domain(self):
        return [
            ("name", "=", self.test_date),
            ("currency_id", "=", self.ves.id),
            ("company_id", "=", self.company.root_id.id),
        ]

    def test_create_bcv_rate(self):
        with self._mock_fetch(Decimal("884.75")):
            result = self.rate_model._update_bcv_rate(company=self.company)
        rate = self.rate_model.search(self._rate_domain())
        self.assertEqual(len(rate), 1)
        self.assertEqual(rate.source, "bcv")
        self.assertAlmostEqual(rate.company_rate, 884.75, places=6)
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.company.currency_rate_bcv_last_status, "success")

    def test_none_date_uses_today(self):
        today = fields.Date.context_today(self.rate_model)
        self.rate_model.search(
            [
                ("name", "=", today),
                ("currency_id", "=", self.ves.id),
                ("company_id", "in", [False, self.company.root_id.id]),
            ]
        ).unlink()
        with self._mock_fetch(Decimal("800.0"), rate_date=None):
            result = self.rate_model._update_bcv_rate(company=self.company)
        rate = self.rate_model.search(
            [
                ("name", "=", today),
                ("currency_id", "=", self.ves.id),
                ("company_id", "=", self.company.root_id.id),
            ]
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(rate), 1)
        self.assertAlmostEqual(rate.company_rate, 800.0, places=6)

    def test_manual_rate_is_not_overwritten(self):
        manual = self.rate_model.create(
            {
                "name": self.test_date,
                "currency_id": self.ves.id,
                "company_id": self.company.root_id.id,
                "company_rate": 900.0,
                "source": "manual",
            }
        )
        with self._mock_fetch(Decimal("800.0")):
            result = self.rate_model._update_bcv_rate(company=self.company)
        manual.invalidate_recordset()
        self.assertAlmostEqual(manual.company_rate, 900.0, places=6)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(self.company.currency_rate_bcv_last_status, "warning")

    def test_existing_bcv_rate_is_updated(self):
        rate = self.rate_model.create(
            {
                "name": self.test_date,
                "currency_id": self.ves.id,
                "company_id": self.company.root_id.id,
                "company_rate": 900.0,
                "source": "bcv",
            }
        )
        with self._mock_fetch(Decimal("800.0")):
            result = self.rate_model._update_bcv_rate(company=self.company)
        rate.invalidate_recordset()
        self.assertAlmostEqual(rate.company_rate, 800.0, places=6)
        self.assertEqual(result["status"], "success")

    def test_default_source_is_manual(self):
        rate = self.rate_model.create(
            {
                "name": date(2000, 1, 2),
                "currency_id": self.ves.id,
                "company_id": self.company.root_id.id,
                "company_rate": 700.0,
            }
        )
        self.assertEqual(rate.source, "manual")
