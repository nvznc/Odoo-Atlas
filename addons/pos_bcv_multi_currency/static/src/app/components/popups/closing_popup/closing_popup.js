import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { formatCurrency } from "@web/core/currency";
import { parseFloat } from "@web/views/fields/parsers";

ClosePosPopup.props = [...ClosePosPopup.props, "bcv_cash_details?"];

patch(ClosePosPopup.prototype, {
    getInitialState() {
        const state = super.getInitialState(...arguments);
        if (this.props.bcv_cash_details?.id) {
            state.payments[this.props.bcv_cash_details.id] = {
                counted: "0",
            };
        }
        for (const method of this.props.non_cash_payment_methods) {
            if (method.type === "bank") {
                state.payments[method.id] = {
                    counted: this.formatMethodCount(method, method.amount),
                };
            }
        }
        return state;
    },
    get bcvCurrencyId() {
        return (
            this.props.bcv_cash_details?.currency_id ||
            this.pos.session?.raw?.bcv_currency_id ||
            false
        );
    },
    get bcvRate() {
        return Number(this.pos.session?.raw?.bcv_rate) || 1;
    },
    methodCurrencyId(method) {
        return method?.currency_id || this.pos.currency.id;
    },
    formatMethodAmount(method, amount) {
        return formatCurrency(amount, this.methodCurrencyId(method));
    },
    formatMethodCount(method, amount) {
        return formatCurrency(amount, this.methodCurrencyId(method), {
            noSymbol: true,
        });
    },
    isBcvMethod(method) {
        return Boolean(
            method?.currency_id &&
                this.bcvCurrencyId &&
                method.currency_id === this.bcvCurrencyId
        );
    },
    toCompanyCurrency(amount, method) {
        return this.isBcvMethod(method) &&
            this.bcvRate &&
            this.pos.currency.id !== this.bcvCurrencyId
            ? amount / this.bcvRate
            : amount;
    },
    formatBcv(amount) {
        const details = this.props.bcv_cash_details;
        return details?.currency_id
            ? formatCurrency(amount, details.currency_id)
            : `${amount}`;
    },
    autoFillBcvCount() {
        const details = this.props.bcv_cash_details;
        this.state.payments[details.id].counted = this.formatMethodCount(
            details,
            details.amount
        );
    },
    autoFillPMCount(paymentId) {
        const method = this.props.non_cash_payment_methods.find(
            (pm) => pm.id === paymentId
        );
        if (!method) {
            return super.autoFillPMCount(...arguments);
        }
        this.state.payments[paymentId].counted = this.formatMethodCount(
            method,
            method.amount
        );
    },
    getPaymentMethod(paymentId) {
        if (this.props.bcv_cash_details?.id === paymentId) {
            return this.props.bcv_cash_details;
        }
        if (this.props.default_cash_details?.id === paymentId) {
            return this.props.default_cash_details;
        }
        return this.props.non_cash_payment_methods.find(
            (pm) => pm.id === paymentId
        );
    },
    getDifference(paymentId) {
        if (
            this.props.bcv_cash_details &&
            paymentId === this.props.bcv_cash_details.id
        ) {
            const counted = this.state.payments[paymentId].counted;
            if (!this.env.utils.isValidFloat(counted)) {
                return NaN;
            }
            return parseFloat(counted) - this.props.bcv_cash_details.amount;
        }
        return super.getDifference(...arguments);
    },
    getMaxDifference() {
        const paymentIds = Object.keys(this.state.payments).map(Number);
        if (!paymentIds.length) {
            return 0;
        }
        return Math.max(
            ...paymentIds.map((paymentId) => {
                const difference = this.getDifference(paymentId);
                return Math.abs(
                    this.toCompanyCurrency(
                        difference,
                        this.getPaymentMethod(paymentId)
                    )
                );
            })
        );
    },
    get bankPaymentMethodDiffPairs() {
        return this.props.non_cash_payment_methods
            .filter((pm) => pm.type === "bank")
            .map((pm) => [
                pm.id,
                this.toCompanyCurrency(this.getDifference(pm.id), pm),
            ]);
    },
    async closeSession() {
        const dataService = this.pos.data;
        const originalCall = dataService.call;
        if (this.props.bcv_cash_details) {
            dataService.call = (model, method, args, kwargs = {}) => {
                if (model === "pos.session" && method === "post_closing_cash_details") {
                    kwargs = {
                        ...kwargs,
                        counted_cash_bcv: parseFloat(
                            this.state.payments[this.props.bcv_cash_details.id].counted
                        ),
                    };
                }
                return originalCall.call(dataService, model, method, args, kwargs);
            };
        }
        try {
            return await super.closeSession(...arguments);
        } finally {
            dataService.call = originalCall;
        }
    },
});
