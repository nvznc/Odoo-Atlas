from __future__ import annotations

import hashlib
import json
from typing import Any, Final
from urllib.parse import urlsplit

from lxml import etree
from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

VIEW_TYPES: Final = frozenset({"form", "list", "kanban", "search"})
POSITIONS: Final = frozenset({"inside", "after", "before", "replace", "attributes"})
ALLOWED_TAGS: Final = frozenset(
    {
        "a",
        "b",
        "br",
        "button",
        "control",
        "data",
        "div",
        "field",
        "footer",
        "form",
        "group",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "i",
        "img",
        "kanban",
        "label",
        "list",
        "newline",
        "notebook",
        "page",
        "p",
        "search",
        "separator",
        "sheet",
        "span",
        "strong",
        "table",
        "tbody",
        "td",
        "t",
        "th",
        "thead",
        "tr",
        "widget",
    }
)
FORBIDDEN_TAGS: Final = frozenset(
    {"base", "embed", "iframe", "link", "meta", "object", "script", "style", "svg"}
)
FORBIDDEN_ATTRS: Final = frozenset({"style", "srcdoc", "formaction", "t-raw", "t-call", "t-js"})
ALLOWED_URL_SCHEMES: Final = frozenset({"http", "https", "mailto", "tel"})
ALLOWED_SET_ATTRS: Final = frozenset(
    {
        "class",
        "col",
        "colspan",
        "context",
        "create",
        "decoration-danger",
        "decoration-info",
        "decoration-muted",
        "decoration-primary",
        "decoration-success",
        "decoration-warning",
        "delete",
        "domain",
        "duplicate",
        "edit",
        "filename",
        "groups",
        "help",
        "invisible",
        "limit",
        "mode",
        "nolabel",
        "optional",
        "options",
        "placeholder",
        "readonly",
        "required",
        "string",
        "sum",
        "view_mode",
        "widget",
        "width",
    }
)
MAX_XPATH_LENGTH: Final = 2000
MAX_NODE_LENGTH: Final = 20000
PRIORITY: Final = 99
XML_PARSER: Final = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    remove_comments=True,
)


class StudioViewService(models.AbstractModel):
    """Compila operaciones del editor a vistas heredadas de Odoo."""

    _name = "studio.view.service"
    _description = "Servicio de vistas de Atlas-Odoo-Studio"

    @api.model
    def _check_designer(self) -> None:
        """Exige el grupo diseñador para operar sobre vistas."""
        if not self.env.user.has_group("atlas_odoo_studio.group_studio_designer"):
            raise AccessError("No tiene permisos para administrar vistas.")

    @api.model
    def _check_view_type(self, view_type: str) -> str:
        """Valida el tipo de vista soportado por el MVP."""
        if view_type not in VIEW_TYPES:
            raise ValidationError(f"Tipo de vista no soportado: {view_type!r}.")
        return view_type

    @api.model
    def _get_model(self, model_name: str) -> models.Model:
        """Devuelve el modelo o lanza un error legible."""
        model = self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)
        if not model:
            raise ValidationError(f"El modelo {model_name!r} no existe.")
        return model

    @api.model
    def _resolve_base_view(
        self,
        model_name: str,
        view_type: str,
        base_view_id: int | None = None,
    ) -> models.Model:
        """Resuelve la vista primaria sobre la que se aplicará la extensión."""
        view = self.env["ir.ui.view"].sudo().browse()
        if base_view_id:
            try:
                view = self.env["ir.ui.view"].sudo().browse(int(base_view_id))
            except (TypeError, ValueError) as error:
                raise ValidationError("La vista base no es válida.") from error
        else:
            result = self.env[model_name].sudo().get_view(False, view_type)
            if not result.get("id"):
                raise UserError(f"No existe una vista {view_type} almacenada para {model_name!r}.")
            view = self.env["ir.ui.view"].sudo().browse(result["id"])
        if not view.exists():
            raise ValidationError("La vista base no existe.")
        while view.mode == "extension" and view.inherit_id:
            view = view.inherit_id
        if view.model != model_name:
            raise ValidationError("La vista base pertenece a otro modelo.")
        if view.type != view_type:
            raise ValidationError("La vista base no es del tipo solicitado.")
        return view

    @api.model
    def _validate_xpath(self, xpath: Any) -> str:
        """Valida sintaxis y longitud de un XPath."""
        if not isinstance(xpath, str) or not xpath.strip():
            raise ValidationError("Cada operación necesita un XPath.")
        xpath = xpath.strip()
        if len(xpath) > MAX_XPATH_LENGTH:
            raise ValidationError("El XPath es demasiado largo.")
        try:
            etree.XPath(xpath)
        except (etree.XPathSyntaxError, etree.XPathEvalError) as error:
            raise ValidationError(f"XPath inválido: {error}") from error
        return xpath

    @api.model
    def _validate_attributes(self, element: etree._Element) -> None:
        """Rechaza etiquetas y atributos peligrosos en el XML del editor."""
        tag = str(element.tag)
        if tag in FORBIDDEN_TAGS or tag not in ALLOWED_TAGS:
            raise ValidationError(f"Etiqueta no permitida: {tag!r}.")
        for key, value in element.attrib.items():
            lowered = key.lower()
            if lowered in FORBIDDEN_ATTRS or lowered.startswith("on"):
                raise ValidationError(f"Atributo no permitido: {key!r}.")
            if lowered.startswith("t-"):
                raise ValidationError(f"Directiva QWeb no permitida: {key!r}.")
            local_name = lowered.rsplit("}", 1)[-1].rsplit(":", 1)[-1]
            if local_name in {"href", "src"}:
                self._validate_url(value)
        for child in element:
            self._validate_attributes(child)

    @api.model
    def _validate_url(self, value: Any) -> None:
        """Permite solo esquemas de URL seguros en href/src."""
        raw = str(value or "").strip()
        compact = "".join(char for char in raw if ord(char) > 32).lower()
        try:
            parsed = urlsplit(compact)
        except ValueError as error:
            raise ValidationError("URL no permitida.") from error
        if parsed.scheme and parsed.scheme not in ALLOWED_URL_SCHEMES:
            raise ValidationError("URL no permitida.")

    @api.model
    def _validate_node_xml(self, node_xml: Any, model_name: str) -> str:
        """Normaliza y valida el XML de un nodo añadido."""
        if not isinstance(node_xml, str) or not node_xml.strip():
            raise ValidationError("Añadir un nodo requiere node_xml.")
        if len(node_xml) > MAX_NODE_LENGTH:
            raise ValidationError("El nodo es demasiado grande.")
        if "<!DOCTYPE" in node_xml.upper() or "<?xml" in node_xml.lower():
            raise ValidationError("El nodo no puede incluir declaraciones XML.")
        try:
            root = etree.fromstring(f"<data>{node_xml}</data>", parser=XML_PARSER)
        except etree.XMLSyntaxError as error:
            raise ValidationError(f"XML inválido: {error}") from error
        children = list(root)
        if not children:
            raise ValidationError("El nodo no contiene elementos.")
        for child in children:
            self._validate_attributes(child)
            for element in child.iter():
                if element.tag != "field":
                    continue
                field_name = element.get("name")
                if not field_name or field_name not in self.env[model_name].sudo()._fields:
                    raise ValidationError(f"Campo desconocido: {field_name!r}.")
        return "".join(etree.tostring(child, encoding="unicode") for child in children)

    @api.model
    def _validate_attribute_data(self, data: Any) -> dict[str, str]:
        """Valida los atributos de una operación set_attribute."""
        if not isinstance(data, dict) or not data:
            raise ValidationError("Cambiar atributos requiere un objeto attributes.")
        normalized: dict[str, str] = {}
        for key, value in data.items():
            if key not in ALLOWED_SET_ATTRS:
                raise ValidationError(f"Atributo no permitido: {key!r}.")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, bool):
                value = "1" if value else "0"
            if value is None:
                continue
            text = str(value)
            if len(text) > 5000:
                raise ValidationError(f"El valor de {key!r} es demasiado largo.")
            normalized[key] = text
        if not normalized:
            raise ValidationError("No hay atributos para aplicar.")
        return normalized

    @api.model
    def _normalize_operation(
        self,
        operation: Any,
        sequence: int,
        model_name: str,
    ) -> dict[str, Any]:
        """Valida y normaliza una operación individual."""
        if not isinstance(operation, dict):
            raise ValidationError("Cada operación debe ser un objeto.")
        op_type = operation.get("op_type")
        if op_type not in {"add_node", "remove_node", "set_attribute"}:
            raise ValidationError(f"Operación no soportada: {op_type!r}.")
        position = self._normalize_position(op_type, operation.get("position", "inside"))
        item = {
            "sequence": sequence * 10,
            "op_type": op_type,
            "target_xpath": self._validate_xpath(operation.get("target_xpath")),
            "position": position,
            "node_xml": "",
            "attributes_data": {},
        }
        if op_type == "add_node":
            item["node_xml"] = self._validate_node_xml(operation.get("node_xml"), model_name)
        elif op_type == "set_attribute":
            item["attributes_data"] = self._validate_attribute_data(operation.get("attributes"))
        return item

    @api.model
    def _normalize_position(self, op_type: str, position: Any) -> str:
        """Valida y ajusta la posición según el tipo de operación."""
        if position not in POSITIONS:
            raise ValidationError(f"Posición no soportada: {position!r}.")
        if op_type == "add_node" and position == "attributes":
            raise ValidationError("add_node no admite position='attributes'.")
        if op_type == "set_attribute" and position != "attributes":
            raise ValidationError("set_attribute exige position='attributes'.")
        if op_type == "remove_node":
            return "replace"
        return position

    @api.model
    def _normalize_operations(
        self,
        operations: Any,
        model_name: str,
    ) -> list[dict[str, Any]]:
        """Valida y normaliza la lista completa de operaciones."""
        if not isinstance(operations, list):
            raise ValidationError("Las operaciones deben ser una lista.")
        return [
            self._normalize_operation(operation, sequence, model_name)
            for sequence, operation in enumerate(operations, start=1)
        ]

    @api.model
    def _build_extension_arch(self, operations: list[dict[str, Any]]) -> str:
        """Construye el arch de la vista heredada a partir de las operaciones."""
        root = etree.Element("data")
        for operation in operations:
            xpath = etree.SubElement(
                root,
                "xpath",
                expr=operation["target_xpath"],
                position=operation["position"],
            )
            if operation["op_type"] == "add_node":
                wrapper = etree.fromstring(
                    f"<data>{operation['node_xml']}</data>", parser=XML_PARSER
                )
                for child in wrapper:
                    xpath.append(child)
            elif operation["op_type"] == "set_attribute":
                for name, value in operation["attributes_data"].items():
                    attribute = etree.SubElement(xpath, "attribute", name=name)
                    attribute.text = value
        return etree.tostring(root, encoding="unicode")

    @api.model
    def get_models(self) -> list[dict[str, Any]]:
        """Devuelve los modelos disponibles para el selector del editor."""
        self._check_designer()
        records = (
            self.env["ir.model"]
            .sudo()
            .search(
                [("transient", "=", False)],
                order="model",
                limit=500,
            )
        )
        return [
            {
                "model": record.model,
                "name": record.name,
                "state": record.state,
            }
            for record in records
            if record.model and not record.model.startswith("studio.")
        ]

    @api.model
    def get_views(self, model_name: str, view_type: str) -> list[dict[str, Any]]:
        """Devuelve las vistas primarias de un modelo y tipo."""
        self._check_designer()
        self._check_view_type(view_type)
        records = (
            self.env["ir.ui.view"]
            .sudo()
            .search(
                [
                    ("model", "=", model_name),
                    ("type", "=", view_type),
                    ("mode", "=", "primary"),
                ],
                order="priority, id",
            )
        )
        return [
            {
                "id": record.id,
                "name": record.name,
                "type": record.type,
                "priority": record.priority,
            }
            for record in records
        ]

    @api.model
    def get_editor_data(
        self,
        model_name: str,
        view_type: str,
        base_view_id: int | None = None,
    ) -> dict[str, Any]:
        """Carga el arch limpio, campos y operaciones de una vista."""
        self._check_designer()
        model = self._get_model(model_name)
        self._check_view_type(view_type)
        base_view = self._resolve_base_view(model_name, view_type, base_view_id)
        customization = self.env["studio.customization"].search(
            [
                ("model_id", "=", model.id),
                ("view_type", "=", view_type),
                ("base_view_id", "=", base_view.id),
                ("company_id", "=", self.env.company.id),
                ("active", "=", True),
            ],
            limit=1,
        )
        excluded = customization.extension_view_id.id if customization else False
        context = {"studio_exclude_view_id": excluded} if excluded else {}
        result = (
            self.env[model_name].sudo().with_context(**context).get_view(base_view.id, view_type)
        )
        arch = result.get("arch") or ""
        operations = []
        if customization:
            operations = [
                {
                    "id": operation.id,
                    "sequence": operation.sequence,
                    "op_type": operation.op_type,
                    "target_xpath": operation.target_xpath,
                    "position": operation.position,
                    "node_xml": operation.node_xml or "",
                    "attributes": operation.attributes_data or {},
                    "state": operation.state,
                }
                for operation in customization.operation_ids.sorted("sequence")
            ]
        return {
            "model": model_name,
            "model_label": model.name,
            "view_type": view_type,
            "base_view_id": base_view.id,
            "base_view_name": base_view.name,
            "arch": arch,
            "fields": self.env["studio.field.service"].get_fields(model_name),
            "views": self.get_views(model_name, view_type),
            "customization": {
                "id": customization.id,
                "name": customization.name,
                "version": customization.version,
                "state": customization.state,
                "extension_view_id": customization.extension_view_id.id or False,
            }
            if customization
            else False,
            "operations": operations,
        }

    @api.model
    def preview_operations(
        self,
        model_name: str,
        view_type: str,
        operations: Any,
        base_view_id: int | None = None,
    ) -> dict[str, Any]:
        """Valida operaciones y devuelve el arch de extensión sin guardarlo."""
        self._check_designer()
        self._get_model(model_name)
        self._check_view_type(view_type)
        self._resolve_base_view(model_name, view_type, base_view_id)
        normalized = self._normalize_operations(operations, model_name)
        return {
            "arch": self._build_extension_arch(normalized),
            "operations": normalized,
        }

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
        """Guarda operaciones y genera o actualiza la vista heredada."""
        self._check_designer()
        model = self._get_model(model_name)
        self._check_view_type(view_type)
        base_view = self._resolve_base_view(model_name, view_type, base_view_id)
        normalized = self._normalize_operations(operations, model_name)
        if not normalized:
            raise ValidationError("No hay operaciones para guardar.")

        customization = self.env["studio.customization"].browse()
        if customization_id:
            customization = self.env["studio.customization"].browse(customization_id)
            if not customization.exists():
                raise ValidationError("La personalización no existe.")
            customization._assert_can_manage()
            if customization.model_id != model or customization.view_type != view_type:
                raise ValidationError(
                    "La personalización no corresponde al modelo y tipo indicados."
                )
        else:
            customization = self.env["studio.customization"].search(
                [
                    ("model_id", "=", model.id),
                    ("view_type", "=", view_type),
                    ("base_view_id", "=", base_view.id),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )
        arch = self._build_extension_arch(normalized)
        checksum = hashlib.sha256(arch.encode()).hexdigest()
        version = (customization.version if customization else 0) + 1
        view_name = f"Atlas Studio [{self.env.company.name}]: {base_view.name}"
        key = f"atlas_odoo_studio.{self.env.company.id}.{model_name}_{view_type}_{base_view.id}"

        try:
            with self.env.cr.savepoint():
                if not customization:
                    customization = (
                        self.env["studio.customization"]
                        .sudo()
                        .create(
                            {
                                "name": name or f"Studio {model.name} {view_type}",
                                "model_id": model.id,
                                "view_type": view_type,
                                "base_view_id": base_view.id,
                                "company_id": self.env.company.id,
                                "description": description,
                            }
                        )
                    )
                extension = customization._get_generated_view()
                view_values = {
                    "name": view_name,
                    "model": model_name,
                    "type": view_type,
                    "inherit_id": base_view.id,
                    "mode": "extension",
                    "priority": PRIORITY,
                    "arch": arch,
                    "key": key,
                    "active": True,
                }
                if extension and extension.exists():
                    extension.sudo().write(view_values)
                else:
                    extension = self.env["ir.ui.view"].sudo().create(view_values)
                customization.sudo().write(
                    {
                        "name": name or customization.name,
                        "description": description or customization.description,
                        "base_view_id": base_view.id,
                        "extension_view_id": extension.id,
                        "state": "applied",
                        "active": True,
                        "version": version,
                        "checksum": checksum,
                        "last_applied": fields.Datetime.now(),
                        "applied_by_id": self.env.user.id,
                        "operation_ids": [Command.clear()],
                    }
                )
                self.env["studio.operation"].create(
                    [
                        {"customization_id": customization.id, "state": "applied", **item}
                        for item in normalized
                    ]
                )
                self.env["studio.audit.log"].sudo().log_event(
                    action="apply_operations",
                    model_name=model_name,
                    res_id=extension.id,
                    customization=customization,
                    after_hash=checksum,
                    details={
                        "view_type": view_type,
                        "view_id": extension.id,
                        "operations": len(normalized),
                        "version": version,
                    },
                )
        except (UserError, ValidationError, ValueError):
            self.env.registry.clear_cache()
            raise
        except Exception:
            self.env.registry.clear_cache()
            raise

        return {
            "customization_id": customization.id,
            "extension_view_id": extension.id,
            "base_view_id": base_view.id,
            "view_type": view_type,
            "version": version,
            "checksum": checksum,
            "arch": arch,
        }

    @api.model
    def apply_customization(self, customization: models.Model) -> dict[str, Any]:
        """Reaplica las operaciones almacenadas de una personalización."""
        self._check_designer()
        customization._assert_can_manage()
        operations = [
            {
                "op_type": operation.op_type,
                "target_xpath": operation.target_xpath,
                "position": operation.position,
                "node_xml": operation.node_xml,
                "attributes": operation.attributes_data,
            }
            for operation in customization.operation_ids.sorted("sequence")
        ]
        return self.save_customization(
            customization.model_name,
            customization.view_type,
            operations,
            base_view_id=customization.base_view_id.id,
            customization_id=customization.id,
            name=customization.name,
            description=customization.description or "",
        )

    @api.model
    def rollback_customization(self, customization_id: int) -> bool:
        """Desactiva la vista generada sin borrar los datos del modelo."""
        self._check_designer()
        customization = self.env["studio.customization"].browse(customization_id)
        if not customization.exists():
            raise ValidationError("La personalización no existe.")
        customization._assert_can_manage()
        if customization.extension_view_id:
            customization.extension_view_id.sudo().active = False
        customization.write({"state": "draft"})
        self.env["studio.audit.log"].sudo().log_event(
            action="rollback",
            model_name=customization.model_name,
            customization=customization,
            details={"view_type": customization.view_type},
        )
        return True
