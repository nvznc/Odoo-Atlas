import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        const result = await super.addNewPaymentLine(...arguments);
        const line = this.selectedPaymentLine;
        if (result && line?.isVes?.()) {
            this.numberBuffer.set(line.paymentAmount.toString());
        }
        return result;
    },
    updateSelectedPaymentline(amount = false) {
        const line = this.selectedPaymentLine;
        if (!line?.isVes?.()) {
            return super.updateSelectedPaymentline(amount);
        }
        if (amount === false) {
            if (this.numberBuffer.get() === null) {
                amount = null;
            } else if (this.numberBuffer.get() === "") {
                amount = 0;
            } else {
                amount = this.numberBuffer.getFloat();
            }
        }
        const paymentTerminal = line.payment_method_id.payment_terminal;
        if (
            paymentTerminal &&
            !["pending", "retry"].includes(line.getPaymentStatus())
        ) {
            return;
        }
        if (amount === null) {
            this.deletePaymentLine(line.uuid);
        } else {
            line.setAmount(amount);
        }
    },
});
