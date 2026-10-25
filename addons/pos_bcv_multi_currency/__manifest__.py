{
    "name": "POS BCV Multi Currency",
    "version": "19.0.1.0.4",
    "summary": "Cobro en bolívares con tasa BCV en el punto de venta",
    "description": """
Agrega soporte para cobrar en bolívares (VES) en el POS usando la tasa
oficial del BCV, manteniendo los pedidos y la contabilidad en USD.

Incluye tasa congelada por pedido, pagos en moneda extranjera y una caja
separada para el efectivo en bolívares.
""",
    "author": "Custom",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "account", "currency_rate_bcv"],
    "data": [
        "views/pos_config_views.xml",
        "views/pos_payment_method_views.xml",
        "views/pos_order_views.xml",
        "views/pos_payment_views.xml",
        "views/pos_session_views.xml",
        "views/report_saledetails_bcv.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_bcv_multi_currency/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
