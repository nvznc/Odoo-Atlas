import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { formatCurrency } from "@web/core/currency";

patch(PosOrder.prototype, {
    get bcvCurrency() {
        const currencyId =
            this.raw.bcv_currency_id || this.config?.raw?.bcv_currency_id || false;
        return currencyId ? this.models["res.currency"].get(currencyId) : undefined;
    },
    get bcvRate() {
        const orderRate = Number(this.raw.bcv_rate) || 0;
        if (orderRate > 0) {
            return orderRate;
        }
        const sessionRate = Number(this.session?.raw?.bcv_rate) || 0;
        return sessionRate > 0 ? sessionRate : Number(this.config?.raw?.bcv_rate) || 0;
    },
    get bcvRateDate() {
        return this.raw.bcv_rate_date || this.session?.raw?.bcv_rate_date || false;
    },
    get hasBcv() {
        return Boolean(this.bcvCurrency && this.bcvRate > 0);
    },
    get bcvTotal() {
        if (!this.hasBcv) {
            return 0;
        }
        return this.bcvCurrency.round(this.totalDue * this.bcvRate);
    },
    get bcvPaid() {
        if (!this.hasBcv) {
            return 0;
        }
        return this.bcvCurrency.round(
            this.payment_ids.reduce((total, payment) => {
                if (payment.isVes?.() || payment.paymentCurrency?.id === this.bcvCurrency.id) {
                    return total + payment.paymentAmount;
                }
                return total;
            }, 0)
        );
    },
    get bcvRemainingDue() {
        if (!this.hasBcv) {
            return 0;
        }
        return this.bcvCurrency.round(this.remainingDue * this.bcvRate);
    },
    get bcvChange() {
        if (!this.hasBcv) {
            return 0;
        }
        return this.bcvCurrency.round((this.change || 0) * this.bcvRate);
    },
    get bcvTotalDisplay() {
        return this.hasBcv
            ? formatCurrency(this.bcvTotal, this.bcvCurrency.id)
            : "";
    },
    get bcvRemainingDueDisplay() {
        return this.hasBcv
            ? formatCurrency(this.bcvRemainingDue, this.bcvCurrency.id)
            : "";
    },
    get bcvPaidDisplay() {
        return this.hasBcv
            ? formatCurrency(this.bcvPaid, this.bcvCurrency.id)
            : "";
    },
    get bcvChangeDisplay() {
        return this.hasBcv ? formatCurrency(this.bcvChange, this.bcvCurrency.id) : "";
    },
    addPaymentline(paymentMethod) {
        const dueBefore = this.remainingDue;
        const result = super.addPaymentline(...arguments);
        if (!result?.status || !this.hasBcv) {
            return result;
        }
        const line = result.data;
        if (!line?.isVes?.()) {
            return result;
        }
        line.payment_currency_id = this.bcvCurrency;
        line.payment_rate = this.bcvRate;
        line.setAmount(this.bcvCurrency.round(dueBefore * this.bcvRate));
        return result;
    },
    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        if (this.hasBcv) {
            data.bcv_rate = this.bcvRate;
            data.bcv_rate_date = this.bcvRateDate;
        }
        return data;
    },
});
