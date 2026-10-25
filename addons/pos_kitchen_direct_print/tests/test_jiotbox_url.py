from odoo.addons.pos_kitchen_direct_print.models.jiotbox_url import (
    JiotBoxUrlError,
    normalize_jiotbox_url,
    validate_jiotbox_url,
)
from odoo.tests.common import TransactionCase


class TestJiotBoxUrl(TransactionCase):
    def test_bare_host_defaults_to_https(self):
        self.assertEqual(
            normalize_jiotbox_url("192.168.1.50:8443"),
            "https://192.168.1.50:8443",
        )

    def test_trailing_slash_is_stripped(self):
        self.assertEqual(
            normalize_jiotbox_url("https://example.com/"),
            "https://example.com",
        )

    def test_base_path_is_preserved(self):
        self.assertEqual(
            normalize_jiotbox_url("https://example.com/kitchen/"),
            "https://example.com/kitchen",
        )

    def test_http_is_allowed(self):
        self.assertEqual(
            normalize_jiotbox_url("http://192.168.1.50:8080"),
            "http://192.168.1.50:8080",
        )

    def test_scheme_and_host_are_lowercased(self):
        self.assertEqual(
            normalize_jiotbox_url("HTTPS://Example.COM/Kitchen"),
            "https://example.com/Kitchen",
        )

    def test_ftp_is_rejected(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url("ftp://example.com")

    def test_javascript_is_rejected(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url("javascript://example.com")

    def test_credentials_are_rejected(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url("https://user:secret@example.com")

    def test_query_string_is_rejected(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url("https://example.com/kitchen?printer=1")

    def test_fragment_is_rejected(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url("https://example.com/kitchen#main")

    def test_invalid_port_is_rejected(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url("https://example.com:99999")

    def test_non_numeric_port_is_rejected(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url("https://example.com:abc")

    def test_empty_value_is_rejected_by_validate(self):
        with self.assertRaises(JiotBoxUrlError):
            validate_jiotbox_url("   ")

    def test_none_is_rejected_by_validate(self):
        with self.assertRaises(JiotBoxUrlError):
            validate_jiotbox_url(None)

    def test_ipv6_host_is_bracketed(self):
        self.assertEqual(
            normalize_jiotbox_url("http://[2001:DB8::1]:8080/kitchen/"),
            "http://[2001:db8::1]:8080/kitchen",
        )

    def test_maximum_length_is_enforced(self):
        with self.assertRaises(JiotBoxUrlError):
            normalize_jiotbox_url(f"https://{'a' * 510}.com")
