# Pantalla de preparación POS

Módulo para Odoo 19 Community que agrega una pantalla de cocina/bar y una
pantalla pública de estado de pedidos para televisores.

## Requisitos

- Odoo 19 Community.
- Módulos `point_of_sale` y `pos_restaurant`.
- Navegador con acceso a la red local de Odoo.

## Funcionalidad

- Pantalla de preparación autenticada con etapas configurables.
- Pantalla pública con columnas `Preparando`, `Casi listo` y `Listo`.
- Actualización en vivo mediante el bus de Odoo.
- Filtro por categorías de productos por pantalla.
- Selección de los puntos de venta que envían pedidos a cada pantalla.
- Temporizadores de alerta, tiempo promedio y limpieza automática de pedidos listos.
- Notas generales, notas internas, notas de cliente y atributos de producto.
- Soporte para líneas de combo.
- Botones para avanzar, completar y reiniciar pedidos.
- Botón `← Volver a Odoo` en la pantalla de preparación.
- Interfaz visible en español.
- Etiqueta de mesas combinadas en cocina y TV. Por ejemplo, una orden sobre las
  mesas 2 y 1 se muestra como `Mesa 2 y 1`, sin importar cuál sea la mesa padre.
- Total de comensales tomado de `pos.order.customer_count`. Odoo suma ese valor
  al combinar órdenes; el módulo no suma los asientos de las mesas.

## Instalación

1. Copiar `pos_preparation_display_atlas` dentro de un directorio de addons.
2. Actualizar la lista de aplicaciones.
3. Instalar **Pantalla de preparación POS**.

## Configuración

1. Ir a **Punto de venta → Configuración → Puntos de venta**.
2. Activar **Pantalla de preparación** en el POS que debe enviar pedidos.
3. Ir a **Punto de venta → Pantallas de preparación**.
4. Crear o editar una pantalla:
   - asignar compañía y puntos de venta;
   - seleccionar categorías (vacío significa todas);
   - definir etapas, colores y temporizadores;
   - configurar limpieza automática si se desea.
5. Abrir la pantalla desde los botones de la ficha.

## URLs

- Cocina, requiere sesión de Odoo:
  `/pos_preparation_display/web?display_id=<ID>`
- TV pública, usa el token de la pantalla:
  `/pos-order-tracking?access_token=<TOKEN>`

El token se consulta en la ficha de la pantalla de preparación y no debe
publicarse en documentación ni en repositorios.

## Pruebas

```bash
odoo -d odoo_prep_display_test -u pos_preparation_display_atlas \
  --test-enable --stop-after-init --http-port=8070 \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  --test-tags=/pos_preparation_display_atlas
```

La suite cubre creación y actualización de pedidos, cancelaciones, categorías,
etapas, pantalla pública, token, reinicio, idempotencia y mesas combinadas.

## Versión

`19.0.1.0.2`
