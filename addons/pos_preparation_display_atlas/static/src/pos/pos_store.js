import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async sendOrderInPreparation(order, opts = {}) {
        const result = await super.sendOrderInPreparation(order, opts);
        if (!this.config.prep_display_enabled || !this.models["pos.prep.display"]?.getAll().length) {
            return result;
        }

        const processOrderOptions = {
            general_customer_note: order.general_customer_note || "",
            internal_note: order.internal_note || "[]",
            cancelled: Boolean(opts.cancelled),
            fired_course_id: opts.firedCourseId || false,
        };

        try {
            if (opts.cancelled) {
                if (order.id) {
                    await this.data.call("pos.prep.order", "process_order", [
                        order.id,
                        processOrderOptions,
                    ]);
                }
            } else {
                await this.syncAllOrders({
                    orders: [order],
                    force: true,
                    context: {
                        preparation: {
                            process_order_options: processOrderOptions,
                        },
                    },
                });
                if (typeof order.updateSavedQuantity === "function") {
                    order.updateSavedQuantity();
                }
            }
        } catch (error) {
            console.error("Failed to send the order to the preparation display", error);
            this.notification?.add(
                "No se pudo enviar el pedido a la pantalla de preparación.",
                { type: "danger" }
            );
        }
        return result;
    },
});
