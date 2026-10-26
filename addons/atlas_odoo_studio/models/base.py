from __future__ import annotations

from typing import Any

from odoo import api, models


class Base(models.AbstractModel):
    """Amplía la clave de caché de vistas con el filtro del editor."""

    _inherit = "base"

    @api.model
    def _get_view_cache_key(
        self,
        view_id: int | None = None,
        view_type: str = "form",
        **options: Any,
    ) -> tuple:
        """Incluye la vista excluida para no reutilizar una caché incorrecta."""
        key = super()._get_view_cache_key(view_id, view_type, **options)
        key = (*key, f"atlas_company:{self.env.company.id}")
        excluded_view_id = self.env.context.get("studio_exclude_view_id")
        if excluded_view_id:
            return (*key, f"studio_exclude_view_id:{excluded_view_id}")
        return key
