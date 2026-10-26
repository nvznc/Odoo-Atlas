from odoo import fields, models


class IrModel(models.Model):
    """Marca la compañía propietaria de los modelos creados por Atlas."""

    _inherit = "ir.model"

    studio_company_id = fields.Many2one(
        "res.company",
        string="Atlas Studio Company",
        ondelete="set null",
        index=True,
        readonly=True,
        copy=False,
    )


class IrModelFields(models.Model):
    """Marca la compañía propietaria de los campos creados por Atlas."""

    _inherit = "ir.model.fields"

    studio_company_id = fields.Many2one(
        "res.company",
        string="Atlas Studio Company",
        ondelete="set null",
        index=True,
        readonly=True,
        copy=False,
    )
