{
    "name": "Pantalla de preparación POS",
    "version": "19.0.1.0.2",
    "category": "Ventas/Punto de venta",
    "summary": "Pantalla de cocina y pantalla pública de estado de pedidos",
    "description": """
Agrega una pantalla de preparación para cocina/bar y una pantalla pública de
estado de pedidos para televisores orientados al cliente.

Este módulo es una implementación independiente para Odoo Community. No
contiene código de Odoo Enterprise Edition.
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
