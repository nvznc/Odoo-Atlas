from odoo import fields, models


class PosPrepStage(models.Model):
    """Define a preparation stage for a display."""

    _name = "pos.prep.stage"
    _description = "Etapa de preparación POS"
    _order = "sequence, id"

    name = fields.Char(string="Nombre", required=True)
    color = fields.Char(string="Color", default="#6C757D")
    alert_timer = fields.Integer(
        string="Temporizador de alerta (minutos)",
        default=10,
        help="Minutos antes de resaltar el pedido como atrasado.",
    )
    prep_display_id = fields.Many2one(
        "pos.prep.display",
        string="Pantalla de preparación",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Secuencia", default=10)

    def is_stage_position(self, position):
        """Return whether this stage is at the given position."""
        self.ensure_one()
        stages = self.prep_display_id.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
        try:
            return stages[position].id == self.id
        except IndexError:
            return False
