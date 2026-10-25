import { _t } from "@web/core/l10n/translation";
import { getLNATargetAddressSpace } from "@point_of_sale/app/utils/init_lna";
import { HWPrinter } from "@point_of_sale/app/utils/printer/hw_printer";

const JIOTBOX_ACTION_PATH = "/hw_proxy/default_printer_action";
const JIOTBOX_TIMEOUT_MS = 15000;
const JIOTBOX_SCHEME_PATTERN = /^[a-z][a-z0-9+.-]*:\/\//i;

/**
 * Normalize the URL of a jIotBox so it can be used as a fetch base URL.
 * An empty value is left untouched, HTTPS is added when the protocol is
 * missing and trailing slashes are removed.
 *
 * @param {string} url raw URL entered in the Point of Sale settings
 * @returns {string} normalized URL, or an empty string when no URL is given
 */
export function normalizeJiotBoxUrl(url) {
    const value = String(url ?? "").trim();
    if (!value) {
        return "";
    }
    let normalized = value;
    if (!JIOTBOX_SCHEME_PATTERN.test(normalized)) {
        normalized = `https://${normalized}`;
    }
    return normalized.replace(/\/+$/, "");
}

/**
 * Printer that talks to a jIotBox through its `default_printer_action`
 * hardware proxy endpoint. Fetch is used instead of the Odoo RPC helper so
 * that Local Network Access target address spaces can be forwarded.
 */
export class JiotBoxPrinter extends HWPrinter {
    /**
     * @override
     * @param {Object} params
     * @param {string} params.url base URL of the jIotBox
     */
    setup({ url }) {
        super.setup({ url: normalizeJiotBoxUrl(url) });
        this.lnaTargetAddressSpace = getLNATargetAddressSpace(this.url);
    }

    /**
     * Send a hardware action to the jIotBox. Errors are stored on
     * `this.lastError` and never thrown so that BasePrinter can clear its
     * queue and display the corresponding error.
     *
     * @override
     * @param {Object} data action payload, e.g. `{ action: "cashbox" }`
     * @returns {Promise<{ result: boolean }>}
     */
    async sendAction(data) {
        this.lastError = null;
        if (!this.url) {
            this.lastError = { code: "JIOTBOX_NOT_CONFIGURED" };
            return { result: false };
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), JIOTBOX_TIMEOUT_MS);
        const params = {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { data },
                id: Date.now(),
            }),
            credentials: "omit",
            mode: "cors",
            signal: controller.signal,
        };
        if (odoo.use_lna) {
            params.targetAddressSpace = this.lnaTargetAddressSpace;
        }

        try {
            const response = await fetch(`${this.url}${JIOTBOX_ACTION_PATH}`, params);
            if (!response.ok) {
                this.lastError = {
                    code: "JIOTBOX_HTTP_ERROR",
                    status: response.status,
                };
                return { result: false };
            }

            const body = await response.json();
            if (body.error) {
                this.lastError = {
                    code: "JIOTBOX_REJECTED",
                    message: body.error.data?.message || body.error.message,
                };
                return { result: false };
            }
            if (body.result === false || body.result?.result === false) {
                this.lastError = { code: "JIOTBOX_REJECTED" };
                return { result: false };
            }
            return { result: true };
        } catch (error) {
            if (error.name === "AbortError") {
                this.lastError = { code: "JIOTBOX_TIMEOUT" };
            } else {
                this.lastError = {
                    code: "JIOTBOX_UNREACHABLE",
                    message: error.message,
                };
            }
            return { result: false };
        } finally {
            clearTimeout(timeout);
        }
    }

    /**
     * Build a retryable, user-facing error from `this.lastError`.
     *
     * @override
     * @returns {{ successful: boolean, canRetry: boolean, message: { title: string, body: string } }}
     */
    getResultsError() {
        const error = this.lastError || { code: "JIOTBOX_REJECTED" };
        let body;
        switch (error.code) {
            case "JIOTBOX_NOT_CONFIGURED":
                body = _t(
                    "No jIotBox URL is configured for this Point of Sale. Please set the jIotBox URL in the settings before retrying."
                );
                break;
            case "JIOTBOX_TIMEOUT":
                body = _t(
                    "The jIotBox at %s did not answer within %s seconds. Please check that it is powered on and connected to the network before retrying.",
                    this.url,
                    JIOTBOX_TIMEOUT_MS / 1000
                );
                break;
            case "JIOTBOX_UNREACHABLE":
                body = _t(
                    "The jIotBox at %s could not be reached. Please check the URL and that the device is on the same network before retrying.",
                    this.url
                );
                break;
            case "JIOTBOX_HTTP_ERROR":
                body = _t(
                    "The jIotBox at %s returned an HTTP error (status %s). Please check the device before retrying.",
                    this.url,
                    error.status
                );
                break;
            default:
                body = _t(
                    "The jIotBox at %s rejected the print request%s. Please check the printer connected to the jIotBox before retrying.",
                    this.url,
                    error.message ? ` (${error.message})` : ""
                );
        }
        return {
            successful: false,
            canRetry: true,
            message: {
                title: _t("Printing through jIotBox failed"),
                body,
            },
        };
    }
}
