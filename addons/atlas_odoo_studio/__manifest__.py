{
    "name": "Atlas-Odoo-Studio",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "Editor visual de modelos, campos, vistas y menús para Odoo CE",
    "description": """
Atlas-Odoo-Studio es una implementación independiente de un editor visual
para Odoo 19 Community. Permite crear campos y modelos personalizados, añadir
campos a formularios y listas, crear menús y acciones, y mantener un historial
auditable de cada cambio.

No contiene código, XML, assets ni nombres internos de Odoo Enterprise.
""",
    "author": "Odoo Atlas",
    "website": "https://github.com/nvznc/Odoo-Atlas",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "security/studio_security.xml",
        "security/ir.model.access.csv",
        "views/studio_views.xml",
        "data/studio_actions.xml",
        "views/studio_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "atlas_odoo_studio/static/src/js/**/*",
            "atlas_odoo_studio/static/src/scss/studio.scss",
        ],
    },
    "installable": True,
    "application": True,
}
