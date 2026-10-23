from odoo import fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    preparation_time = fields.Integer(
        string="Preparation Time",
        default=-1,
        readonly=True,
        help="Seconds between the order and the moment the line was prepared.",
    )
    service_time = fields.Integer(
        string="Service Time",
        default=-1,
        readonly=True,
        help="Seconds between preparation and service.",
    )
