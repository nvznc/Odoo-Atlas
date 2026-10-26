from __future__ import annotations

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install", "atlas_studio")
class TestStudioViews(TransactionCase):
    """Pruebas del motor de vistas y operaciones de Atlas-Odoo-Studio."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = new_test_user(
            cls.env,
            login="atlas_view_designer",
            groups="base.group_user,atlas_odoo_studio.group_studio_designer",
        )
        cls.service = cls.env["studio.metadata.service"].with_user(cls.designer)
        cls.model_data = cls.service.create_model("Atlas Vista")
        cls.model_name = cls.model_data["model"]
        cls.base_view_id = cls.model_data["form_view_id"]

    def _add_node(self, node_xml: str = '<field name="x_name"/>') -> dict:
        return {
            "op_type": "add_node",
            "target_xpath": "/form[1]/sheet[1]/group[1]",
            "position": "inside",
            "node_xml": node_xml,
        }

    def test_get_editor_data_returns_base_view(self):
        data = self.service.get_editor_data(self.model_name, "form")
        self.assertEqual(data["model"], self.model_name)
        self.assertEqual(data["base_view_id"], self.base_view_id)
        self.assertIn('name="x_name"', data["arch"])
        base_view = self.env["ir.ui.view"].browse(self.base_view_id)
        self.assertTrue(base_view.key.startswith(f"atlas_odoo_studio.{self.env.company.id}."))
        self.assertFalse(data["customization"])
        self.assertEqual(data["operations"], [])
        self.assertTrue(any(field["name"] == "x_name" for field in data["fields"]))

    def test_preview_operations_returns_extension_arch(self):
        result = self.service.preview_operations(self.model_name, "form", [self._add_node()])
        self.assertIn("<xpath", result["arch"])
        self.assertIn('position="inside"', result["arch"])
        self.assertEqual(len(result["operations"]), 1)

    def test_save_customization_creates_extension_view(self):
        result = self.service.save_customization(self.model_name, "form", [self._add_node()])
        self.assertEqual(result["version"], 1)
        extension = self.env["ir.ui.view"].browse(result["extension_view_id"])
        self.assertTrue(extension.exists())
        self.assertEqual(extension.mode, "extension")
        self.assertEqual(extension.inherit_id.id, self.base_view_id)
        self.assertEqual(extension.type, "form")
        self.assertTrue(extension.key.startswith(f"atlas_odoo_studio.{self.env.company.id}."))

        combined = self.env[self.model_name].get_view(self.base_view_id, "form")["arch"]
        self.assertEqual(combined.count('name="x_name"'), 2)

        data = self.service.get_editor_data(self.model_name, "form")
        self.assertNotEqual(data["customization"], False)
        self.assertEqual(data["customization"]["version"], 1)
        self.assertEqual(len(data["operations"]), 1)
        self.assertEqual(data["arch"].count('name="x_name"'), 1)

    def test_resave_updates_existing_extension(self):
        first = self.service.save_customization(self.model_name, "form", [self._add_node()])
        second = self.service.save_customization(
            self.model_name,
            "form",
            [self._add_node('<field name="x_name" string="Nombre"/>')],
            customization_id=first["customization_id"],
        )
        self.assertEqual(second["extension_view_id"], first["extension_view_id"])
        self.assertEqual(second["version"], 2)
        extensions = self.env["ir.ui.view"].search(
            [
                ("model", "=", self.model_name),
                ("mode", "=", "extension"),
            ]
        )
        self.assertEqual(len(extensions), 1)

    def test_remove_node_uses_replace_position(self):
        operation = {
            "op_type": "remove_node",
            "target_xpath": "/form[1]/sheet[1]/group[1]/field[1]",
            "position": "inside",
        }
        preview = self.service.preview_operations(self.model_name, "form", [operation])
        self.assertIn('position="replace"', preview["arch"])
        result = self.service.save_customization(self.model_name, "form", [operation])
        combined = self.env[self.model_name].get_view(result["base_view_id"], "form")["arch"]
        self.assertNotIn('name="x_name"', combined)

    def test_set_attribute_operation(self):
        result = self.service.save_customization(
            self.model_name,
            "form",
            [
                {
                    "op_type": "set_attribute",
                    "target_xpath": "/form[1]/sheet[1]/group[1]/field[1]",
                    "position": "attributes",
                    "attributes": {"string": "Nombre personalizado"},
                }
            ],
        )
        combined = self.env[self.model_name].get_view(result["base_view_id"], "form")["arch"]
        self.assertIn('string="Nombre personalizado"', combined)

    def test_invalid_xpath_is_rejected(self):
        operation = self._add_node()
        operation["target_xpath"] = "//*["
        with self.assertRaises(ValidationError):
            self.service.preview_operations(self.model_name, "form", [operation])

    def test_forbidden_node_is_rejected(self):
        operation = self._add_node("<script>alert(1)</script>")
        with self.assertRaises(ValidationError):
            self.service.preview_operations(self.model_name, "form", [operation])

    def test_nested_unknown_field_is_rejected(self):
        operation = self._add_node('<group><field name="x_sr_missing"/></group>')
        with self.assertRaises(ValidationError):
            self.service.preview_operations(self.model_name, "form", [operation])

    def test_qweb_directive_is_rejected(self):
        operation = self._add_node('<field name="x_name" t-if="True"/>')
        with self.assertRaises(ValidationError):
            self.service.preview_operations(self.model_name, "form", [operation])

    def test_javascript_url_is_rejected(self):
        operation = self._add_node('<a href="javascript:alert(1)">Abrir</a>')
        with self.assertRaises(ValidationError):
            self.service.preview_operations(self.model_name, "form", [operation])

    def test_unknown_field_is_rejected(self):
        operation = self._add_node('<field name="x_sr_does_not_exist"/>')
        with self.assertRaises(ValidationError):
            self.service.preview_operations(self.model_name, "form", [operation])

    def test_forbidden_attribute_is_rejected(self):
        operation = self._add_node('<field name="x_name" onclick="alert(1)"/>')
        with self.assertRaises(ValidationError):
            self.service.preview_operations(self.model_name, "form", [operation])

    def test_forbidden_set_attribute_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.preview_operations(
                self.model_name,
                "form",
                [
                    {
                        "op_type": "set_attribute",
                        "target_xpath": "/form[1]/sheet[1]/group[1]/field[1]",
                        "position": "attributes",
                        "attributes": {"style": "color: red"},
                    }
                ],
            )

    def test_create_customization_rejects_generated_fields(self):
        model = self.env["ir.model"].search([("model", "=", self.model_name)], limit=1)
        with self.assertRaises(UserError):
            self.env["studio.customization"].with_user(self.designer).create(
                {
                    "name": "Intento",
                    "model_id": model.id,
                    "view_type": "form",
                    "extension_view_id": self.base_view_id,
                }
            )

    def test_context_cannot_bypass_protected_fields(self):
        model = self.env["ir.model"].search([("model", "=", self.model_name)], limit=1)
        values = {
            "name": "Intento",
            "model_id": model.id,
            "view_type": "form",
            "extension_view_id": self.base_view_id,
        }
        with self.assertRaises(UserError):
            self.env["studio.customization"].with_user(self.designer).with_context(
                studio_internal=True
            ).create(values)
        result = self.service.save_customization(self.model_name, "form", [self._add_node()])
        customization = self.env["studio.customization"].browse(result["customization_id"])
        with self.assertRaises(UserError):
            customization.with_user(self.designer).with_context(studio_internal=True).write(
                {"version": 99}
            )

    def test_unlink_does_not_delete_base_view(self):
        model = self.env["ir.model"].search([("model", "=", self.model_name)], limit=1)
        customization = (
            self.env["studio.customization"]
            .sudo()
            .create(
                {
                    "name": "Intento",
                    "model_id": model.id,
                    "view_type": "form",
                    "base_view_id": self.base_view_id,
                    "extension_view_id": self.base_view_id,
                }
            )
        )
        base_view = self.env["ir.ui.view"].browse(self.base_view_id)
        customization.unlink()
        self.assertTrue(base_view.exists())

    def test_legacy_base_view_key_is_visible(self):
        base_view = self.env["ir.ui.view"].browse(self.base_view_id)
        base_view.sudo().write({"key": f"atlas_odoo_studio.view_{self.model_name}_form"})
        self.env.registry.clear_cache()
        arch = self.env[self.model_name].get_view(self.base_view_id, "form")["arch"]
        self.assertIn('name="x_name"', arch)

    def test_legacy_extension_key_is_reused_and_migrated(self):
        result = self.service.save_customization(self.model_name, "form", [self._add_node()])
        extension = self.env["ir.ui.view"].browse(result["extension_view_id"])
        legacy_key = f"atlas_odoo_studio.{self.model_name}_form_{self.base_view_id}"
        extension.sudo().write({"key": legacy_key})
        self.env.registry.clear_cache()
        combined = self.env[self.model_name].get_view(self.base_view_id, "form")["arch"]
        self.assertEqual(combined.count('name="x_name"'), 2)
        self.service.save_customization(
            self.model_name,
            "form",
            [self._add_node('<field name="x_name" string="Legacy"/>')],
            customization_id=result["customization_id"],
        )
        expected_key = (
            f"atlas_odoo_studio.{self.env.company.id}.{self.model_name}_form_{self.base_view_id}"
        )
        self.assertEqual(extension.key, expected_key)

    def test_other_company_extension_is_not_visible(self):
        other_company = self.env["res.company"].create({"name": "Atlas Other"})
        key = f"atlas_odoo_studio.{other_company.id}.{self.model_name}_form_{self.base_view_id}"
        other_view = (
            self.env["ir.ui.view"]
            .sudo()
            .create(
                {
                    "name": "Otra compañía",
                    "model": self.model_name,
                    "type": "form",
                    "inherit_id": self.base_view_id,
                    "mode": "extension",
                    "priority": 99,
                    "key": key,
                    "arch": (
                        '<data><xpath expr="//field[@name=\'x_name\']" position="after">'
                        '<field name="x_name" string="Otra compañía"/></xpath></data>'
                    ),
                }
            )
        )
        arch = self.env[self.model_name].get_view(self.base_view_id, "form")["arch"]
        self.assertNotIn('string="Otra compañía"', arch)
        other_view.unlink()

    def test_rollback_deactivates_extension(self):
        result = self.service.save_customization(self.model_name, "form", [self._add_node()])
        extension = self.env["ir.ui.view"].browse(result["extension_view_id"])
        self.assertTrue(self.service.rollback_customization(result["customization_id"]))
        self.assertFalse(extension.active)
        customization = self.env["studio.customization"].browse(result["customization_id"])
        self.assertEqual(customization.state, "draft")
