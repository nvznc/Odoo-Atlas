from __future__ import annotations

from odoo import fields, models


class StudioOperation(models.Model):
    """Operación atómica aplicada sobre una vista de Odoo."""

    _name = "studio.operation"
    _description = "Operación de Atlas-Odoo-Studio"
    _order = "customization_id, sequence, id"

    customization_id = fields.Many2one(
        "studio.customization",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10, required=True)
    op_type = fields.Selection(
        [
            ("add_node", "Añadir nodo"),
            ("remove_node", "Eliminar nodo"),
            ("set_attribute", "Cambiar atributo"),
        ],
        required=True,
        default="add_node",
    )
    target_xpath = fields.Text(required=True)
    position = fields.Selection(
        [
            ("inside", "Dentro"),
            ("after", "Después"),
            ("before", "Antes"),
            ("replace", "Reemplazar"),
            ("attributes", "Atributos"),
        ],
        required=True,
        default="inside",
    )
    node_xml = fields.Text()
    attributes_data = fields.Json(default=dict)
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("applied", "Aplicada"),
            ("failed", "Fallida"),
        ],
        default="pending",
        required=True,
    )
    error = fields.Text()
    applied_at = fields.Datetime()

    _sequence_unique = models.Constraint(
        "UNIQUE(customization_id, sequence)",
        "La secuencia debe ser única dentro de la personalización.",
    )
