from __future__ import annotations

from odoo import api, models
from odoo.fields import Domain


class IrUiView(models.Model):
    """Extiende la resolución de vistas para excluir la vista del editor."""

    _inherit = "ir.ui.view"

    @api.model
    def _get_inheriting_views_domain(self) -> Domain:
        """Permite obtener el arch sin la extensión que se está editando."""
        domain = super()._get_inheriting_views_domain()
        company_id = self.env.company.id
        legacy_extension_ids = (
            self.env["studio.customization"]
            .sudo()
            .search([("company_id", "=", company_id), ("extension_view_id", "!=", False)])
            .mapped("extension_view_id")
            .ids
        )
        allowed_keys = (
            Domain("key", "=", False)
            | Domain("key", "not like", "atlas_odoo_studio.%")
            | Domain("key", "=like", f"atlas_odoo_studio.{company_id}.%")
            | (Domain("key", "=like", "atlas_odoo_studio.view_%") & Domain("mode", "=", "primary"))
            | Domain("id", "in", legacy_extension_ids)
        )
        domain &= allowed_keys
        excluded_view_id = self.env.context.get("studio_exclude_view_id")
        if excluded_view_id:
            return domain & Domain("id", "!=", excluded_view_id)
        return domain
