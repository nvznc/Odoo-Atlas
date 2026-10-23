from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    prep_display_enabled = fields.Boolean(
        string="Preparation Display",
        default=True,
        help="Send orders from this point of sale to the preparation screens.",
    )
