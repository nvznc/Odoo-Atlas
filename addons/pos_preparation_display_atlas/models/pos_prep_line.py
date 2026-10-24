from odoo import fields, models


class PosPrepLine(models.Model):
    """Store preparation data for a POS order line."""

    _name = "pos.prep.line"
    _description = "Línea de preparación POS"

    prep_order_id = fields.Many2one(
        "pos.prep.order",
        string="Orden de preparación",
        required=True,
        ondelete="cascade",
        index=True,
    )
    quantity = fields.Float(string="Cantidad", required=True, default=0.0)
    cancelled = fields.Float(string="Cancelado", default=0.0)
    pos_order_line_uuid = fields.Char(string="UUID de línea POS", index=True)
    internal_note = fields.Char(string="Nota interna")
    customer_note = fields.Char(string="Nota del cliente")
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
    )
    attribute_value_ids = fields.Many2many(
        "product.template.attribute.value",
        "pos_prep_line_attribute_value_rel",
        "prep_line_id",
        "attribute_value_id",
        string="Atributos seleccionados",
    )
    combo_parent_id = fields.Many2one(
        "pos.prep.line",
        string="Línea principal del combo",
        index=True,
        ondelete="cascade",
    )
    combo_line_ids = fields.One2many(
        "pos.prep.line",
        "combo_parent_id",
        string="Líneas del combo",
    )
    pos_order_line_id = fields.Many2one(
        "pos.order.line",
        string="Línea de pedido POS",
        ondelete="set null",
        index=True,
    )
    state_ids = fields.One2many(
        "pos.prep.state",
        "prep_line_id",
        string="Estados de preparación",
    )

    @property
    def pending_quantity(self):
        """Return the quantity still pending preparation."""
        self.ensure_one()
        return self.quantity - self.cancelled
