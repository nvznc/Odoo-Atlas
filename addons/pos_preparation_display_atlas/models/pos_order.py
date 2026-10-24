from odoo import api, models


class PosOrder(models.Model):
    """Send POS order changes to the preparation displays."""

    _inherit = "pos.order"

    @api.model
    def sync_from_ui(self, orders):
        """Process preparation changes after the POS synchronization."""
        data = super().sync_from_ui(orders)
        order_rows = data.get("pos.order") or []
        if not order_rows:
            return data

        order_ids = [row["id"] for row in order_rows if row.get("id")]
        pos_orders = self.browse(order_ids).exists()
        preparation_context = self.env.context.get("preparation") or {}
        options = preparation_context.get("process_order_options") or {}

        for order in pos_orders:
            if not order.config_id.prep_display_enabled:
                continue
            if preparation_context:
                self.env["pos.prep.order"].process_order(order.id, options)
            elif not order.config_id.module_pos_restaurant:
                self.env["pos.prep.order"].process_order(order.id, options)
            elif order.state == "paid":
                self.env["pos.prep.order"].process_order(order.id, options)

        if preparation_context and pos_orders:
            order = pos_orders[0]
            order.config_id.notify_synchronisation(
                order.config_id.current_session_id.id,
                self.env.context.get("device_identifier", 0),
            )
        return data

    def _process_preparation_changes(self, options=None):
        self.ensure_one()
        options = options or {}
        prep_order = self.env["pos.prep.order"].search(
            [("pos_order_id", "=", self.id)],
            limit=1,
        )
        if options.get("cancelled"):
            return self._cancel_preparation(prep_order)

        prep_lines = prep_order.prep_line_ids
        existing_by_uuid = {
            line.pos_order_line_uuid: line for line in prep_lines if line.pos_order_line_uuid
        }
        seen_uuids = set()
        displays = self.env["pos.prep.display"]
        category_ids = set()
        changed = False
        sound = False
        order_added = False

        for line in self.lines:
            result = self._process_preparation_line(line, prep_order, existing_by_uuid)
            if not result:
                continue
            prep_order = result["prep_order"]
            existing_by_uuid[line.uuid] = result["prep_line"]
            seen_uuids.add(line.uuid)
            displays |= result["displays"]
            category_ids.update(result["category_ids"])
            changed = changed or result["changed"]
            sound = sound or result["sound"]
            order_added = order_added or result["order_added"]

        result = self._cancel_missing_prep_lines(prep_lines, seen_uuids)
        displays |= result["displays"]
        category_ids.update(result["category_ids"])
        changed = changed or result["changed"]

        if prep_order:
            changed = self._update_preparation_notes(prep_order, options) or changed

        return {
            "change": changed,
            "sound": sound,
            "displays": displays,
            "category_ids": category_ids,
            "order_added": order_added,
        }

    def _process_preparation_line(self, line, prep_order, existing_by_uuid):
        qty = line.qty
        if not line.product_id or qty <= 0:
            return False
        line_displays = self.env["pos.prep.display"]._get_preparation_displays(
            self, line.product_id.pos_categ_ids.ids
        )
        if not line_displays:
            return False

        prep_line = existing_by_uuid.get(line.uuid)
        order_added = False
        sound = False
        changed = False
        if not prep_line:
            if not prep_order:
                prep_order = self.env["pos.prep.order"].create(
                    {
                        "pos_order_id": self.id,
                        "pdis_general_customer_note": self.general_customer_note or "",
                        "pdis_internal_note": self.internal_note or "[]",
                    }
                )
            prep_line = self.env["pos.prep.line"].create(
                {
                    "prep_order_id": prep_order.id,
                    "pos_order_line_uuid": line.uuid,
                    "pos_order_line_id": line.id,
                    "product_id": line.product_id.id,
                    "quantity": qty,
                    "cancelled": 0.0,
                    "internal_note": line.note or "",
                    "customer_note": line.customer_note or "",
                    "attribute_value_ids": [(6, 0, line.attribute_value_ids.ids)],
                    "combo_parent_id": self._get_prep_combo_parent(line, prep_order),
                }
            )
            order_added = True
            sound = True
            changed = True
        else:
            changed = self._update_preparation_line(prep_line, line)

        self._ensure_preparation_states(prep_line, line_displays)
        return {
            "prep_order": prep_order,
            "prep_line": prep_line,
            "displays": line_displays,
            "category_ids": set(line.product_id.pos_categ_ids.ids),
            "changed": changed,
            "sound": sound,
            "order_added": order_added,
        }

    def _update_preparation_line(self, prep_line, line):
        changed = False
        remaining = prep_line.quantity - prep_line.cancelled
        if line.qty > remaining:
            prep_line.quantity += line.qty - remaining
            changed = True
        elif line.qty < remaining:
            prep_line.cancelled += remaining - line.qty
            changed = True

        values = {}
        if prep_line.product_id != line.product_id:
            values["product_id"] = line.product_id.id
        if prep_line.internal_note != (line.note or ""):
            values["internal_note"] = line.note or ""
        if prep_line.customer_note != (line.customer_note or ""):
            values["customer_note"] = line.customer_note or ""
        attribute_ids = line.attribute_value_ids.ids
        if set(prep_line.attribute_value_ids.ids) != set(attribute_ids):
            values["attribute_value_ids"] = [(6, 0, attribute_ids)]
        if values:
            prep_line.write(values)
            changed = True
        return changed

    def _ensure_preparation_states(self, prep_line, line_displays):
        for display in line_displays:
            display_states = prep_line.state_ids.filtered(
                lambda state, display=display: state.stage_id.prep_display_id == display
            )
            if display_states:
                continue
            stages = display.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
            if stages:
                self.env["pos.prep.state"].create(
                    {
                        "prep_line_id": prep_line.id,
                        "stage_id": stages[0].id,
                        "todo": True,
                    }
                )

    def _cancel_preparation(self, prep_order):
        changed = False
        displays = self.env["pos.prep.display"]
        category_ids = set()
        if prep_order:
            for prep_line in prep_order.prep_line_ids:
                if prep_line.cancelled != prep_line.quantity:
                    prep_line.cancelled = prep_line.quantity
                    changed = True
                category_ids.update(prep_line.product_id.pos_categ_ids.ids)
            if changed:
                displays = self.env["pos.prep.display"]._get_preparation_displays(
                    self, category_ids
                )
        return {
            "change": changed,
            "sound": False,
            "displays": displays,
            "category_ids": category_ids,
        }

    def _cancel_missing_prep_lines(self, prep_lines, seen_uuids):
        changed = False
        displays = self.env["pos.prep.display"]
        category_ids = set()
        for prep_line in prep_lines:
            if prep_line.pos_order_line_uuid in seen_uuids:
                continue
            if prep_line.cancelled == prep_line.quantity:
                continue
            prep_line.cancelled = prep_line.quantity
            changed = True
            category_ids.update(prep_line.product_id.pos_categ_ids.ids)
            displays |= self.env["pos.prep.display"]._get_preparation_displays(
                self, prep_line.product_id.pos_categ_ids.ids
            )
        return {
            "changed": changed,
            "displays": displays,
            "category_ids": category_ids,
        }

    def _update_preparation_notes(self, prep_order, options):
        changed = False
        general_note = options.get("general_customer_note")
        internal_note = options.get("internal_note")
        if general_note is not None and prep_order.pdis_general_customer_note != general_note:
            prep_order.pdis_general_customer_note = general_note
            changed = True
        if internal_note is not None and prep_order.pdis_internal_note != internal_note:
            prep_order.pdis_internal_note = internal_note
            changed = True
        return changed

    def _get_prep_combo_parent(self, line, prep_order):
        if not line.combo_parent_id:
            return False
        parent_line = prep_order.prep_line_ids.filtered(
            lambda prep_line: prep_line.pos_order_line_uuid == line.combo_parent_id.uuid
        )[:1]
        return parent_line.id or False
