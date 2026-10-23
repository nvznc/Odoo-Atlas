import { Component, useState, whenReady } from "@odoo/owl";
import { mountComponent } from "@web/env";
import { usePreparationDisplay } from "./kitchen_service";

export class OrderCard extends Component {
    static template = "pos_preparation_display_atlas.OrderCard";
    static props = {
        order: Object,
        now: Number,
    };

    setup() {
        this.preparationDisplay = usePreparationDisplay();
        this.state = useState(this.preparationDisplay.state);
    }

    get order() {
        return this.props.order;
    }

    get elapsedMinutes() {
        const started = new Date(
            this.props.order.stage_started_at.replace(" ", "T") + "Z"
        ).getTime();
        return Math.max(0, Math.floor((this.props.now - started) / 60000));
    }

    get elapsedLabel() {
        const started = new Date(
            this.props.order.stage_started_at.replace(" ", "T") + "Z"
        ).getTime();
        const total = Math.max(0, Math.floor((this.props.now - started) / 1000));
        const minutes = String(Math.floor(total / 60)).padStart(2, "0");
        const seconds = String(total % 60).padStart(2, "0");
        return `${minutes}:${seconds}`;
    }

    get isLate() {
        const stage = this.state.stages.find(
            (item) => item.id === this.props.order.stage_id
        );
        return Boolean(stage?.alert_timer) && this.elapsedMinutes >= stage.alert_timer;
    }

    get lastStage() {
        const stages = this.state.stages;
        return stages[stages.length - 1];
    }

    get isCompleted() {
        return this.lastStage?.id === this.props.order.stage_id;
    }

    get lines() {
        return this.props.order.lines;
    }

    async advance() {
        if (this.isCompleted) {
            return;
        }
        await this.preparationDisplay.advance(this.props.order);
    }

    async reset() {
        await this.preparationDisplay.reset(this.props.order);
    }

    async complete() {
        await this.preparationDisplay.complete(this.props.order);
    }

    async toggleLine(line) {
        await this.preparationDisplay.toggleLine(line);
    }
}

export class PreparationDisplayApp extends Component {
    static template = "pos_preparation_display_atlas.PreparationDisplay";
    static components = { OrderCard };

    setup() {
        this.preparationDisplay = usePreparationDisplay();
        this.state = useState(this.preparationDisplay.state);
    }

    get stages() {
        return this.state.stages;
    }

    get selectedStageId() {
        return this.state.selectedStageId;
    }

    get visibleOrders() {
        if (!this.selectedStageId) {
            return this.state.orders;
        }
        return this.state.orders.filter(
            (order) => order.stage_id === this.selectedStageId
        );
    }

    stageCount(stageId) {
        return this.state.orders.filter((order) => order.stage_id === stageId).length;
    }

    selectStage(stageId) {
        this.state.selectedStageId = stageId;
    }

    async resetAll() {
        if (window.confirm("¿Eliminar todos los pedidos activos de esta pantalla?")) {
            await this.preparationDisplay.resetAll();
        }
    }

    get stageButtonStyle() {
        return "";
    }
}

whenReady(() => mountComponent(PreparationDisplayApp, document.body));
