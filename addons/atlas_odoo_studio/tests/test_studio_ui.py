from __future__ import annotations

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install", "atlas_studio", "atlas_studio_ui")
class TestStudioUI(HttpCase):
    """Pruebas de humo del editor OWL en un navegador real."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = new_test_user(
            cls.env,
            login="atlas_ui",
            password="atlas_ui",
            groups="base.group_user,atlas_odoo_studio.group_studio_designer",
        )

    def _browser_js(self, url_path: str, code: str, success_signal: str) -> None:
        self.browser_js(
            url_path,
            code,
            login=self.designer.login,
            timeout=120,
            success_signal=success_signal,
        )

    def test_editor_renders_and_selects_node(self):
        code = """
            (async () => {
                const fail = (message) => {
                    throw new Error(`[ATLAS_UI] FAIL ${message}`);
                };
                const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
                const waitFor = async (predicate, message, timeout = 30000) => {
                    const deadline = Date.now() + timeout;
                    while (Date.now() < deadline) {
                        const value = predicate();
                        if (value) {
                            return value;
                        }
                        await sleep(100);
                    }
                    return fail(message);
                };
                try {
                    const root = await waitFor(() => {
                        const alert = document.querySelector(".o_atlas_alert");
                        if (alert) {
                            throw new Error(alert.textContent.trim());
                        }
                        const candidate = document.querySelector(".o_atlas_studio");
                        if (!candidate) {
                            return null;
                        }
                        const hasNodes = candidate.querySelectorAll(
                            ".o_atlas_tree .o_atlas_node"
                        ).length;
                        const hasFields = candidate.querySelectorAll(
                            ".o_atlas_field_list .o_atlas_field"
                        ).length;
                        return hasNodes && hasFields ? candidate : null;
                    }, "editor not rendered");
                    await sleep(500);
                    const xmlTab = root.querySelectorAll(".o_atlas_tab")[1];
                    if (!xmlTab) {
                        fail("xml tab missing");
                    }
                    xmlTab.click();
                    await waitFor(
                        () => document.querySelector(".o_atlas_xml"),
                        "xml panel not rendered"
                    );
                    const line = document.querySelector(
                        ".o_atlas_tree .o_atlas_node_line"
                    );
                    if (!line) {
                        fail("tree line missing");
                    }
                    line.click();
                    await waitFor(
                        () => document.querySelector(".o_atlas_attributes"),
                        "attributes panel not rendered"
                    );
                    await waitFor(
                        () => document.querySelector(".o_atlas_node_selected"),
                        "selected node class not rendered"
                    );
                    console.log("[ATLAS_UI] OK");
                } catch (error) {
                    console.error(error.message || String(error));
                }
            })();
        """
        self._browser_js(
            "/odoo/action-atlas_odoo_studio.action_studio_editor",
            code,
            "[ATLAS_UI] OK",
        )

    def test_systray_opens_editor(self):
        code = """
            (async () => {
                const fail = (message) => {
                    throw new Error(`[ATLAS_SYSTRAY] FAIL ${message}`);
                };
                const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
                const waitFor = async (predicate, message, timeout = 30000) => {
                    const deadline = Date.now() + timeout;
                    while (Date.now() < deadline) {
                        const value = predicate();
                        if (value) {
                            return value;
                        }
                        await sleep(100);
                    }
                    return fail(message);
                };
                try {
                    const button = await waitFor(
                        () => document.querySelector(".o_atlas_systray"),
                        "systray button not visible for designer"
                    );
                    button.click();
                    await waitFor(() => {
                        const alert = document.querySelector(".o_atlas_alert");
                        if (alert) {
                            throw new Error(alert.textContent.trim());
                        }
                        const root = document.querySelector(".o_atlas_studio");
                        if (!root) {
                            return null;
                        }
                        return root.querySelectorAll(
                            ".o_atlas_tree .o_atlas_node"
                        ).length
                            ? root
                            : null;
                    }, "editor did not open from systray");
                    console.log("[ATLAS_SYSTRAY] OK");
                } catch (error) {
                    console.error(error.message || String(error));
                }
            })();
        """
        self._browser_js("/odoo", code, "[ATLAS_SYSTRAY] OK")
