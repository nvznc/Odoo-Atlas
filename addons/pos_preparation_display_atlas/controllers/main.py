import json

import werkzeug
from odoo import http
from odoo.http import request


class PosPreparationDisplayController(http.Controller):
    """Serve kitchen and public preparation display routes."""

    def _get_display_by_id(self, display_id):
        try:
            display_id = int(display_id)
        except (TypeError, ValueError):
            return request.env["pos.prep.display"]
        return request.env["pos.prep.display"].search(
            [("id", "=", display_id)],
            limit=1,
        )

    def _get_display_by_token(self, access_token):
        if not access_token:
            return request.env["pos.prep.display"]
        return (
            request.env["pos.prep.display"]
            .sudo()
            .search(
                [("access_token", "=", access_token), ("active", "=", True)],
                limit=1,
            )
        )

    @http.route(
        ["/pos_preparation_display/web", "/pos_preparation_display/web/"],
        type="http",
        auth="user",
        methods=["GET"],
    )
    def preparation_display(self, display_id=None, **kwargs):
        """Render the authenticated kitchen screen."""
        display = self._get_display_by_id(display_id)
        if not display:
            raise werkzeug.exceptions.NotFound()
        display.sudo()._ensure_access_token()
        session_info = request.env["ir.http"].session_info()
        session_info["prep_display"] = {
            "id": display.id,
            "name": display.name,
            "access_token": display.access_token,
        }
        return request.render(
            "pos_preparation_display_atlas.prep_display_index",
            {
                "session_info": session_info,
                "prep_display": session_info["prep_display"],
            },
        )

    @http.route(
        ["/pos-order-tracking", "/pos-order-tracking/"],
        type="http",
        auth="public",
        methods=["GET"],
    )
    def order_status_display(self, access_token=None, **kwargs):
        """Render the public order status screen."""
        display = self._get_display_by_token(access_token)
        if not display:
            raise werkzeug.exceptions.NotFound()
        initial_data = display._get_public_orders()
        session_info = request.env["ir.http"].session_info()
        session_info.update(
            {
                "prep_display": {
                    "id": display.id,
                    "name": display.name,
                    "access_token": display.access_token,
                    "auto_clear": display.auto_clear,
                    "clear_time_interval": display.clear_time_interval,
                },
                "initial_data": initial_data,
                "db": request.env.cr.dbname,
            }
        )
        return request.render(
            "pos_preparation_display_atlas.order_status_index",
            {"session_info": session_info, "initial_data": initial_data},
        )

    @http.route(
        "/pos-order-tracking/data",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def order_status_data(self, access_token=None, **kwargs):
        """Return the public order status payload as JSON."""
        display = self._get_display_by_token(access_token)
        if not display:
            raise werkzeug.exceptions.NotFound()
        payload = display._get_public_orders()
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )
