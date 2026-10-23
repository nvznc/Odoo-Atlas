import { Component, useState, whenReady } from "@odoo/owl";
import { mountComponent } from "@web/env";
import { useOrderStatus } from "./status_service";

export class StatusColumn extends Component {
    static template = "pos_preparation_display_atlas.StatusColumn";
    static props = {
        title: String,
        orders: Array,
        tone: String,
    };
}

export class OrderStatusApp extends Component {
    static template = "pos_preparation_display_atlas.OrderStatus";
    static components = { StatusColumn };

    setup() {
        this.orderStatus = useOrderStatus();
        this.state = useState(this.orderStatus.state);
    }

    get data() {
        return this.state.data;
    }

    get clockLabel() {
        return new Date(this.state.now).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    get columns() {
        return [
            {
                key: "preparing",
                title: this.data.labels.preparing || "Preparando",
                orders: this.data.preparing || [],
                tone: "preparing",
            },
            {
                key: "almost_ready",
                title: this.data.labels.almost_ready || "Casi Listo",
                orders: this.data.almost_ready || [],
                tone: "almost",
            },
            {
                key: "ready",
                title: this.data.labels.ready || "Listo",
                orders: this.data.ready || [],
                tone: "ready",
            },
        ];
    }
}

whenReady(() => mountComponent(OrderStatusApp, document.body));
