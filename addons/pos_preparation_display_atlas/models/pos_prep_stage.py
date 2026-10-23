from odoo import fields, models


class PosPrepStage(models.Model):
    _name = "pos.prep.stage"
    _description = "POS Preparation Stage"
    _order = "sequence, id"

    name = fields.Char(required=True)
    color = fields.Char(default="#6C757D")
    alert_timer = fields.Integer(
        string="Alert timer (minutes)",
        default=10,
        help="Minutes before the order is highlighted as late.",
    )
    prep_display_id = fields.Many2one(
        "pos.prep.display",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    def is_stage_position(self, position):
        self.ensure_one()
        stages = self.prep_display_id.stage_ids.sorted(
            lambda stage: (stage.sequence, stage.id)
        )
        try:
            return stages[position].id == self.id
        except IndexError:
            return False
