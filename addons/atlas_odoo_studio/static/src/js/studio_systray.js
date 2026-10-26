import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

export class StudioSystrayItem extends Component {
    static template = "atlas_odoo_studio.SystrayItem";
    static props = {};

    setup() {
        this.action = useService("action");
        this.state = useState({ visible: false });
        onWillStart(async () => {
            this.state.visible = await user.hasGroup(
                "atlas_odoo_studio.group_studio_designer"
            );
        });
    }

    async openStudio() {
        const controller = this.action.currentController;
        const currentAction = controller?.action || {};
        const viewType = controller?.view?.type || currentAction.view_mode?.split(",")[0] || "form";
        const viewId =
            (currentAction.views || []).find(([, type]) => type === viewType)?.[0] || false;
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "atlas_odoo_studio.editor",
            params: {
                model: currentAction.res_model || "",
                viewType,
                viewId,
                previousControllerJsId: controller?.jsId || false,
            },
        });
    }
}

export const studioSystrayItem = {
    Component: StudioSystrayItem,
};

registry.category("systray").add("atlas_odoo_studio.studio", studioSystrayItem, {
    sequence: 50,
});
