"""Expose the jIotBox customer receipt URL in the Point of Sale settings."""

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Add a related jIotBox receipt URL to the settings form."""

    _inherit = "res.config.settings"

    pos_jiotbox_customer_receipt_url = fields.Char(
        related="pos_config_id.jiotbox_customer_receipt_url",
        readonly=False,
    )
