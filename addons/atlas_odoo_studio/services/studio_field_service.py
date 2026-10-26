from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Final

from odoo import Command, api, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

FIELD_NAME_RE: Final = re.compile(r"^x_[a-z][a-z0-9_]{0,60}$")
RESERVED_NAMES: Final = frozenset(
    {
        "id",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "display_name",
    }
)
SUPPORTED_TYPES: Final = frozenset(
    {
        "char",
        "text",
        "html",
        "integer",
        "float",
        "monetary",
        "boolean",
        "date",
        "datetime",
        "selection",
        "many2one",
        "one2many",
        "many2many",
        "binary",
    }
)
RELATIONAL_TYPES: Final = frozenset({"many2one", "one2many", "many2many"})
SYSTEM_FIELDS: Final = frozenset({"x_name", "x_company_id"})


class StudioFieldService(models.AbstractModel):
    """Crea y valida campos manuales para Atlas-Odoo-Studio."""

    _name = "studio.field.service"
    _description = "Servicio de campos de Atlas-Odoo-Studio"

    @api.model
    def _check_designer(self) -> None:
        """Exige el grupo diseñador para operar sobre metadatos."""
        if not self.env.user.has_group("atlas_odoo_studio.group_studio_designer"):
            raise AccessError("No tiene permisos para administrar campos personalizados.")

    @api.model
    def _get_model(self, model_name: str) -> models.Model:
        """Devuelve el registro `ir.model` o lanza un error legible."""
        if not model_name or not isinstance(model_name, str):
            raise ValidationError("El modelo es obligatorio.")
        model = self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)
        if not model:
            raise ValidationError(f"El modelo {model_name!r} no existe.")
        return model

    @api.model
    def _validate_name(self, name: str) -> str:
        """Valida el nombre técnico de un campo manual."""
        if not isinstance(name, str):
            raise ValidationError("El nombre técnico debe ser texto.")
        name = name.strip()
        if name in SYSTEM_FIELDS:
            raise ValidationError(f"El campo {name!r} está reservado por Atlas-Odoo-Studio.")
        if name in RESERVED_NAMES or not FIELD_NAME_RE.match(name):
            raise ValidationError(
                "El nombre debe empezar por 'x_', usar minúsculas, números y guiones "
                "bajos, y no puede ser un campo reservado."
            )
        if len(name) > 63:
            raise ValidationError("El nombre técnico no puede superar 63 caracteres.")
        return name

    @api.model
    def _validate_type(self, ttype: str) -> str:
        """Valida el tipo de campo soportado en el MVP."""
        if ttype not in SUPPORTED_TYPES:
            raise ValidationError(
                f"Tipo de campo no soportado: {ttype!r}. "
                f"Tipos disponibles: {', '.join(sorted(SUPPORTED_TYPES))}."
            )
        return ttype

    @api.model
    def _validate_relation(self, relation: str) -> str:
        """Valida que el modelo relacionado exista."""
        if not relation or not self.env["ir.model"].sudo()._get_id(relation):
            raise ValidationError(f"El modelo relacionado {relation!r} no existe.")
        return relation

    @api.model
    def _validate_selection(self, selection: Any) -> list[dict[str, Any]]:
        """Normaliza y valida las opciones de un campo selection."""
        if not isinstance(selection, (list, tuple)) or not selection:
            raise ValidationError("Un campo de selección necesita al menos una opción.")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(selection):
            if isinstance(item, dict):
                value = str(item.get("value", "")).strip()
                label = str(item.get("label", value)).strip()
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                value, label = str(item[0]).strip(), str(item[1]).strip()
            else:
                raise ValidationError("Cada opción debe ser {value, label} o [value, label].")
            if not value or not label:
                raise ValidationError("Las opciones necesitan valor y etiqueta.")
            if value in seen:
                raise ValidationError(f"Valor de selección duplicado: {value!r}.")
            seen.add(value)
            normalized.append({"value": value, "label": label, "sequence": index * 10})
        return normalized

    @api.model
    def _build_values(
        self,
        model_name: str,
        name: str,
        label: str,
        ttype: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Construye los valores de `ir.model.fields` con una lista blanca."""
        model = self._get_model(model_name)
        if model.studio_company_id and model.studio_company_id != self.env.company:
            raise AccessError("El modelo pertenece a otra compañía.")
        name = self._validate_name(name)
        ttype = self._validate_type(ttype)
        if not label or not str(label).strip():
            raise ValidationError("La etiqueta del campo es obligatoria.")

        values: dict[str, Any] = {
            "model_id": model.id,
            "name": name,
            "field_description": str(label).strip(),
            "ttype": ttype,
            "state": "manual",
            "store": True,
            "required": bool(options.get("required")),
            "readonly": bool(options.get("readonly")),
            "index": bool(options.get("index")),
            "studio_company_id": self.env.company.id,
        }
        self._apply_optional_values(values, options)
        self._apply_relational_values(values, ttype, options)
        self._apply_scalar_values(values, model_name, ttype, options)
        return values

    @api.model
    def _apply_optional_values(self, values: dict[str, Any], options: dict[str, Any]) -> None:
        """Añade ayuda y dominio opcionales a los valores del campo."""
        help_text = options.get("help")
        if help_text:
            values["help"] = str(help_text)
        domain = options.get("domain")
        if domain:
            if not isinstance(domain, str):
                raise ValidationError("El dominio debe ser una cadena de texto.")
            if len(domain) > 5000:
                raise ValidationError("El dominio es demasiado largo.")
            try:
                parsed = safe_eval(domain, {"uid": self.env.uid})
            except (NameError, SyntaxError, TypeError, ValueError) as error:
                raise ValidationError("El dominio no es válido.") from error
            if not isinstance(parsed, (list, tuple)):
                raise ValidationError("El dominio debe ser una lista.")
            values["domain"] = domain

    @api.model
    def _apply_relational_values(
        self, values: dict[str, Any], ttype: str, options: dict[str, Any]
    ) -> None:
        """Completa los valores de los campos relacionales."""
        if ttype not in RELATIONAL_TYPES:
            return
        values["relation"] = self._validate_relation(options.get("relation", ""))
        if ttype == "many2one":
            on_delete = str(options.get("on_delete", "set null"))
            if on_delete not in {"set null", "restrict", "cascade"}:
                raise ValidationError(f"Política on_delete no válida: {on_delete!r}.")
            values["on_delete"] = on_delete
        elif ttype == "one2many":
            values["relation_field"] = self._validate_inverse_field(
                values["relation"], options.get("relation_field", "")
            )

    @api.model
    def _apply_scalar_values(
        self,
        values: dict[str, Any],
        model_name: str,
        ttype: str,
        options: dict[str, Any],
    ) -> None:
        """Completa los valores específicos de tipos no relacionales."""
        if ttype == "monetary":
            values["currency_field"] = self._validate_currency_field(model_name, options)
        elif ttype == "html":
            values.update(
                {
                    "sanitize": True,
                    "sanitize_tags": True,
                    "sanitize_attributes": True,
                    "sanitize_style": False,
                    "strip_style": False,
                    "strip_classes": False,
                }
            )
        elif ttype == "selection":
            values["selection_ids"] = [
                Command.create(
                    {
                        "value": item["value"],
                        "name": item["label"],
                        "sequence": item["sequence"],
                    }
                )
                for item in self._validate_selection(options.get("selection"))
            ]

    @api.model
    def _validate_inverse_field(self, relation: str, relation_field: str) -> str:
        """Valida el campo many2one inverso de un one2many."""
        relation_field = str(relation_field).strip()
        if not relation_field:
            raise ValidationError("Un one2many necesita el campo many2one inverso.")
        inverse = (
            self.env["ir.model.fields"]
            .sudo()
            .search(
                [
                    ("model", "=", relation),
                    ("name", "=", relation_field),
                    ("ttype", "=", "many2one"),
                ],
                limit=1,
            )
        )
        if not inverse:
            raise ValidationError(
                f"El campo inverso {relation_field!r} no existe como many2one en {relation!r}."
            )
        return relation_field

    @api.model
    def _validate_currency_field(self, model_name: str, options: dict[str, Any]) -> str:
        """Valida el campo de moneda de un campo monetary."""
        currency_field = str(options.get("currency_field", "currency_id")).strip()
        if currency_field not in self.env[model_name].sudo()._fields:
            raise ValidationError(
                f"El campo de moneda {currency_field!r} no existe en {model_name!r}."
            )
        return currency_field

    @api.model
    def create_field(
        self,
        model_name: str,
        name: str,
        label: str,
        ttype: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Crea un campo manual y devuelve su representación serializable."""
        self._check_designer()
        values = self._build_values(model_name, name, label, ttype, **options)
        if (
            self.env["ir.model.fields"]
            .sudo()
            .search_count([("model", "=", model_name), ("name", "=", values["name"])])
        ):
            raise ValidationError(f"El campo {values['name']!r} ya existe.")
        field = self.env["ir.model.fields"].sudo().create(values)
        self.env["studio.audit.log"].sudo().log_event(
            action="create_field",
            model_name=model_name,
            res_id=field.id,
            after_hash=self._field_hash(field),
            details={
                "name": field.name,
                "ttype": field.ttype,
                "relation": field.relation or "",
            },
        )
        return self._field_info(field)

    @api.model
    def delete_field(self, field_id: int) -> bool:
        """Elimina un campo manual creado por el editor."""
        self._check_designer()
        field = self.env["ir.model.fields"].sudo().browse(field_id)
        if not field.exists():
            raise ValidationError("El campo no existe.")
        if field.state != "manual" or not field.name.startswith("x_"):
            raise UserError("Solo se pueden eliminar campos manuales con prefijo x_.")
        if field.name in SYSTEM_FIELDS:
            raise UserError(f"El campo {field.name!r} está reservado por Atlas-Odoo-Studio.")
        if field.studio_company_id != self.env.company:
            raise UserError("El campo no pertenece a esta compañía.")
        model_name = field.model
        field_name = field.name
        before_hash = self._field_hash(field)
        field.unlink()
        self.env["studio.audit.log"].sudo().log_event(
            action="delete_field",
            model_name=model_name,
            res_id=field_id,
            before_hash=before_hash,
            details={"name": field_name},
        )
        return True

    @api.model
    def get_fields(self, model_name: str) -> list[dict[str, Any]]:
        """Devuelve los campos visibles del modelo para la paleta del editor."""
        self._check_designer()
        self._get_model(model_name)
        field_info = (
            self.env[model_name]
            .sudo()
            .fields_get(attributes=["string", "type", "relation", "required", "readonly", "store"])
        )
        manual = {
            field.name: field
            for field in self.env["ir.model.fields"]
            .sudo()
            .search([("model", "=", model_name), ("state", "=", "manual")])
        }
        result = []
        for name, info in sorted(field_info.items()):
            if name in RESERVED_NAMES:
                continue
            manual_field = manual.get(name)
            result.append(
                {
                    "id": manual_field.id if manual_field else False,
                    "name": name,
                    "string": info.get("string", name),
                    "ttype": info.get("type", "char"),
                    "relation": info.get("relation", ""),
                    "required": bool(info.get("required")),
                    "readonly": bool(info.get("readonly")),
                    "store": bool(info.get("store", True)),
                    "manual": bool(manual_field),
                }
            )
        return result

    @api.model
    def _field_info(self, field: models.Model) -> dict[str, Any]:
        """Serializa un campo para el cliente."""
        return {
            "id": field.id,
            "name": field.name,
            "string": field.field_description,
            "ttype": field.ttype,
            "relation": field.relation or "",
            "required": field.required,
            "readonly": field.readonly,
            "manual": field.state == "manual",
        }

    @api.model
    def _field_hash(self, field: models.Model) -> str:
        """Calcula una huella estable de la definición del campo."""
        payload = {
            "model": field.model,
            "name": field.name,
            "ttype": field.ttype,
            "relation": field.relation or "",
            "required": field.required,
            "readonly": field.readonly,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
