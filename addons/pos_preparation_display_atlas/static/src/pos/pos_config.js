import { PosConfig } from "@point_of_sale/app/models/pos_config";
import { patch } from "@web/core/utils/patch";

patch(PosConfig.prototype, {
    get preparationDisplayCategories() {
        const displays = this.models["pos.prep.display"]?.getAll() || [];
        const allCategories = this.models["pos.category"]?.getAll() || [];
        return new Set(
            displays.flatMap((display) =>
                display.category_ids.length
                    ? display.category_ids
                    : allCategories.map((category) => category.id)
            )
        );
    },

    get preparationCategories() {
        let categories = super.preparationCategories;
        if (this.preparationDisplayCategories.size) {
            categories = new Set([
                ...categories,
                ...this.preparationDisplayCategories,
            ]);
        }
        return categories;
    },

    get displayTrackingNumber() {
        return (
            super.displayTrackingNumber ||
            Boolean(this.models["pos.prep.display"]?.getAll().length)
        );
    },
});
