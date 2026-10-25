"""Extend Point of Sale configurations with an optional jIotBox receipt URL."""

from __future__ import annotations

from typing import Any

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .jiotbox_url import (
    MAX_URL_LENGTH,
    JiotBoxUrlError,
    normalize_jiotbox_url,
    validate_jiotbox_url,
)


class PosConfig(models.Model):
    """Add an optional jIotBox customer receipt URL to the Point of Sale."""

    _inherit = "pos.config"

    jiotbox_customer_receipt_url = fields.Char(
        string="jIotBox receipt URL",
        size=MAX_URL_LENGTH,
        help=(
            "Optional URL of the jIotBox local agent used to print customer receipts, "
            "for example https://192.168.1.50:8443/receipt."
        ),
    )

    @api.model
    def _load_pos_data_fields(self, config: models.BaseModel) -> list[str]:
        """Return the POS data fields, including the optional receipt URL."""
        fields_list = super()._load_pos_data_fields(config)
        if fields_list and "jiotbox_customer_receipt_url" not in fields_list:
            fields_list = [*fields_list, "jiotbox_customer_receipt_url"]
        return fields_list

    @api.constrains("jiotbox_customer_receipt_url")
    def _constrain_jiotbox_customer_receipt_url(self) -> None:
        """Ensure the optional jIotBox receipt URL is valid when provided."""
        for config in self:
            if not config.jiotbox_customer_receipt_url:
                continue
            try:
                validate_jiotbox_url(config.jiotbox_customer_receipt_url)
            except JiotBoxUrlError as error:
                raise ValidationError(str(error)) from error

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> models.BaseModel:
        """Normalize the jIotBox receipt URL before creating configurations."""
        for values in vals_list:
            if values.get("jiotbox_customer_receipt_url"):
                values["jiotbox_customer_receipt_url"] = self._normalize_url(
                    values["jiotbox_customer_receipt_url"]
                )
        return super().create(vals_list)

    def write(self, vals: dict[str, Any]) -> bool:
        """Normalize the jIotBox receipt URL before updating configurations."""
        if vals.get("jiotbox_customer_receipt_url"):
            vals["jiotbox_customer_receipt_url"] = self._normalize_url(
                vals["jiotbox_customer_receipt_url"]
            )
        return super().write(vals)

    @api.model
    def _normalize_url(self, url: str | None) -> str:
        """Normalize a URL and convert helper errors into validation errors."""
        try:
            return normalize_jiotbox_url(url)
        except JiotBoxUrlError as error:
            raise ValidationError(str(error)) from error
