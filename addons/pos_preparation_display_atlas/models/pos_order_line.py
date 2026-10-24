from odoo import fields, models


class PosOrderLine(models.Model):
    """Track preparation and service times on POS order lines."""

    _inherit = "pos.order.line"

    preparation_time = fields.Integer(
        string="Tiempo de preparación",
        default=-1,
        readonly=True,
        help="Segundos entre el pedido y el momento en que se preparó la línea.",
    )
    service_time = fields.Integer(
        string="Tiempo de servicio",
        default=-1,
        readonly=True,
        help="Segundos entre la preparación y el servicio.",
    )
