from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    prep_display_enabled = fields.Boolean(
        string="Pantalla de preparación",
        default=True,
        help="Envía los pedidos de este punto de venta a las pantallas de preparación.",
    )
