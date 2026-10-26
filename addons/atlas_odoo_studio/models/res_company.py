from odoo import api, models


class ResCompany(models.Model):
    """Mantiene los defaults de compañía de los modelos generados."""

    _inherit = "res.company"

    @api.model_create_multi
    def create(self, vals_list):
        """Añade los defaults de compañía a los modelos generados existentes."""
        companies = super().create(vals_list)
        self.env["studio.metadata.service"].sudo()._add_company_defaults(companies)
        return companies
