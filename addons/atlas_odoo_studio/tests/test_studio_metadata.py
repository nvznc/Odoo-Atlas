from __future__ import annotations

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install", "atlas_studio")
class TestStudioMetadata(TransactionCase):
    """Pruebas del servicio de metadatos de Atlas-Odoo-Studio."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = new_test_user(
            cls.env,
            login="atlas_designer",
            groups="base.group_user,atlas_odoo_studio.group_studio_designer",
        )
        cls.simple_user = new_test_user(
            cls.env,
            login="atlas_simple_user",
            groups="base.group_user",
        )
        cls.service = cls.env["studio.metadata.service"].with_user(cls.designer)

    def _create_model(self, label: str = "Atlas Test App") -> dict:
        return self.service.create_model(label)

    def test_bootstrap_requires_designer(self):
        with self.assertRaises(AccessError):
            self.env["studio.metadata.service"].with_user(self.simple_user).get_bootstrap()

    def test_create_field_requires_designer(self):
        result = self._create_model()
        with self.assertRaises(AccessError):
            self.env["studio.metadata.service"].with_user(self.simple_user).create_field(
                result["model"], "x_sr_note", "Nota", "char"
            )

    def test_create_model_creates_expected_artifacts(self):
        result = self._create_model("Atlas Facturas")
        model = self.env["ir.model"].search([("model", "=", result["model"])])
        self.assertTrue(model, "El modelo manual debe existir.")
        self.assertEqual(model.state, "manual")
        self.assertEqual(model.studio_company_id, self.env.company)
        self.assertTrue(result["model"].startswith("x_sr_"))
        self.assertEqual(result["label"], "Atlas Facturas")

        name_field = self.env["ir.model.fields"].search(
            [("model", "=", result["model"]), ("name", "=", "x_name")]
        )
        self.assertTrue(name_field, "El campo x_name debe existir.")
        self.assertTrue(name_field.required)

        form_view = self.env["ir.ui.view"].browse(result["form_view_id"])
        list_view = self.env["ir.ui.view"].browse(result["list_view_id"])
        self.assertEqual(form_view.type, "form")
        self.assertEqual(list_view.type, "list")
        self.assertIn('name="x_name"', form_view.arch)
        self.assertIn('name="x_name"', list_view.arch)

        action = self.env["ir.actions.act_window"].browse(result["action_id"])
        menu = self.env["ir.ui.menu"].browse(result["menu_id"])
        self.assertEqual(action.res_model, result["model"])
        self.assertEqual(menu.action, action)

        privileges = self.env["ir.model.access"].search([("model_id", "=", model.id)])
        self.assertEqual(len(privileges), 2)
        self.assertIn(
            self.env.ref("atlas_odoo_studio.group_studio_designer"),
            privileges.group_id,
        )

        audit = self.env["studio.audit.log"].search(
            [("action", "=", "create_model"), ("model_name", "=", result["model"])]
        )
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit.company_id, self.env.company)

    def test_generated_model_data_is_company_scoped(self):
        other_company = self.env["res.company"].create({"name": "Atlas Data Other"})
        self.designer.sudo().write({"company_ids": [(4, other_company.id)]})
        result = self._create_model("Atlas Data")
        model = self.env[result["model"]].with_user(self.designer)
        record_main = model.with_company(self.env.company).create({"x_name": "Main"})
        record_other = model.with_company(other_company).create({"x_name": "Other"})
        self.assertEqual(record_main.x_company_id, self.env.company)
        self.assertEqual(record_other.x_company_id, other_company)
        self.assertEqual(
            model.with_company(self.env.company).search([]),
            record_main,
        )
        self.assertEqual(model.with_company(other_company).search([]), record_other)

    def test_audit_log_requires_designer(self):
        with self.assertRaises(AccessError):
            self.env["studio.audit.log"].with_user(self.simple_user).log_event(
                "create_model",
                model_name="x_sr_forbidden",
            )

    def test_audit_log_is_company_scoped(self):
        other_company = self.env["res.company"].create({"name": "Atlas Other"})
        audit_model = self.env["studio.audit.log"]
        main_log = audit_model.with_user(self.designer).log_event(
            "create_model",
            model_name="x_sr_audit_main",
        )
        other_log = (
            audit_model.with_company(other_company)
            .sudo()
            .log_event("create_model", model_name="x_sr_audit_other")
        )
        visible = audit_model.with_user(self.designer).search(
            [("id", "in", [main_log.id, other_log.id])]
        )
        self.assertEqual(visible, main_log)
        self.assertEqual(main_log.company_id, self.env.company)
        self.assertEqual(other_log.company_id, other_company)

    def test_create_field_returns_manual_field(self):
        result = self._create_model()
        field = self.service.create_field(
            result["model"], "x_sr_note", "Nota interna", "char", required=True
        )
        self.assertEqual(field["name"], "x_sr_note")
        self.assertTrue(field["manual"])
        record = self.env["ir.model.fields"].browse(field["id"])
        self.assertEqual(record.state, "manual")
        self.assertEqual(record.field_description, "Nota interna")
        self.assertEqual(record.studio_company_id, self.env.company)
        self.assertTrue(record.required)

    def test_create_selection_field(self):
        result = self._create_model()
        field = self.service.create_field(
            result["model"],
            "x_sr_state",
            "Estado",
            "selection",
            selection=[("draft", "Borrador"), ("done", "Hecho")],
        )
        record = self.env["ir.model.fields"].browse(field["id"])
        self.assertEqual(record.ttype, "selection")
        self.assertEqual(len(record.selection_ids), 2)

    def test_invalid_on_delete_is_rejected(self):
        result = self._create_model()
        with self.assertRaises(ValidationError):
            self.service.create_field(
                result["model"],
                "x_sr_partner",
                "Partner",
                "many2one",
                relation="res.partner",
                on_delete="drop table",
            )

    def test_invalid_domain_is_rejected(self):
        result = self._create_model()
        with self.assertRaises(ValidationError):
            self.service.create_field(
                result["model"],
                "x_sr_partner",
                "Partner",
                "many2one",
                relation="res.partner",
                domain="not a domain",
            )

    def test_valid_domain_is_accepted(self):
        result = self._create_model()
        field = self.service.create_field(
            result["model"],
            "x_sr_partner",
            "Partner",
            "many2one",
            relation="res.partner",
            domain='[("active", "=", True)]',
        )
        record = self.env["ir.model.fields"].browse(field["id"])
        self.assertEqual(record.domain, '[("active", "=", True)]')

    def test_create_field_on_other_company_model_is_rejected(self):
        result = self._create_model()
        other_company = self.env["res.company"].create({"name": "Atlas Other Fields"})
        with self.assertRaises(AccessError):
            self.env["studio.field.service"].with_user(self.designer).with_company(
                other_company
            ).create_field(result["model"], "x_sr_note", "Nota", "char")

    def test_delete_field_from_other_company_is_rejected(self):
        result = self._create_model()
        field = self.service.create_field(result["model"], "x_sr_note", "Nota", "char")
        other_company = self.env["res.company"].create({"name": "Atlas Other Fields"})
        with self.assertRaises(UserError):
            self.env["studio.field.service"].with_user(self.designer).with_company(
                other_company
            ).delete_field(field["id"])

    def test_delete_model_from_other_company_is_rejected(self):
        result = self._create_model()
        other_company = self.env["res.company"].create({"name": "Atlas Other Models"})
        with self.assertRaises(UserError):
            self.env["studio.metadata.service"].with_user(self.designer).with_company(
                other_company
            ).delete_model(result["model"])

    def test_invalid_field_name_is_rejected(self):
        result = self._create_model()
        with self.assertRaises(ValidationError):
            self.service.create_field(result["model"], "note", "Nota", "char")
        with self.assertRaises(ValidationError):
            self.service.create_field(result["model"], "x_sr_bad", "Nota", "unknown")

    def test_duplicate_field_name_is_rejected(self):
        result = self._create_model()
        self.service.create_field(result["model"], "x_sr_note", "Nota", "char")
        with self.assertRaises(ValidationError):
            self.service.create_field(result["model"], "x_sr_note", "Otra", "char")

    def test_delete_field_only_manual(self):
        result = self._create_model()
        field = self.service.create_field(result["model"], "x_sr_note", "Nota", "char")
        self.assertTrue(self.service.delete_field(field["id"]))
        self.assertFalse(self.env["ir.model.fields"].browse(field["id"]).exists())
        with self.assertRaises(ValidationError):
            self.service.delete_field(99999999)
        with self.assertRaises(UserError):
            self.service.delete_field(1)

    def test_system_fields_cannot_be_deleted_or_recreated(self):
        result = self._create_model()
        for field_name in ("x_name", "x_company_id"):
            field = self.env["ir.model.fields"].search(
                [("model", "=", result["model"]), ("name", "=", field_name)],
                limit=1,
            )
            with self.assertRaises(UserError):
                self.service.delete_field(field.id)
            with self.assertRaises(ValidationError):
                self.service.create_field(result["model"], field_name, "Reservado", "char")

    def test_delete_model_only_manual(self):
        partner = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        with self.assertRaises(UserError):
            self.service.delete_model(partner.model)
        result = self._create_model("Atlas Temporal")
        self.assertTrue(self.service.delete_model(result["model"]))
        self.assertFalse(self.env["ir.model"].search([("model", "=", result["model"])]))

    def test_get_fields_marks_manual_fields(self):
        result = self._create_model()
        self.service.create_field(result["model"], "x_sr_note", "Nota", "char")
        fields = self.service.get_fields(result["model"])
        by_name = {field["name"]: field for field in fields}
        self.assertIn("x_name", by_name)
        self.assertTrue(by_name["x_sr_note"]["manual"])
        self.assertIsInstance(by_name["x_sr_note"]["id"], int)
        self.assertNotIn("id", by_name)
        self.assertTrue(all("id" in field for field in fields))
