from odoo import api, fields, models, _


class PosPrepOrder(models.Model):
    _name = "pos.prep.order"
    _description = "POS Preparation Order"
    _pos_order_uniq = models.Constraint(
        "unique(pos_order_id)",
        "A preparation order already exists for this POS order.",
    )

    pos_order_id = fields.Many2one(
        "pos.order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    prep_line_ids = fields.One2many(
        "pos.prep.line",
        "prep_order_id",
        string="Preparation Lines",
    )
    order_name = fields.Char(compute="_compute_order_name")
    pdis_general_customer_note = fields.Text()
    pdis_internal_note = fields.Text()
    completion_time = fields.Integer(
        help="Minutes between order creation and completion.",
    )

    @api.depends("pos_order_id.table_id", "pos_order_id.floating_order_name", "pos_order_id.tracking_number")
    def _compute_order_name(self):
        for prep_order in self:
            pos_order = prep_order.pos_order_id
            table = prep_order._get_table_label()
            prep_order.order_name = (
                table
                or pos_order.floating_order_name
                or pos_order.tracking_number
                or pos_order.name
                or _("Order")
            )

    def _get_table_label(self):
        self.ensure_one()
        table = self.pos_order_id.table_id
        if not table:
            return self.pos_order_id.floating_order_name or ""
        label = "T%s" % table.table_number
        if table.parent_id:
            label += " & T%s" % table.parent_id.table_number
        return label

    def _get_customer_count(self):
        self.ensure_one()
        return self.pos_order_id.customer_count or 0

    def _get_states(self, display=None):
        self.ensure_one()
        states = self.prep_line_ids.state_ids
        if display:
            states = states.filtered(
                lambda state: state.stage_id.prep_display_id == display
            )
        return states

    def _get_current_stage(self, display):
        self.ensure_one()
        states = self._get_states(display)
        if not states:
            return display.stage_ids.sorted(
                lambda stage: (stage.sequence, stage.id)
            )[:1]
        return max(
            states.mapped("stage_id"),
            key=lambda stage: (stage.sequence, stage.id),
        )

    @api.model
    def process_order(self, order_id, options=None):
        options = options or {}
        order = self.env["pos.order"].browse(int(order_id)).exists()
        if not order:
            return False
        result = order._process_preparation_changes(options)
        if not result.get("change"):
            return True
        for display in result.get("displays", self.env["pos.prep.display"]):
            display._send_load_orders_message(
                sound=result.get("sound", False),
                order_id=order.id,
            )
        return True

    @api.model
    def advance_order(self, prep_order_id, display_id, direction=1):
        prep_order = self.browse(int(prep_order_id)).exists()
        display = self.env["pos.prep.display"].browse(int(display_id)).exists()
        if not prep_order or not display:
            return False
        stages = display.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
        if not stages:
            return False
        states = prep_order._get_states(display)
        if not states:
            return False
        current = prep_order._get_current_stage(display)
        index = stages.ids.index(current.id) if current.id in stages.ids else 0
        target_index = max(0, min(len(stages) - 1, index + int(direction)))
        target = stages[target_index]
        now = fields.Datetime.now()
        for state in states:
            state.write(
                {
                    "stage_id": target.id,
                    "todo": target != stages[-1],
                    "last_stage_change": now,
                }
            )
        if target == stages[-1] and not prep_order.completion_time:
            delta = now - prep_order.pos_order_id.create_date
            prep_order.completion_time = max(0, int(delta.total_seconds() / 60))
        display._send_load_orders_message()
        return display.get_display_data()

    @api.model
    def reset_order(self, prep_order_id, display_id):
        prep_order = self.browse(int(prep_order_id)).exists()
        display = self.env["pos.prep.display"].browse(int(display_id)).exists()
        if not prep_order or not display:
            return False
        stages = display.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
        if not stages:
            return False
        states = prep_order._get_states(display)
        states.write(
            {
                "stage_id": stages[0].id,
                "todo": True,
                "last_stage_change": fields.Datetime.now(),
            }
        )
        prep_order.completion_time = 0
        display._send_load_orders_message()
        return display.get_display_data()

    @api.model
    def complete_order(self, prep_order_id, display_id):
        prep_order = self.browse(int(prep_order_id)).exists()
        display = self.env["pos.prep.display"].browse(int(display_id)).exists()
        if not prep_order or not display:
            return False
        stages = display.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
        if not stages:
            return False
        states = prep_order._get_states(display)
        if not states:
            return False
        now = fields.Datetime.now()
        states.write(
            {
                "stage_id": stages[-1].id,
                "todo": False,
                "last_stage_change": now,
            }
        )
        if not prep_order.completion_time:
            delta = now - prep_order.pos_order_id.create_date
            prep_order.completion_time = max(0, int(delta.total_seconds() / 60))
        display._send_load_orders_message()
        return display.get_display_data()
