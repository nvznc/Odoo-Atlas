import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
import { formatCurrency } from "@web/core/currency";

patch(PosPayment.prototype, {
    get paymentCurrency() {
        const methodCurrency = this.payment_method_id?.currency_id;
        if (this.pos_order_id?.bcvCurrency?.id === methodCurrency?.id) {
            return methodCurrency;
        }
        return (
            this.payment_currency_id ||
            methodCurrency ||
            this.pos_order_id?.currency
        );
    },
    get paymentRate() {
        if (this.isVes()) {
            const orderRate = Number(this.pos_order_id?.bcvRate) || 0;
            if (orderRate > 0) {
                return orderRate;
            }
            const storedRate = Number(this.payment_rate) || 0;
            return storedRate > 0 ? storedRate : 1;
        }
        const rate = Number(this.payment_rate) || 0;
        if (rate > 0) {
            return rate;
        }
        return this.pos_order_id?.currency_rate || 1;
    },
    get paymentAmount() {
        if (this.isVes()) {
            const storedRate = Number(this.payment_rate) || 0;
            if (
                this.payment_amount !== undefined &&
                this.payment_amount !== null &&
                storedRate > 0 &&
                Math.abs(storedRate - this.paymentRate) < 0.000001
            ) {
                return this.payment_amount;
            }
            const amount = this.getAmount() || 0;
            const converted = amount * this.paymentRate;
            return this.paymentCurrency ? this.paymentCurrency.round(converted) : converted;
        }
        if (this.payment_amount !== undefined && this.payment_amount !== null) {
            return this.payment_amount;
        }
        return this.getAmount() * this.paymentRate;
    },
    isVes() {
        const bcvCurrency = this.pos_order_id?.bcvCurrency;
        if (!bcvCurrency) {
            return false;
        }
        return [this.payment_currency_id, this.payment_method_id?.currency_id].some(
            (currency) => currency?.id === bcvCurrency.id
        );
    },
    isBcv() {
        return this.isVes();
    },
    get formattedPaymentAmount() {
        return this.paymentCurrency
            ? formatCurrency(this.paymentAmount, this.paymentCurrency.id)
            : "";
    },
    get formattedUsdAmount() {
        return formatCurrency(this.getAmount());
    },
    setAmount(value) {
        this.pos_order_id.assertEditable();
        const parsed = parseFloat(value) || 0;
        if (this.isBcv()) {
            const rate = this.paymentRate || 1;
            this.payment_currency_id = this.paymentCurrency;
            this.payment_rate = rate;
            this.payment_amount = this.paymentCurrency.round(parsed);
            this.amount = this.pos_order_id.currency.round(this.payment_amount / rate);
        } else {
            const amount = this.pos_order_id.currency.round(parsed);
            this.payment_currency_id = this.pos_order_id.currency;
            this.payment_rate = 1;
            this.payment_amount = amount;
            this.amount = amount;
        }
    },
    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        data.payment_currency_id = this.paymentCurrency?.id || false;
        data.payment_amount = this.paymentAmount;
        data.payment_rate = this.paymentRate;
        return data;
    },
});
