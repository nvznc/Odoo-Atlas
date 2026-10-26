from __future__ import annotations

from typing import TYPE_CHECKING, Any

from odoo import api, fields, models
from odoo.exceptions import AccessError

if TYPE_CHECKING:
    from .studio_customization import StudioCustomization
    from .studio_operation import StudioOperation


class StudioAuditLog(models.Model):
    """Registro inmutable de cambios realizados desde Atlas-Odoo-Studio."""

    _name = "studio.audit.log"
    _description = "Auditoría de Atlas-Odoo-Studio"
    _order = "timestamp desc, id desc"

    timestamp = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )
    action = fields.Selection(
        [
            ("create_field", "Crear campo"),
            ("delete_field", "Eliminar campo"),
            ("create_model", "Crear modelo"),
            ("delete_model", "Eliminar modelo"),
            ("apply_operations", "Aplicar operaciones"),
            ("archive", "Archivar"),
            ("rollback", "Revertir"),
        ],
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
        index=True,
    )
    model_name = fields.Char(readonly=True, index=True)
    res_id = fields.Integer(readonly=True)
    customization_id = fields.Many2one(
        "studio.customization",
        ondelete="set null",
        readonly=True,
        index=True,
    )
    operation_id = fields.Many2one(
        "studio.operation",
        ondelete="set null",
        readonly=True,
    )
    before_hash = fields.Char(readonly=True)
    after_hash = fields.Char(readonly=True)
    details = fields.Json(readonly=True)
    ip = fields.Char(readonly=True)
    request_id = fields.Char(readonly=True, index=True)

    @api.model
    @api.private
    def log_event(
        self,
        action: str,
        *,
        model_name: str = "",
        res_id: int = 0,
        customization: StudioCustomization | None = None,
        operation: StudioOperation | None = None,
        before_hash: str = "",
        after_hash: str = "",
        details: dict[str, Any] | None = None,
    ) -> StudioAuditLog:
        """Crea un registro de auditoría con el contexto de la petición."""
        if not self.env.user.has_group("atlas_odoo_studio.group_studio_designer"):
            raise AccessError("No tiene permisos para escribir la auditoría.")
        customization_id = customization.id if customization else False
        operation_id = operation.id if operation else False
        company = customization.company_id if customization else self.env.company
        return (
            self.sudo()
            .with_context(active_test=False)
            .create(
                {
                    "action": action,
                    "company_id": company.id,
                    "model_name": model_name,
                    "res_id": res_id,
                    "customization_id": customization_id,
                    "operation_id": operation_id,
                    "before_hash": before_hash,
                    "after_hash": after_hash,
                    "details": details or {},
                    "ip": self.env.context.get("studio_ip", ""),
                    "request_id": self.env.context.get("studio_request_id", ""),
                }
            )
        )
