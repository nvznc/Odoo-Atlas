import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { formatCurrency } from "@web/core/currency";
import { parseFloat } from "@web/views/fields/parsers";

ClosePosPopup.props = [...ClosePosPopup.props, "bcv_cash_details"];

patch(ClosePosPopup.prototype, {
    getInitialState() {
        const state = super.getInitialState(...arguments);
        if (this.props.bcv_cash_details) {
            state.payments[this.props.bcv_cash_details.id] = {
                counted: "0",
            };
        }
        return state;
    },
    get bcvRate() {
        return Number(this.pos.session?.raw?.bcv_rate) || 1;
    },
    formatBcv(amount) {
        const details = this.props.bcv_cash_details;
        return details?.currency_id
            ? formatCurrency(amount, details.currency_id)
            : `${amount}`;
    },
    autoFillBcvCount() {
        const details = this.props.bcv_cash_details;
        this.state.payments[details.id].counted = this.env.utils.formatCurrency(
            details.amount,
            false
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
        if (!this.props.bcv_cash_details) {
            return super.getMaxDifference(...arguments);
        }
        return Math.max(
            ...Object.keys(this.state.payments).map((id) => {
                const difference = this.getDifference(parseInt(id));
                if (parseInt(id) === this.props.bcv_cash_details.id) {
                    return Math.abs(difference / this.bcvRate);
                }
                return Math.abs(difference);
            })
        );
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
