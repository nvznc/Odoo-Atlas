{
    "name": "POS Kitchen Direct Print (jIotBox)",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "author": "Odoo Atlas",
    "summary": "Print POS kitchen tickets on local or USB printers through jIotBox",
    "description": """
POS Kitchen Direct Print (jIotBox)
==================================

This module adds a new preparation printer type, *Direct print (jIotBox)*.
Kitchen tickets are rendered as raster images and sent directly from the
Point of Sale browser to a jIotBox local HTTP agent, which forwards them to a
local or USB printer. No Odoo IoT Box is required.

An optional jIotBox customer receipt URL can be configured on the Point of
Sale to print customer receipts through the same local agent.
""",
    "depends": ["point_of_sale"],
    "data": [
        "views/pos_printer_views.xml",
        "views/pos_config_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_kitchen_direct_print/static/src/app/**/*.js",
        ],
    },
    "installable": True,
}
