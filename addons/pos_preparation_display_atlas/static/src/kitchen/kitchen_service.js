import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { getOnNotified } from "@point_of_sale/utils";

const preparationDisplayService = {
    dependencies: ["orm", "bus_service", "notification"],
    async start(env, { orm, bus_service, notification }) {
        const state = reactive({
            loading: true,
            display: {},
            stages: [],
            orders: [],
            selectedStageId: 0,
            now: Date.now(),
        });

        const displayId = odoo.prep_display.id;
        const accessToken = odoo.prep_display.access_token;

        const load = async () => {
            const data = await orm.call("pos.prep.display", "get_display_data", [
                [displayId],
            ]);
            state.display = data.display;
            state.stages = data.stages;
            state.orders = data.orders;
            state.loading = false;
        };

        const onNotified = getOnNotified(bus_service, accessToken);
        onNotified("LOAD_ORDERS", async () => {
            try {
                await load();
            } catch (error) {
                console.error("Unable to refresh the preparation display", error);
            }
        });
        bus_service.addEventListener("BUS:RECONNECT", () => {
            load().catch((error) => {
                console.error("Unable to refresh the preparation display", error);
            });
        });

        setInterval(() => {
            state.now = Date.now();
        }, 1000);

        await load();

        return {
            state,
            displayId,
            load,
            notification,
            async advance(order, direction = 1) {
                await orm.call("pos.prep.order", "advance_order", [
                    order.id,
                    displayId,
                    direction,
                ]);
                await load();
            },
            async reset(order) {
                await orm.call("pos.prep.order", "reset_order", [
                    order.id,
                    displayId,
                ]);
                await load();
            },
            async complete(order) {
                await orm.call("pos.prep.order", "complete_order", [
                    order.id,
                    displayId,
                ]);
                await load();
            },
            async toggleLine(line) {
                await orm.call("pos.prep.state", "toggle_state", [line.state_id]);
                await load();
            },
            async resetAll() {
                await orm.call("pos.prep.display", "reset_all_orders", [
                    [displayId],
                ]);
                await load();
            },
        };
    },
};

registry.category("services").add(
    "preparation_display",
    preparationDisplayService
);

export function usePreparationDisplay() {
    return useService("preparation_display");
}
