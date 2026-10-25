import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { JiotBoxPrinter } from "../utils/printer/jiotbox_printer";

patch(PosStore.prototype, {
    /**
     * @override
     * @param {Object} config Point of Sale configuration
     * @returns {JiotBoxPrinter|Object} the printer selected for this configuration
     */
    createPrinter(config) {
        if (config.printer_type === "jiotbox") {
            return new JiotBoxPrinter({ url: config.jiotbox_url });
        }
        return super.createPrinter(...arguments);
    },

    /**
     * Install the jIotBox customer receipt printer after the server data has
     * been processed. When both a jIotBox customer receipt URL and an Epson
     * printer are configured, jIotBox intentionally takes priority for the
     * customer receipt.
     *
     * @override
     * @returns {Promise<Object>} the result of the parent implementation
     */
    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        if (this.config.jiotbox_customer_receipt_url) {
            this.hardwareProxy.printer = new JiotBoxPrinter({
                url: this.config.jiotbox_customer_receipt_url,
            });
        }
        return result;
    },
});
