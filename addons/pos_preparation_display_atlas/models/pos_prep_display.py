import json
import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosPrepDisplay(models.Model):
    _name = "pos.prep.display"
    _description = "Pantalla de preparación POS"
    _inherit = ["pos.bus.mixin", "pos.load.mixin"]
    _order = "name, id"

    name = fields.Char(string="Nombre", required=True)
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    pos_config_ids = fields.Many2many("pos.config", string="Punto de venta")
    category_ids = fields.Many2many(
        "pos.category",
        string="Categorías de productos",
        help="Déjalo vacío para mostrar todas las categorías.",
    )
    stage_ids = fields.One2many("pos.prep.stage", "prep_display_id", string="Etapas")
    order_count = fields.Integer(string="Pedidos en curso", compute="_compute_dashboard_values")
    average_time = fields.Integer(string="Tiempo promedio", compute="_compute_dashboard_values")
    contains_bar_restaurant = fields.Boolean(
        string="Incluye bar/restaurante",
        compute="_compute_contains_bar_restaurant",
        store=True,
    )
    auto_clear = fields.Boolean(
        string="Limpieza automática",
        help=(
            "Elimina los pedidos listos de la pantalla pública después del "
            "intervalo configurado."
        ),
    )
    clear_time_interval = fields.Integer(
        string="Limpiar después de (minutos)",
        default=10,
    )
    preparing_label = fields.Char(string="Etiqueta Preparando", default="Preparando")
    almost_ready_label = fields.Char(string="Etiqueta Casi listo", default="Casi Listo")
    ready_label = fields.Char(string="Etiqueta Listo", default="Listo")

    @api.model
    def _default_stages(self):
        return [
            {"name": "Preparando", "color": "#6C757D", "alert_timer": 10, "sequence": 10},
            {"name": "Listo", "color": "#4D89D1", "alert_timer": 5, "sequence": 20},
            {"name": "Completado", "color": "#4EA82A", "alert_timer": 0, "sequence": 30},
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("stage_ids"):
                vals["stage_ids"] = [
                    (0, 0, stage) for stage in self._default_stages()
                ]
        return super().create(vals_list)

    @api.constrains("clear_time_interval")
    def _check_clear_time_interval(self):
        for display in self:
            if display.clear_time_interval <= 0:
                raise ValidationError(
                    _("El intervalo de limpieza automática debe ser mayor que cero.")
                )

    @api.constrains("stage_ids")
    def _check_stage_ids(self):
        for display in self:
            if not display.stage_ids:
                raise ValidationError(
                    _("La pantalla de preparación debe tener al menos una etapa.")
                )

    @api.depends("pos_config_ids")
    def _compute_contains_bar_restaurant(self):
        for display in self:
            display.contains_bar_restaurant = any(
                display._get_pos_config_ids().mapped("module_pos_restaurant")
            )

    def _compute_dashboard_values(self):
        for display in self:
            states = display._get_open_states()
            display.order_count = len(
                states.mapped("prep_line_id.prep_order_id")
            )
            completed = self.env["pos.prep.order"].search(
                [
                    ("completion_time", ">", 0),
                    (
                        "prep_line_ids.state_ids.stage_id.prep_display_id",
                        "=",
                        display.id,
                    ),
                    (
                        "pos_order_id.session_id.state",
                        "not in",
                        ["closed", "closing_control"],
                    ),
                ],
                limit=200,
            )
            times = completed.mapped("completion_time")
            display.average_time = round(sum(times) / len(times)) if times else 0

    def _get_pos_config_ids(self):
        self.ensure_one()
        return self.pos_config_ids or self.env["pos.config"].search([])

    def _is_enabled_for_config(self, config):
        self.ensure_one()
        if not config or not getattr(config, "prep_display_enabled", False):
            return False
        if self.company_id and self.company_id != config.company_id:
            return False
        if self.pos_config_ids and config not in self.pos_config_ids:
            return False
        return True

    def _matches_categories(self, category_ids):
        self.ensure_one()
        if not self.category_ids:
            return True
        return bool(set(self.category_ids.ids) & set(category_ids or []))

    @api.model
    def _get_preparation_displays(self, order, category_ids):
        if not order or not order.config_id:
            return self.browse()
        candidates = self.search(
            [
                ("active", "=", True),
                "|",
                ("company_id", "=", order.config_id.company_id.id),
                ("company_id", "=", False),
            ]
        )
        category_ids = set(category_ids or [])
        return candidates.filtered(
            lambda display: display._is_enabled_for_config(order.config_id)
            and display._matches_categories(category_ids)
        )

    def _get_open_states(self):
        self.ensure_one()
        if not self.stage_ids:
            return self.env["pos.prep.state"]
        completed_stage = self.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))[-1]
        states = self.env["pos.prep.state"].search(
            [
                ("stage_id", "in", self.stage_ids.ids),
                ("stage_id", "!=", completed_stage.id),
            ]
        )
        return states.filtered(
            lambda state: state.prep_line_id.prep_order_id.pos_order_id.session_id.state
            not in ("closed", "closing_control")
            and state.prep_line_id.quantity - state.prep_line_id.cancelled > 0
        )

    def _load_pos_data_domain(self, data, config):
        if not getattr(config, "prep_display_enabled", False):
            return False
        return [
            ("active", "=", True),
            ("company_id", "=", config.company_id.id),
            "|",
            ("pos_config_ids", "=", False),
            ("pos_config_ids", "in", config.id),
        ]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["id", "name", "category_ids", "pos_config_ids", "write_date"]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return [
            "id",
            "name",
            "category_ids",
            "pos_config_ids",
            "stage_ids",
            "access_token",
            "auto_clear",
            "clear_time_interval",
            "preparing_label",
            "almost_ready_label",
            "ready_label",
        ]

    def _send_load_orders_message(self, sound=False, order_id=False):
        self.ensure_one()
        self._notify(
            "LOAD_ORDERS",
            {"sound": bool(sound), "orderId": order_id or False},
        )
        self._notify("NEW_ORDERS", {"orderId": order_id or False})

    def _notify_state_change(self, states):
        displays = states.mapped("stage_id.prep_display_id")
        for display in displays:
            display._send_load_orders_message()

    def _stage_payload(self):
        self.ensure_one()
        return [
            {
                "id": stage.id,
                "name": stage.name,
                "color": stage.color or "#6C757D",
                "alert_timer": stage.alert_timer,
                "sequence": stage.sequence,
            }
            for stage in self.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
        ]

    @api.model
    def _parse_note(self, note):
        if not note:
            return []
        try:
            value = json.loads(note)
        except (TypeError, ValueError):
            return [str(note)]
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    label = item.get("text") or item.get("name") or item.get("note")
                    if label:
                        result.append(str(label))
                elif item:
                    result.append(str(item))
            return result
        return [str(value)]

    def _serialize_order_lines(self, states, stage):
        lines = []
        for state in states:
            line = state.prep_line_id
            attributes = []
            for value in line.attribute_value_ids:
                attributes.append(
                    {
                        "attribute": value.attribute_id.name,
                        "value": value.name,
                    }
                )
            lines.append(
                {
                    "id": line.id,
                    "state_id": state.id,
                    "product": line.product_id.display_name or _("Producto"),
                    "quantity": line.quantity - line.cancelled,
                    "ordered_quantity": line.quantity,
                    "cancelled": line.cancelled,
                    "todo": state.todo,
                    "note": line.internal_note or "",
                    "customer_note": line.customer_note or "",
                    "attributes": attributes,
                    "combo_parent_id": line.combo_parent_id.id or False,
                }
            )
        return lines

    def get_display_data(self):
        self.ensure_one()
        states = self.env["pos.prep.state"].search(
            [
                ("stage_id", "in", self.stage_ids.ids),
            ]
        )
        states = states.filtered(
            lambda state: state.prep_line_id.prep_order_id.pos_order_id.session_id.state
            not in ("closed", "closing_control")
            and state.prep_line_id.quantity - state.prep_line_id.cancelled > 0
        )
        grouped = {}
        for state in states:
            prep_order = state.prep_line_id.prep_order_id
            key = (prep_order.id, state.stage_id.id)
            grouped.setdefault(
                key,
                {
                    "id": prep_order.id,
                    "name": prep_order.order_name
                    or prep_order.pos_order_id.tracking_number
                    or _("Pedido"),
                    "tracking_number": prep_order.pos_order_id.tracking_number or "",
                    "table": prep_order._get_table_label(),
                    "customer_count": prep_order._get_customer_count(),
                    "customer_note": prep_order.pdis_general_customer_note or "",
                    "internal_note": self._parse_note(prep_order.pdis_internal_note),
                    "stage_id": state.stage_id.id,
                    "stage_name": state.stage_id.name,
                    "stage_color": state.stage_id.color or "#6C757D",
                    "stage_sequence": state.stage_id.sequence,
                    "stage_started_at": state.last_stage_change,
                    "states": [],
                },
            )
            grouped[key]["states"].append(state)
            if state.last_stage_change and (
                not grouped[key]["stage_started_at"]
                or state.last_stage_change < grouped[key]["stage_started_at"]
            ):
                grouped[key]["stage_started_at"] = state.last_stage_change

        orders = []
        for item in grouped.values():
            stage = self.stage_ids.filtered(lambda s: s.id == item["stage_id"])
            item["lines"] = self._serialize_order_lines(item.pop("states"), stage)
            item["stage_started_at"] = (
                fields.Datetime.to_string(item["stage_started_at"])
                if item["stage_started_at"]
                else fields.Datetime.to_string(fields.Datetime.now())
            )
            orders.append(item)

        stage_order = {
            stage.id: index
            for index, stage in enumerate(
                self.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
            )
        }
        orders.sort(
            key=lambda item: (
                stage_order.get(item["stage_id"], 999),
                item["stage_started_at"],
                item["id"],
            )
        )
        return {
            "display": {
                "id": self.id,
                "name": self.name,
                "preparing_label": self.preparing_label or "Preparando",
                "almost_ready_label": self.almost_ready_label or "Casi Listo",
                "ready_label": self.ready_label or "Listo",
            },
            "stages": self._stage_payload(),
            "orders": orders,
        }

    def _get_public_order_payload(self, prep_order, ready_since=False):
        pos_order = prep_order.pos_order_id
        return {
            "id": prep_order.id,
            "name": prep_order.order_name
            or pos_order.tracking_number
            or pos_order.name
            or _("Pedido"),
            "tracking_number": pos_order.tracking_number or "",
            "table": prep_order._get_table_label(),
            "customer_count": prep_order._get_customer_count(),
            "ready_since": fields.Datetime.to_string(ready_since)
            if ready_since
            else False,
        }

    def _get_public_orders(self):
        self.ensure_one()
        stages = self.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
        if len(stages) <= 1:
            return {"preparing": [], "almost_ready": [], "ready": []}

        completed_stage = stages[-1]
        ready_stage = stages[-2]
        states = self.env["pos.prep.state"].search(
            [
                ("stage_id", "in", stages.ids),
                ("stage_id", "!=", completed_stage.id),
            ]
        )
        states = states.filtered(
            lambda state: state.prep_line_id.prep_order_id.pos_order_id.session_id.state
            not in ("closed", "closing_control")
            and state.prep_line_id.quantity - state.prep_line_id.cancelled > 0
        )

        by_order = {}
        for state in states:
            prep_order = state.prep_line_id.prep_order_id
            by_order.setdefault(prep_order.id, []).append(state)

        preparing = []
        almost_ready = []
        ready = []
        now = fields.Datetime.now()
        for prep_order_id, order_states in by_order.items():
            prep_order = self.env["pos.prep.order"].browse(prep_order_id)
            order_states = self.env["pos.prep.state"].browse(
                [state.id for state in order_states]
            )
            ready_states = order_states.filtered(lambda s: s.stage_id == ready_stage)
            if len(ready_states) == len(order_states):
                ready_since = max(ready_states.mapped("last_stage_change"))
                if (
                    self.auto_clear
                    and ready_since
                    and now - ready_since > timedelta(minutes=self.clear_time_interval)
                ):
                    continue
                ready.append(
                    self._get_public_order_payload(prep_order, ready_since)
                )
            elif ready_states:
                almost_ready.append(self._get_public_order_payload(prep_order))
            else:
                preparing.append(self._get_public_order_payload(prep_order))

        preparing.sort(key=lambda item: (item["tracking_number"], item["id"]))
        almost_ready.sort(key=lambda item: (item["tracking_number"], item["id"]))
        ready.sort(key=lambda item: (item.get("ready_since") or "", item["id"]))
        return {
            "preparing": preparing,
            "almost_ready": almost_ready,
            "ready": ready,
            "labels": {
                "preparing": self.preparing_label or "Preparando",
                "almost_ready": self.almost_ready_label or "Casi Listo",
                "ready": self.ready_label or "Listo",
            },
            "display_name": self.name,
        }

    @api.model
    def get_order_status_data(self, access_token):
        display = self.sudo().search(
            [("access_token", "=", access_token), ("active", "=", True)],
            limit=1,
        )
        if not display:
            return False
        return display._get_public_orders()

    def reset_all_orders(self, return_data=False):
        data = False
        for display in self:
            states = self.env["pos.prep.state"].search(
                [("stage_id", "in", display.stage_ids.ids)]
            )
            states.unlink()
            display._send_load_orders_message()
            if return_data:
                data = display.get_display_data()
        return data or True

    def open_preparation_screen(self):
        self.ensure_one()
        self.sudo()._ensure_access_token()
        return {
            "type": "ir.actions.act_url",
            "url": "/pos_preparation_display/web?display_id=%d" % self.id,
            "target": "self",
        }

    def open_order_status_screen(self):
        self.ensure_one()
        self.sudo()._ensure_access_token()
        return {
            "type": "ir.actions.act_url",
            "url": "/pos-order-tracking?access_token=%s" % self.access_token,
            "target": "new",
        }

    def _ensure_access_token(self):
        for display in self:
            if not display.access_token:
                display.access_token = str(uuid.uuid4())
        return self[:1].access_token

    @api.model
    def _clean_preparation_data(self):
        limit = fields.Datetime.now() - timedelta(days=1)
        orders = self.env["pos.prep.order"].search(
            [
                ("write_date", "<=", limit),
                "|",
                ("pos_order_id.session_id.state", "in", ["closed", "closing_control"]),
                ("completion_time", ">", 0),
            ]
        )
        orders.unlink()
        return True
