# Odoo-Atlas

Repositorio del proyecto Odoo Atlas.

## Documentación

- [Registro de cambios](CAMBIOS.md)
- [Auditoría, implementación y despliegue](AUDIT_DEPLOY_20261023.md)

## Addons

- `currency_rate_bcv`: tasa oficial BCV.
- `pos_bcv_multi_currency`: multi-moneda BCV en el POS.
- `pos_preparation_display_atlas`: pantalla de preparación y estado público de pedidos
  para Odoo 19 Community. Ver el [README del addon](addons/pos_preparation_display_atlas/README.md)
  y la sección 11 de [CAMBIOS.md](CAMBIOS.md#11-módulo-pos-preparation-display-2026-10-23).
- `Atlas-box`: Aplicación escrita en C# para capturar las impresoras conectadas via usb y virtualizarlas como IP
- `pos_kitchen_direct_print`: impresión directa de comandas y tickets del POS en
  impresoras locales/USB mediante jIotBox, sin IoT Box. Ver el
  [README del addon](addons/pos_kitchen_direct_print/README.rst) y la sección 12
  de [CAMBIOS.md](CAMBIOS.md#12-módulo-pos-kitchen-direct-print-jiotbox-2026-10-25).
- `atlas_odoo_studio`: editor visual clean-room para modelos, campos, vistas,
  menús y permisos en Odoo 19 Community. Ver la sección 14 de
  [CAMBIOS.md](CAMBIOS.md#14-addon-atlas-odoo-studio-2026-10-26).
