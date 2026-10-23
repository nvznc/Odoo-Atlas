from odoo import fields, models


class PosPrepLine(models.Model):
    _name = "pos.prep.line"
    _description = "POS Preparation Line"

    prep_order_id = fields.Many2one(
        "pos.prep.order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    quantity = fields.Float(required=True, default=0.0)
    cancelled = fields.Float(default=0.0)
    pos_order_line_uuid = fields.Char(index=True)
    internal_note = fields.Char()
    customer_note = fields.Char()
    product_id = fields.Many2one("product.product", required=True)
    attribute_value_ids = fields.Many2many(
        "product.template.attribute.value",
        "pos_prep_line_attribute_value_rel",
        "prep_line_id",
        "attribute_value_id",
        string="Selected Attributes",
    )
    combo_parent_id = fields.Many2one(
        "pos.prep.line",
        index=True,
        ondelete="cascade",
    )
    combo_line_ids = fields.One2many(
        "pos.prep.line",
        "combo_parent_id",
        string="Combo Lines",
    )
    pos_order_line_id = fields.Many2one(
        "pos.order.line",
        ondelete="set null",
        index=True,
    )
    state_ids = fields.One2many(
        "pos.prep.state",
        "prep_line_id",
        string="Preparation States",
    )

    @property
    def pending_quantity(self):
        self.ensure_one()
        return self.quantity - self.cancelled
