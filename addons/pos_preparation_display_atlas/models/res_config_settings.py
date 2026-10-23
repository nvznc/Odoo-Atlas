from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_prep_display_enabled = fields.Boolean(
        related="pos_config_id.prep_display_enabled",
        readonly=False,
    )
