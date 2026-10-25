"""Extend preparation printers with a jIotBox direct print type."""

from __future__ import annotations

from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .jiotbox_url import (
    MAX_URL_LENGTH,
    JiotBoxUrlError,
    normalize_jiotbox_url,
    validate_jiotbox_url,
)


class PosPrinter(models.Model):
    """Add a jIotBox URL and printer type to preparation printers."""

    _inherit = "pos.printer"

    printer_type = fields.Selection(
        selection_add=[("jiotbox", "Direct print (jIotBox)")],
        ondelete={"jiotbox": "set default"},
    )
    jiotbox_url = fields.Char(
        string="jIotBox URL",
        size=MAX_URL_LENGTH,
        help=(
            "URL of the jIotBox local agent used to print kitchen tickets, for example "
            "https://192.168.1.50:8443. An optional base path can select a specific printer."
        ),
    )

    @api.model
    def _load_pos_data_fields(self, config: models.BaseModel) -> list[str]:
        """Return the POS data fields, including the jIotBox URL."""
        fields_list = super()._load_pos_data_fields(config)
        if "jiotbox_url" not in fields_list:
            fields_list = [*fields_list, "jiotbox_url"]
        return fields_list

    @api.constrains("printer_type", "jiotbox_url")
    def _constrain_jiotbox_url(self) -> None:
        """Ensure jIotBox printers have a valid agent URL."""
        for printer in self:
            if printer.printer_type != "jiotbox":
                continue
            if not printer.jiotbox_url:
                raise ValidationError(_("The jIotBox URL is required for a jIotBox printer."))
            try:
                validate_jiotbox_url(printer.jiotbox_url)
            except JiotBoxUrlError as error:
                raise ValidationError(str(error)) from error

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> models.BaseModel:
        """Normalize the jIotBox URL before creating printers."""
        for values in vals_list:
            if values.get("jiotbox_url"):
                values["jiotbox_url"] = self._normalize_url(values["jiotbox_url"])
        return super().create(vals_list)

    def write(self, vals: dict[str, Any]) -> bool:
        """Normalize the jIotBox URL before updating printers."""
        if vals.get("jiotbox_url"):
            vals["jiotbox_url"] = self._normalize_url(vals["jiotbox_url"])
        return super().write(vals)

    @api.model
    def _normalize_url(self, url: str | None) -> str:
        """Normalize a URL and convert helper errors into validation errors."""
        try:
            return normalize_jiotbox_url(url)
        except JiotBoxUrlError as error:
            raise ValidationError(str(error)) from error
