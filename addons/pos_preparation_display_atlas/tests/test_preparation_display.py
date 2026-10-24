from uuid import uuid4

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPreparationDisplay(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category_food = cls.env["pos.category"].create({"name": "Kitchen Test"})
        cls.category_drinks = cls.env["pos.category"].create({"name": "Bar Test"})
        cls.product_food = cls.env["product.product"].create(
            {
                "name": "Test Burger",
                "available_in_pos": True,
                "list_price": 5.0,
                "pos_categ_ids": [(6, 0, [cls.category_food.id])],
            }
        )
        cls.product_drink = cls.env["product.product"].create(
            {
                "name": "Test Juice",
                "available_in_pos": True,
                "list_price": 2.0,
                "pos_categ_ids": [(6, 0, [cls.category_drinks.id])],
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Preparation Test POS",
                "prep_display_enabled": True,
            }
        )
        cls.session = cls.env["pos.session"].create(
            {"config_id": cls.config.id, "user_id": cls.env.uid}
        )
        cls.session.set_opening_control(0.0, "", 0.0)
        cls.display = cls.env["pos.prep.display"].create(
            {
                "name": "Kitchen Test Display",
                "pos_config_ids": [(6, 0, [cls.config.id])],
                "category_ids": [(6, 0, [cls.category_food.id])],
            }
        )

    def _create_order(self, lines, table=None):
        values = {
            "session_id": self.session.id,
            "amount_total": sum(qty * 5.0 for _product, qty in lines),
            "amount_paid": 0.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
        }
        if table:
            values["table_id"] = table.id
        order = self.env["pos.order"].create(values)
        for product, qty in lines:
            self.env["pos.order.line"].create(
                {
                    "order_id": order.id,
                    "product_id": product.id,
                    "qty": qty,
                    "price_unit": product.list_price,
                    "price_subtotal": qty * product.list_price,
                    "price_subtotal_incl": qty * product.list_price,
                }
            )
        return order

    def _process_order(self, order, options=None):
        self.env["pos.prep.order"].process_order(order.id, options or {})
        return self.env["pos.prep.order"].search([("pos_order_id", "=", order.id)], limit=1)

    def test_default_stages_and_labels(self):
        stages = self.display.stage_ids.sorted(lambda stage: stage.sequence)
        self.assertEqual([stage.name for stage in stages], ["Preparando", "Listo", "Completado"])
        self.assertEqual(self.display.preparing_label, "Preparando")
        self.assertEqual(self.display.almost_ready_label, "Casi Listo")
        self.assertEqual(self.display.ready_label, "Listo")

    def test_only_matching_categories_are_sent(self):
        order = self._create_order([(self.product_food, 2), (self.product_drink, 1)])
        prep_order = self._process_order(order)
        self.assertTrue(prep_order)
        self.assertEqual(len(prep_order.prep_line_ids), 1)
        self.assertEqual(prep_order.prep_line_ids.product_id, self.product_food)
        self.assertEqual(len(prep_order.prep_line_ids.state_ids), 1)
        self.assertEqual(
            prep_order.prep_line_ids.state_ids.stage_id,
            self.display.stage_ids.sorted(lambda stage: stage.sequence)[0],
        )

    def test_processing_is_idempotent(self):
        order = self._create_order([(self.product_food, 1)])
        self._process_order(order)
        self._process_order(order)
        prep_orders = self.env["pos.prep.order"].search([("pos_order_id", "=", order.id)])
        self.assertEqual(len(prep_orders), 1)
        self.assertEqual(len(prep_orders.prep_line_ids), 1)
        self.assertEqual(len(prep_orders.prep_line_ids.state_ids), 1)

    def test_quantity_changes_and_cancellation(self):
        order = self._create_order([(self.product_food, 2)])
        prep_order = self._process_order(order)
        line = prep_order.prep_line_ids
        self.assertEqual(line.quantity - line.cancelled, 2)

        order.lines[0].qty = 3
        self._process_order(order)
        self.assertEqual(line.quantity - line.cancelled, 3)

        order.lines[0].qty = 1
        self._process_order(order)
        self.assertEqual(line.quantity - line.cancelled, 1)
        self.assertEqual(line.cancelled, 2)

        self._process_order(order, {"cancelled": True})
        self.assertEqual(line.quantity - line.cancelled, 0)
        self.assertEqual(line.cancelled, 3)
        self.assertFalse(self.display.get_display_data()["orders"])
        public = self.display._get_public_orders()
        self.assertFalse(public["preparing"])
        self.assertFalse(public["almost_ready"])
        self.assertFalse(public["ready"])

    def test_manual_stage_flow(self):
        order = self._create_order([(self.product_food, 1)])
        prep_order = self._process_order(order)
        state = prep_order.prep_line_ids.state_ids
        stages = self.display.stage_ids.sorted(lambda stage: stage.sequence)

        self.env["pos.prep.order"].advance_order(prep_order.id, self.display.id, 1)
        self.assertEqual(state.stage_id, stages[1])

        self.env["pos.prep.order"].complete_order(prep_order.id, self.display.id)
        self.assertEqual(state.stage_id, stages[2])
        self.assertFalse(state.todo)
        self.assertGreaterEqual(prep_order.completion_time, 0)

        self.env["pos.prep.order"].reset_order(prep_order.id, self.display.id)
        self.assertEqual(state.stage_id, stages[0])
        self.assertTrue(state.todo)

    def test_table_label_includes_merged_tables(self):
        floor = self.env["restaurant.floor"].create({"name": "Test Floor"})
        table_1 = self.env["restaurant.table"].create({"floor_id": floor.id, "table_number": 1})
        table_2 = self.env["restaurant.table"].create({"floor_id": floor.id, "table_number": 2})
        table_3 = self.env["restaurant.table"].create({"floor_id": floor.id, "table_number": 3})
        order = self._create_order([(self.product_food, 1)], table=table_2)
        prep_order = self._process_order(order)

        self.assertEqual(prep_order._get_table_label(), "2")

        table_1.parent_id = table_2
        self.assertEqual(prep_order._get_table_label(), "2 y 1")

        table_3.parent_id = table_2
        self.assertEqual(prep_order._get_table_label(), "2 y 1 y 3")

        table_1.parent_id = False
        table_2.parent_id = table_1
        order.table_id = table_1
        self.assertEqual(prep_order._get_table_label(), "1 y 2 y 3")

    def test_public_screen_three_columns(self):
        order = self._create_order([(self.product_food, 1), (self.product_food, 1)])
        prep_order = self._process_order(order)
        stages = self.display.stage_ids.sorted(lambda stage: stage.sequence)
        states = prep_order.prep_line_ids.state_ids

        data = self.display._get_public_orders()
        self.assertEqual(len(data["preparing"]), 1)
        self.assertEqual(len(data["almost_ready"]), 0)
        self.assertEqual(len(data["ready"]), 0)

        states[0].write(
            {
                "stage_id": stages[1].id,
                "last_stage_change": fields.Datetime.now(),
            }
        )
        data = self.display._get_public_orders()
        self.assertEqual(len(data["preparing"]), 0)
        self.assertEqual(len(data["almost_ready"]), 1)
        self.assertEqual(len(data["ready"]), 0)

        states.write(
            {
                "stage_id": stages[1].id,
                "last_stage_change": fields.Datetime.now(),
            }
        )
        data = self.display._get_public_orders()
        self.assertEqual(len(data["preparing"]), 0)
        self.assertEqual(len(data["almost_ready"]), 0)
        self.assertEqual(len(data["ready"]), 1)
        self.assertEqual(data["labels"]["almost_ready"], "Casi Listo")

    def test_public_token(self):
        order = self._create_order([(self.product_food, 1)])
        self._process_order(order)
        data = self.env["pos.prep.display"].get_order_status_data(self.display.access_token)
        self.assertTrue(data)
        self.assertFalse(self.env["pos.prep.display"].get_order_status_data("invalid-token"))

    def _ui_order_data(self, qty=1):
        uuid = str(uuid4())
        total = qty * self.product_food.list_price
        return {
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "amount_tax": 0.0,
            "amount_total": total,
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False,
            "pricelist_id": self.config.pricelist_id.id,
            "name": f"Order {uuid}",
            "last_order_preparation_change": "{}",
            "lines": [
                (
                    0,
                    0,
                    {
                        "id": 1,
                        "pack_lot_ids": [],
                        "price_unit": self.product_food.list_price,
                        "product_id": self.product_food.id,
                        "price_subtotal": total,
                        "price_subtotal_incl": total,
                        "qty": qty,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
            "partner_id": False,
            "session_id": self.session.id,
            "payment_ids": [],
            "uuid": uuid,
            "user_id": self.env.uid,
            "to_invoice": False,
            "state": "draft",
        }

    def test_unpaid_order_is_sent_on_sync(self):
        order_data = self._ui_order_data(2)
        result = self.env["pos.order"].sync_from_ui([order_data])
        order = self.env["pos.order"].browse(result["pos.order"][0]["id"])
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.amount_paid, 0.0)
        prep_order = self.env["pos.prep.order"].search([("pos_order_id", "=", order.id)], limit=1)
        self.assertTrue(prep_order)
        self.assertEqual(prep_order.prep_line_ids.quantity, 2)
        self.assertTrue(prep_order.prep_line_ids.state_ids)

    def test_cancelled_order_is_sent_with_context(self):
        order_data = self._ui_order_data(1)
        result = self.env["pos.order"].sync_from_ui([order_data])
        order = self.env["pos.order"].browse(result["pos.order"][0]["id"])
        prep_order = self.env["pos.prep.order"].search([("pos_order_id", "=", order.id)], limit=1)
        self.assertTrue(prep_order)

        self.env["pos.order"].with_context(
            preparation={"process_order_options": {"cancelled": True}}
        ).sync_from_ui([order_data])
        prep_line = prep_order.prep_line_ids
        self.assertEqual(prep_line.cancelled, prep_line.quantity)

    def test_reset_all_orders(self):
        order = self._create_order([(self.product_food, 1)])
        prep_order = self._process_order(order)
        self.env["pos.prep.order"].complete_order(prep_order.id, self.display.id)
        self.assertTrue(prep_order.prep_line_ids.state_ids)
        self.display.reset_all_orders()
        self.assertFalse(prep_order.prep_line_ids.state_ids)
