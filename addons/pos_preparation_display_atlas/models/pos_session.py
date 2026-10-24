from odoo import api, models


class PosSession(models.Model):
    """Load preparation displays with the POS session data."""

    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config):
        models = super()._load_pos_data_models(config)
        return models + ["pos.prep.display"]
