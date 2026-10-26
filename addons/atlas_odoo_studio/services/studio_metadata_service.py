from __future__ import annotations

import re
import unicodedata
from typing import Any, Final

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MODEL_NAME_RE: Final = re.compile(r"^x_[a-z][a-z0-9_]{1,54}$")
DEFAULT_NAME_FIELD: Final = "x_name"
DEFAULT_NAME_LABEL: Final = "Nombre"
DEFAULT_COMPANY_FIELD: Final = "x_company_id"
DEFAULT_COMPANY_LABEL: Final = "Compañía"
DEFAULT_FORM_ARCH: Final = (
    '<form><sheet><group><field name="x_name"/>'
    f'<field name="{DEFAULT_COMPANY_FIELD}" readonly="1"/></group></sheet></form>'
)
DEFAULT_LIST_ARCH: Final = (
    f'<list><field name="x_name"/><field name="{DEFAULT_COMPANY_FIELD}"/></list>'
)


class StudioMetadataService(models.AbstractModel):
    """Fachada transaccional para todas las operaciones del editor."""

    _name = "studio.metadata.service"
    _description = "Servicio de metadatos de Atlas-Odoo-Studio"

    @api.model
    def _check_designer(self) -> None:
        """Exige el grupo diseñador."""
        if not self.env.user.has_group("atlas_odoo_studio.group_studio_designer"):
            raise AccessError("No tiene permisos para administrar Atlas-Odoo-Studio.")

    @api.model
    def _slugify(self, value: str) -> str:
        """Convierte una etiqueta en un identificador técnico estable."""
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
        return slug or "app"

    @api.model
    def _validate_model_name(self, model_name: str) -> str:
        """Valida el nombre de un modelo manual."""
        if not isinstance(model_name, str):
            raise ValidationError("El nombre del modelo debe ser texto.")
        model_name = model_name.strip()
        if not MODEL_NAME_RE.match(model_name):
            raise ValidationError(
                "El modelo debe empezar por 'x_', usar minúsculas, números y guiones "
                "bajos, y tener entre 3 y 56 caracteres."
            )
        if self.env["ir.model"].sudo().search_count([("model", "=", model_name)]):
            raise ValidationError(f"El modelo {model_name!r} ya existe.")
        return model_name

    @api.model
    def _create_xmlid(self, name: str, model: str, res_id: int) -> models.Model:
        """Crea o recupera un XMLID estable para un artefacto del editor."""
        xmlid = (
            self.env["ir.model.data"]
            .sudo()
            .search(
                [("module", "=", "atlas_odoo_studio"), ("name", "=", name)],
                limit=1,
            )
        )
        if xmlid:
            return xmlid
        return (
            self.env["ir.model.data"]
            .sudo()
            .create(
                {
                    "module": "atlas_odoo_studio",
                    "name": name,
                    "model": model,
                    "res_id": res_id,
                    "noupdate": True,
                }
            )
        )

    @api.model
    def get_bootstrap(self) -> dict[str, Any]:
        """Datos iniciales para el cliente OWL."""
        self._check_designer()
        return {
            "company": {"id": self.env.company.id, "name": self.env.company.name},
            "user": {"id": self.env.user.id, "name": self.env.user.name},
            "models": self.env["studio.view.service"].get_models(),
            "view_types": [
                {"value": "form", "label": "Formulario"},
                {"value": "list", "label": "Lista"},
                {"value": "kanban", "label": "Kanban"},
                {"value": "search", "label": "Búsqueda"},
            ],
        }

    @api.model
    def get_editor_data(
        self,
        model_name: str,
        view_type: str,
        base_view_id: int | None = None,
    ) -> dict[str, Any]:
        """Delegación al servicio de vistas."""
        self._check_designer()
        return self.env["studio.view.service"].get_editor_data(model_name, view_type, base_view_id)

    @api.model
    def preview_operations(
        self,
        model_name: str,
        view_type: str,
        operations: Any,
        base_view_id: int | None = None,
    ) -> dict[str, Any]:
        """Delegación al servicio de vistas."""
        self._check_designer()
        return self.env["studio.view.service"].preview_operations(
            model_name, view_type, operations, base_view_id
        )

    @api.model
    def save_customization(
        self,
        model_name: str,
        view_type: str,
        operations: Any,
        *,
        base_view_id: int | None = None,
        customization_id: int | None = None,
        name: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        """Delegación al servicio de vistas."""
        self._check_designer()
        return self.env["studio.view.service"].save_customization(
            model_name,
            view_type,
            operations,
            base_view_id=base_view_id,
            customization_id=customization_id,
            name=name,
            description=description,
        )

    @api.model
    def create_field(
        self,
        model_name: str,
        name: str,
        label: str,
        ttype: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Delegación al servicio de campos."""
        self._check_designer()
        return self.env["studio.field.service"].create_field(
            model_name, name, label, ttype, **options
        )

    @api.model
    def delete_field(self, field_id: int) -> bool:
        """Delegación al servicio de campos."""
        self._check_designer()
        return self.env["studio.field.service"].delete_field(field_id)

    @api.model
    def get_fields(self, model_name: str) -> list[dict[str, Any]]:
        """Delegación al servicio de campos."""
        self._check_designer()
        return self.env["studio.field.service"].get_fields(model_name)

    @api.model
    def get_views(self, model_name: str, view_type: str) -> list[dict[str, Any]]:
        """Delegación al servicio de vistas."""
        self._check_designer()
        return self.env["studio.view.service"].get_views(model_name, view_type)

    @api.model
    def _create_company_field(self, model: models.Model) -> None:
        """Añade el campo de compañía a un modelo generado."""
        fields_model = self.env["ir.model.fields"].sudo()
        if fields_model.search(
            [("model", "=", model.model), ("name", "=", DEFAULT_COMPANY_FIELD)],
            limit=1,
        ):
            return
        fields_model.create(
            {
                "model_id": model.id,
                "name": DEFAULT_COMPANY_FIELD,
                "field_description": DEFAULT_COMPANY_LABEL,
                "ttype": "many2one",
                "relation": "res.company",
                "state": "manual",
                "store": True,
                "required": True,
                "index": True,
                "on_delete": "restrict",
                "studio_company_id": self.env.company.id,
            }
        )

    @api.model
    def _create_company_rule(self, model: models.Model) -> None:
        """Restringe los registros del modelo generado a la compañía actual."""
        rule_model = self.env["ir.rule"].sudo()
        rule_name = f"Atlas Studio: {model.model} por compañía"
        if rule_model.search([("model_id", "=", model.id), ("name", "=", rule_name)], limit=1):
            return
        rule_model.create(
            {
                "name": rule_name,
                "model_id": model.id,
                "domain_force": f"[('{DEFAULT_COMPANY_FIELD}', 'in', company_ids)]",
            }
        )

    @api.model
    def _ensure_company_defaults(self, model: models.Model, companies: models.Model) -> None:
        """Define la compañía por defecto en cada compañía existente."""
        if DEFAULT_COMPANY_FIELD not in self.env[model.model]._fields:
            return
        default_model = self.env["ir.default"].sudo()
        for company in companies:
            default_model.set(
                model.model,
                DEFAULT_COMPANY_FIELD,
                company.id,
                company_id=company.id,
            )

    @api.model
    def _add_company_defaults(self, companies: models.Model) -> None:
        """Añade defaults de compañía a los modelos generados existentes."""
        models_to_update = (
            self.env["ir.model"]
            .sudo()
            .search([("state", "=", "manual"), ("model", "like", "x_sr_%")])
        )
        for model in models_to_update:
            self._ensure_company_defaults(model, companies)

    @api.model
    def create_model(
        self,
        label: str,
        *,
        model_name: str = "",
        description: str = "",
        menu_name: str = "",
    ) -> dict[str, Any]:
        """Crea un modelo manual con vista form/list, acción, menú y ACL."""
        self._check_designer()
        label = str(label or "").strip()
        if not label:
            raise ValidationError("La etiqueta del modelo es obligatoria.")
        technical = self._validate_model_name(
            model_name.strip() if model_name else f"x_sr_{self._slugify(label)}"
        )
        group_designer = self.env.ref("atlas_odoo_studio.group_studio_designer")
        group_user = self.env.ref("base.group_user")

        try:
            with self.env.cr.savepoint():
                model = (
                    self.env["ir.model"]
                    .sudo()
                    .create(
                        {
                            "model": technical,
                            "name": label,
                            "studio_company_id": self.env.company.id,
                        }
                    )
                )
                name_field = (
                    self.env["ir.model.fields"]
                    .sudo()
                    .search(
                        [("model", "=", technical), ("name", "=", DEFAULT_NAME_FIELD)],
                        limit=1,
                    )
                )
                if name_field:
                    name_field.write(
                        {
                            "field_description": DEFAULT_NAME_LABEL,
                            "required": True,
                            "index": True,
                            "studio_company_id": self.env.company.id,
                        }
                    )
                else:
                    name_field = (
                        self.env["ir.model.fields"]
                        .sudo()
                        .create(
                            {
                                "model_id": model.id,
                                "name": DEFAULT_NAME_FIELD,
                                "field_description": DEFAULT_NAME_LABEL,
                                "ttype": "char",
                                "state": "manual",
                                "store": True,
                                "required": True,
                                "index": True,
                                "studio_company_id": self.env.company.id,
                            }
                        )
                    )
                self._create_company_field(model)
                self._create_company_rule(model)
                self._ensure_company_defaults(model, self.env["res.company"].sudo().search([]))
                form_view = (
                    self.env["ir.ui.view"]
                    .sudo()
                    .create(
                        {
                            "name": f"{label} / Formulario",
                            "model": technical,
                            "type": "form",
                            "mode": "primary",
                            "priority": 16,
                            "arch": DEFAULT_FORM_ARCH,
                            "key": f"atlas_odoo_studio.{self.env.company.id}.view_{technical}_form",
                        }
                    )
                )
                list_view = (
                    self.env["ir.ui.view"]
                    .sudo()
                    .create(
                        {
                            "name": f"{label} / Lista",
                            "model": technical,
                            "type": "list",
                            "mode": "primary",
                            "priority": 16,
                            "arch": DEFAULT_LIST_ARCH,
                            "key": f"atlas_odoo_studio.{self.env.company.id}.view_{technical}_list",
                        }
                    )
                )
                action = (
                    self.env["ir.actions.act_window"]
                    .sudo()
                    .create(
                        {
                            "name": menu_name or label,
                            "res_model": technical,
                            "view_mode": "list,form",
                            "view_id": form_view.id,
                            "target": "current",
                        }
                    )
                )
                menu = (
                    self.env["ir.ui.menu"]
                    .sudo()
                    .create(
                        {
                            "name": menu_name or label,
                            "action": f"ir.actions.act_window,{action.id}",
                            "sequence": 90,
                        }
                    )
                )
                self.env["ir.model.access"].sudo().create(
                    [
                        {
                            "name": f"{label} / Diseñador",
                            "model_id": model.id,
                            "group_id": group_designer.id,
                            "perm_read": True,
                            "perm_write": True,
                            "perm_create": True,
                            "perm_unlink": True,
                        },
                        {
                            "name": f"{label} / Lectura",
                            "model_id": model.id,
                            "group_id": group_user.id,
                            "perm_read": True,
                            "perm_write": False,
                            "perm_create": False,
                            "perm_unlink": False,
                        },
                    ]
                )
                self._create_xmlid(f"model_{technical}", "ir.model", model.id)
                self._create_xmlid(f"view_{technical}_form", "ir.ui.view", form_view.id)
                self._create_xmlid(f"view_{technical}_list", "ir.ui.view", list_view.id)
                self._create_xmlid(f"action_{technical}", "ir.actions.act_window", action.id)
                self._create_xmlid(f"menu_{technical}", "ir.ui.menu", menu.id)
                self.env["studio.audit.log"].sudo().log_event(
                    action="create_model",
                    model_name=technical,
                    res_id=model.id,
                    details={
                        "label": label,
                        "description": description,
                        "field_id": name_field.id,
                        "form_view_id": form_view.id,
                        "list_view_id": list_view.id,
                        "action_id": action.id,
                        "menu_id": menu.id,
                    },
                )
        except (UserError, ValidationError, ValueError):
            self.env.registry.clear_cache()
            raise

        return {
            "model": technical,
            "label": label,
            "field": name_field,
            "form_view_id": form_view.id,
            "list_view_id": list_view.id,
            "action_id": action.id,
            "menu_id": menu.id,
        }

    @api.model
    def _delete_model_artifacts(self, model: models.Model) -> None:
        """Elimina vistas, acciones, menús y XMLIDs antes del modelo."""
        model_name = model.model
        xmlids = (
            self.env["ir.model.data"]
            .sudo()
            .search(
                [
                    ("module", "=", "atlas_odoo_studio"),
                    (
                        "name",
                        "in",
                        [
                            f"model_{model_name}",
                            f"view_{model_name}_form",
                            f"view_{model_name}_list",
                            f"action_{model_name}",
                            f"menu_{model_name}",
                        ],
                    ),
                ]
            )
        )
        self.env["studio.customization"].sudo().search([("model_id", "=", model.id)]).unlink()
        views = self.env["ir.ui.view"].sudo().search([("model", "=", model_name)])
        extensions = views.filtered(lambda view: view.mode == "extension")
        primaries = views - extensions
        actions = self.env["ir.actions.act_window"].sudo().search([("res_model", "=", model_name)])
        action_refs = [f"ir.actions.act_window,{action.id}" for action in actions]
        menus = (
            self.env["ir.ui.menu"].sudo().search([("action", "in", action_refs)])
            if action_refs
            else self.env["ir.ui.menu"].sudo().browse()
        )
        menus.unlink()
        actions.unlink()
        extensions.unlink()
        primaries.unlink()
        xmlids.unlink()

    @api.model
    def delete_model(self, model_name: str) -> bool:
        """Elimina un modelo manual creado desde el editor."""
        self._check_designer()
        model = self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)
        if not model:
            raise ValidationError("El modelo no existe.")
        if model.state != "manual" or not model.model.startswith("x_"):
            raise UserError("Solo se pueden eliminar modelos manuales con prefijo x_.")
        if model.studio_company_id != self.env.company:
            raise UserError("El modelo no pertenece a esta compañía.")
        label = model.name
        self._delete_model_artifacts(model)
        model.unlink()
        self.env["studio.audit.log"].sudo().log_event(
            action="delete_model",
            model_name=model_name,
            details={"deleted_model": model_name, "label": label},
        )
        return True

    @api.model
    def rollback_customization(self, customization_id: int) -> bool:
        """Delegación al servicio de vistas."""
        self._check_designer()
        return self.env["studio.view.service"].rollback_customization(customization_id)

    @api.model
    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Devuelve los últimos eventos de auditoría para el editor."""
        self._check_designer()
        records = self.env["studio.audit.log"].search(
            [], order="timestamp desc, id desc", limit=min(max(limit, 1), 500)
        )
        return [
            {
                "id": record.id,
                "timestamp": fields.Datetime.to_string(record.timestamp),
                "user": record.user_id.name,
                "action": record.action,
                "model": record.model_name,
                "res_id": record.res_id,
                "details": record.details or {},
            }
            for record in records
        ]
