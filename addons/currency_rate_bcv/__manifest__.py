{
    "name": "BCV Currency Rate",
    "version": "19.0.1.0.0",
    "summary": "Actualiza la tasa oficial VES/USD desde bcv.org.ve",
    "description": """
Actualiza la tasa de cambio oficial del Banco Central de Venezuela (BCV)
para la moneda VES, usando USD como moneda base de la compañía.

Incluye un botón de actualización manual y un cron definido dentro del
módulo, inactivo por defecto. No sobrescribe las tasas marcadas como manuales.
""",
    "author": "Custom",
    "category": "Accounting/Localizations",
    "license": "LGPL-3",
    "depends": ["base", "account"],
    "data": [
        "data/ir_cron.xml",
        "views/res_currency_rate_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
