{
    "name": "POS Preparation Display",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Preparation screen for kitchen and public order status screen",
    "description": """
Adds a preparation screen for kitchen/bar staff and a public order status
screen for customer-facing televisions.

This module is an independent implementation for Odoo Community. It does not
contain code from the Odoo Enterprise Edition.
""",
    "author": "Odoo Atlas",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "pos_restaurant"],
    "data": [
        "security/ir.model.access.csv",
        "security/preparation_display_security.xml",
        "views/preparation_display_views.xml",
        "views/preparation_display_templates.xml",
        "views/res_config_settings_views.xml",
        "data/preparation_display_cron.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_preparation_display_atlas/static/src/pos/**/*",
        ],
        "pos_preparation_display_atlas.assets": [
            ("include", "point_of_sale.base_app"),
            "point_of_sale/static/src/utils.js",
            "pos_preparation_display_atlas/static/src/kitchen/**/*",
        ],
        "pos_order_status_atlas.assets": [
            ("include", "point_of_sale.base_app"),
            "point_of_sale/static/src/utils.js",
            "pos_preparation_display_atlas/static/src/status/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
