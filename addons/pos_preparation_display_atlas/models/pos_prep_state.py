from odoo import api, fields, models


class PosPrepState(models.Model):
    _name = "pos.prep.state"
    _description = "Estado de preparación POS"

    prep_line_id = fields.Many2one(
        "pos.prep.line",
        string="Línea de preparación",
        required=True,
        ondelete="cascade",
        index=True,
    )
    todo = fields.Boolean(string="Pendiente", default=True)
    stage_id = fields.Many2one(
        "pos.prep.stage",
        string="Etapa",
        required=True,
        ondelete="cascade",
        index=True,
    )
    last_stage_change = fields.Datetime(
        string="Último cambio de etapa",
        default=fields.Datetime.now,
    )

    @api.model
    def toggle_state(self, state_id):
        state = self.browse(int(state_id)).exists()
        if not state:
            return False
        state.todo = not state.todo
        display = state.stage_id.prep_display_id
        display._send_load_orders_message()
        return display.get_display_data()
