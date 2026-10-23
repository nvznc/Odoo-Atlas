import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { getOnNotified } from "@point_of_sale/utils";

const orderStatusService = {
    dependencies: ["bus_service"],
    async start(env, { bus_service }) {
        const accessToken = odoo.order_status.prep_display.access_token;
        const initialData = odoo.initial_data || {};
        const state = reactive({
            data: {
                preparing: initialData.preparing || [],
                almost_ready: initialData.almost_ready || [],
                ready: initialData.ready || [],
                labels: initialData.labels || {
                    preparing: "Preparando",
                    almost_ready: "Casi Listo",
                    ready: "Listo",
                },
                display_name: initialData.display_name || "",
            },
            loading: !initialData,
            now: Date.now(),
        });

        const load = async () => {
            const response = await fetch(
                `/pos-order-tracking/data?access_token=${encodeURIComponent(accessToken)}`,
                { headers: { Accept: "application/json" } }
            );
            if (!response.ok) {
                return;
            }
            state.data = await response.json();
            state.loading = false;
        };

        const onNotified = getOnNotified(bus_service, accessToken);
        onNotified("NEW_ORDERS", () => {
            load().catch((error) =>
                console.error("Unable to refresh the order status screen", error)
            );
        });
        bus_service.addEventListener("BUS:RECONNECT", () => {
            load().catch((error) =>
                console.error("Unable to refresh the order status screen", error)
            );
        });

        setInterval(() => {
            state.now = Date.now();
        }, 1000);

        setInterval(() => {
            load().catch(() => {});
        }, 30000);

        await load();

        return { state };
    },
};

registry.category("services").add("order_status", orderStatusService);

export function useOrderStatus() {
    return useService("order_status");
}
