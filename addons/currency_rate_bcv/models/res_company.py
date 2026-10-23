"""Company fields used to report the last BCV synchronization status."""

from odoo import fields, models


class ResCompany(models.Model):
    """Expose the last BCV rate synchronization details on companies."""

    _inherit = "res.company"

    currency_rate_bcv_last_sync = fields.Datetime(
        string="BCV: último intento",
        readonly=True,
        copy=False,
    )
    currency_rate_bcv_last_status = fields.Selection(
        selection=[
            ("success", "Correcto"),
            ("warning", "Aviso"),
            ("error", "Error"),
        ],
        string="BCV: estado",
        readonly=True,
        copy=False,
    )
    currency_rate_bcv_last_message = fields.Text(
        string="BCV: detalle",
        readonly=True,
        copy=False,
    )
    currency_rate_bcv_last_rate = fields.Float(
        string="BCV: última tasa",
        digits=(12, 6),
        readonly=True,
        copy=False,
    )
    currency_rate_bcv_last_rate_date = fields.Date(
        string="BCV: fecha de la última tasa",
        readonly=True,
        copy=False,
    )
