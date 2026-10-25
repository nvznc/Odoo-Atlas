from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPosPrinterJiotBox(TransactionCase):
    def test_printer_type_contains_jiotbox(self):
        selection = self.env["pos.printer"]._fields["printer_type"].selection
        self.assertIn(("jiotbox", "Direct print (jIotBox)"), selection)

    def test_jiotbox_printer_requires_url(self):
        with self.assertRaises(ValidationError):
            self.env["pos.printer"].create(
                {
                    "name": "Kitchen",
                    "printer_type": "jiotbox",
                }
            )

    def test_create_normalizes_url(self):
        printer = self.env["pos.printer"].create(
            {
                "name": "Kitchen",
                "printer_type": "jiotbox",
                "jiotbox_url": "192.168.1.50:8443/",
            }
        )
        self.assertEqual(printer.jiotbox_url, "https://192.168.1.50:8443")

    def test_write_normalizes_url(self):
        printer = self.env["pos.printer"].create(
            {
                "name": "Kitchen",
                "printer_type": "jiotbox",
                "jiotbox_url": "https://192.168.1.50:8443",
            }
        )
        printer.write({"jiotbox_url": "HTTP://Example.COM/Kitchen/"})
        self.assertEqual(printer.jiotbox_url, "http://example.com/Kitchen")

    def test_load_pos_data_fields_includes_jiotbox_url(self):
        fields_list = self.env["pos.printer"]._load_pos_data_fields(self.env["pos.config"])
        self.assertIn("jiotbox_url", fields_list)

    def test_invalid_url_on_write_is_rejected(self):
        printer = self.env["pos.printer"].create(
            {
                "name": "Kitchen",
                "printer_type": "jiotbox",
                "jiotbox_url": "https://192.168.1.50:8443",
            }
        )
        with self.assertRaises(ValidationError):
            printer.write({"jiotbox_url": "ftp://example.com"})


class TestPosConfigJiotBox(TransactionCase):
    def test_customer_receipt_url_is_loaded_in_pos_data(self):
        config = self.env["pos.config"].create(
            {
                "name": "jIotBox Test",
                "payment_method_ids": [(5, 0, 0)],
            }
        )
        [data] = config._load_pos_data_read(config, config)
        self.assertIn("jiotbox_customer_receipt_url", data)

    def test_customer_receipt_url_is_normalized(self):
        config = self.env["pos.config"].create(
            {
                "name": "jIotBox Test",
                "payment_method_ids": [(5, 0, 0)],
                "jiotbox_customer_receipt_url": "192.168.1.60/kitchen/",
            }
        )
        self.assertEqual(
            config.jiotbox_customer_receipt_url,
            "https://192.168.1.60/kitchen",
        )

    def test_invalid_customer_receipt_url_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["pos.config"].create(
                {
                    "name": "jIotBox Test",
                    "jiotbox_customer_receipt_url": "ftp://example.com",
                }
            )

    def test_invalid_customer_receipt_url_on_write_is_rejected(self):
        config = self.env["pos.config"].create(
            {"name": "jIotBox Test", "payment_method_ids": [(5, 0, 0)]}
        )
        with self.assertRaises(ValidationError):
            config.write({"jiotbox_customer_receipt_url": "https://example.com?bad=1"})

    def test_empty_customer_receipt_url_is_allowed(self):
        config = self.env["pos.config"].create(
            {
                "name": "jIotBox Test",
                "payment_method_ids": [(5, 0, 0)],
                "jiotbox_customer_receipt_url": "",
            }
        )
        self.assertFalse(config.jiotbox_customer_receipt_url)
        config.write({"jiotbox_customer_receipt_url": False})
        self.assertFalse(config.jiotbox_customer_receipt_url)
