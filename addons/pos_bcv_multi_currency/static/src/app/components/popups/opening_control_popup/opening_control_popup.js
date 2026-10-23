import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { ConnectionLostError } from "@web/core/network/rpc";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(OpeningControlPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.openingCashBcv = this.env.utils.formatCurrency(
            this.pos.session.cash_register_balance_start_bcv || 0,
            false
        );
    },
    get hasBcvCash() {
        return Boolean(
            this.pos.session.bcv_cash_control && this.pos.session.bcv_currency_id
        );
    },
    async confirm() {
        if (!this.hasBcvCash) {
            return super.confirm(...arguments);
        }
        try {
            await this.pos.data.call("pos.session", "set_opening_control", [
                this.pos.session.id,
                parseFloat(this.state.openingCash),
                this.state.notes,
                parseFloat(this.state.openingCashBcv),
            ]);
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                this.dialog.add(AlertDialog, {
                    title: _t("Connection Lost"),
                    body: _t(
                        "The register cannot be opened while offline. Please try again."
                    ),
                });
                return;
            }
            return this.pos.reloadIfSessionDeleted(error);
        }
        this.pos.session.update({
            state: "opened",
            cash_register_balance_start: parseFloat(this.state.openingCash),
            cash_register_balance_start_bcv: parseFloat(this.state.openingCashBcv),
        });
        this.props.close();
    },
});
