from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError

if TYPE_CHECKING:
    from .studio_operation import StudioOperation

PROTECTED_FIELDS = frozenset({"extension_view_id", "version", "checksum", "last_applied"})
STRUCTURAL_FIELDS = frozenset({"model_id", "view_type", "base_view_id", "company_id"})


class StudioCustomization(models.Model):
    """Agrupa las operaciones aplicadas a una vista concreta."""

    _name = "studio.customization"
    _description = "Personalización de Atlas-Odoo-Studio"
    _order = "write_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(required=True, default="Personalización")
    model_id = fields.Many2one(
        "ir.model",
        string="Modelo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_name = fields.Char(related="model_id.model", store=True, index=True)
    view_type = fields.Selection(
        [
            ("form", "Formulario"),
            ("list", "Lista"),
            ("kanban", "Kanban"),
            ("search", "Búsqueda"),
        ],
        required=True,
        default="form",
    )
    base_view_id = fields.Many2one(
        "ir.ui.view",
        string="Vista base",
        ondelete="set null",
        index=True,
    )
    extension_view_id = fields.Many2one(
        "ir.ui.view",
        string="Vista generada",
        ondelete="set null",
        readonly=True,
    )
    operation_ids = fields.One2many(
        "studio.operation",
        "customization_id",
        string="Operaciones",
    )
    operation_count = fields.Integer(compute="_compute_operation_count")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("applied", "Aplicada"),
            ("archived", "Archivada"),
        ],
        default="draft",
        required=True,
    )
    version = fields.Integer(default=1, readonly=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    description = fields.Text()
    checksum = fields.Char(readonly=True)
    last_applied = fields.Datetime(readonly=True)
    applied_by_id = fields.Many2one("res.users", readonly=True)

    _name_unique = models.Constraint(
        "UNIQUE(model_id, view_type, base_view_id, company_id)",
        "Ya existe una personalización para esta vista, modelo y compañía.",
    )

    @api.depends("operation_ids")
    def _compute_operation_count(self) -> None:
        """Cuenta las operaciones de la personalización."""
        for record in self:
            record.operation_count = len(record.operation_ids)

    def action_apply(self) -> bool:
        """Aplica las operaciones pendientes de la personalización."""
        self.ensure_one()
        self.env["studio.view.service"].apply_customization(self)
        return True

    def action_archive(self) -> bool:
        """Archiva la personalización y desactiva su vista generada."""
        for record in self:
            record._assert_can_manage()
            extension = record._get_generated_view()
            if extension:
                extension.sudo().active = False
            record.write({"state": "archived", "active": False})
            self.env["studio.audit.log"].sudo().log_event(
                action="archive",
                model_name=record.model_name,
                customization=record,
                details={"view_type": record.view_type},
            )
        return True

    def action_restore(self) -> bool:
        """Reactiva una personalización archivada."""
        for record in self:
            record._assert_can_manage()
            extension = record._get_generated_view()
            if extension:
                extension.sudo().active = True
            record.write({"state": "applied", "active": True})
        return True

    def unlink(self) -> bool:
        """Elimina la vista generada antes de borrar la personalización."""
        if not self.env.su:
            for record in self:
                record._assert_can_manage()
        for record in self:
            extension = record._get_generated_view()
            if extension:
                extension.sudo().unlink()
        return super().unlink()

    def _get_generated_view(self) -> models.Model:
        """Devuelve la extensión generada solo si pertenece a esta personalización."""
        self.ensure_one()
        view = self.extension_view_id
        expected_key = f"atlas_odoo_studio.{self.company_id.id}."
        legacy_key = (
            f"atlas_odoo_studio.{self.model_id.model}_{self.view_type}_{self.base_view_id.id}"
        )
        if (
            view
            and view.mode == "extension"
            and view.inherit_id == self.base_view_id
            and view.key
            and (view.key.startswith(expected_key) or view.key == legacy_key)
        ):
            return view
        return self.env["ir.ui.view"].browse()

    def _assert_can_manage(self) -> None:
        """Comprueba el grupo diseñador y la compañía."""
        self.ensure_one()
        if not self.env.user.has_group("atlas_odoo_studio.group_studio_designer"):
            raise AccessError("No tiene permisos para administrar Atlas-Odoo-Studio.")
        if self.company_id and self.company_id != self.env.company:
            raise UserError("La personalización pertenece a otra compañía.")

    def create(self, vals: dict) -> StudioCustomization:
        """Impide crear personalizaciones con campos generados o estructurales."""
        protected = PROTECTED_FIELDS | STRUCTURAL_FIELDS
        if protected.intersection(vals) and not self.env.su:
            raise UserError("Los campos generados solo pueden modificarse desde el editor.")
        return super().create(vals)

    def write(self, vals: dict) -> bool:
        """Protege la escritura directa de campos generados y estructurales."""
        protected = PROTECTED_FIELDS | STRUCTURAL_FIELDS
        if protected.intersection(vals) and not self.env.su:
            raise UserError("Los campos generados solo pueden modificarse desde el editor.")
        return super().write(vals)

    def _get_or_create_operation(self, values: dict) -> StudioOperation:
        """Crea una operación dentro de la personalización."""
        self.ensure_one()
        return self.env["studio.operation"].create({"customization_id": self.id, **values})

    def _clear_operations(self) -> None:
        """Elimina las operaciones actuales antes de reemplazarlas."""
        for record in self:
            record.write({"operation_ids": [Command.clear()]})
