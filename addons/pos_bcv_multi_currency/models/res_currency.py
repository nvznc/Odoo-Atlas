from odoo import api, models


class ResCurrency(models.Model):
    """Expose the BCV currency in the point-of-sale loaded data."""

    _inherit = "res.currency"

    @api.model
    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data, config)
        if config and config.bcv_enabled and config.bcv_currency_id:
            leaf = ("id", "=", config.bcv_currency_id.id)
            return ["|", leaf, *domain] if domain else [leaf]
        return domain
