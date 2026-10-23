# Registro de cambios — Odoo Atlas / BCV

Documento de traspaso para otras sesiones de trabajo. Resume qué se cambió, por qué,
cómo se probó, cómo se desplegó y cómo se subió a GitHub.

- **Fecha:** 2026-10-23
- **Repositorio:** <https://github.com/nvznc/Odoo-Atlas>
- **Remoto SSH:** `git@github.com:nvznc/Odoo-Atlas.git`
- **Rama:** `main`
- **Último commit de código:** `cbb6e7b`
- **Producción:** Odoo `19.0-20261015`, base de datos `odoo`
- **Estado:** contenedores healthy, HTTP 200, módulo POS en `19.0.1.0.2`

> Nota: `.env`, `backups/`, credenciales y archivos de datos **no** están en GitHub.
> El detalle técnico de la auditoría está en `AUDIT_DEPLOY_20261023.md`.

---

## 1. Resumen ejecutivo

Se completaron los 8 pasos de la auditoría de los addons `currency_rate_bcv` y
`pos_bcv_multi_currency`, se agregó el cálculo del vuelto en bolívares en la pantalla de
pago del POS, se desplegó todo en producción y se subió el proyecto a GitHub.

- **Auditoría:** 14/14 tests OK, Ruff sin errores, upgrade de ensayo y de producción OK.
- **Seguridad:** contraseña de PostgreSQL rotada y guardada en `.env` local con permisos `600`.
- **POS:** se muestra `Change Bs` con el vuelto convertido por la tasa BCV.
- **Incidente:** una primera versión del template del POS rompió la pantalla de pago; se
  corrigió el selector XPath y se desplegó la versión `19.0.1.0.2`.
- **GitHub:** 4 commits de código en `main` (incluido el commit inicial del repositorio).

---

## 2. Repositorio y uso de GitHub

### 2.1 Datos del repositorio

| Elemento | Valor |
|---|---|
| Repositorio canónico | `github.com/nvznc/Odoo-Atlas` |
| URL SSH | `git@github.com:nvznc/Odoo-Atlas.git` |
| Rama de trabajo | `main` |
| Commit inicial remoto | `9ff4aca` — `Initial commit` |
| Último commit de código | `f397f6f` — `Fix POS payment status template inheritance` |
| Archivos en el primer push | 49 (incluye `README.md` del repo inicial) |

GitHub redirigía desde el nombre en minúsculas `nvznc/odoo-atlas` hacia
`nvznc/Odoo-Atlas`. Por eso el remoto local se dejó apuntando a la URL canónica:

```bash
git remote -v
# origin  git@github.com:nvznc/Odoo-Atlas.git (fetch)
# origin  git@github.com:nvznc/Odoo-Atlas.git (push)
```

### 2.2 Historial de commits de código

| Commit | Fecha (UTC-4) | Mensaje | Alcance |
|---|---|---|---|
| `9ff4aca` | 2026-10-23 01:00:41 | `Initial commit` | README y `.gitignore` iniciales del repo |
| `169a35f` | 2026-10-23 01:48:13 | `Implement BCV audit improvements and deployment tooling` | 48 archivos, +2929 / -209 |
| `24e08bf` | 2026-10-23 02:18:56 | `Show BCV change amount on POS payment screen` | 2 archivos, +11 / -1 |
| `f397f6f` | 2026-10-23 02:33:18 | `Fix POS payment status template inheritance` | 2 archivos, +2 / -2 |

### 2.3 Cómo se subió

1. Se verificó la clave SSH contra GitHub y se comprobó que el repo remoto existía.
2. Se inicializó git en `/home/anthony/odoo` y se agregó `origin`.
3. Se hizo `fetch` del commit inicial y `reset --mixed origin/main` para partir del
   historial remoto sin perder los archivos locales.
4. Se restauró el `README.md` remoto.
5. Se reemplazó el `.gitignore` por una versión compacta y segura.
6. Se revisó que `.env`, `backups/` y cachés quedaran fuera del stage.
7. Se ejecutó un escaneo de secretos sobre los archivos staged.
8. Se hizo commit y `git push -u origin main` por SSH.
9. Se verificó que `HEAD` local y `origin/main` coincidieran y que no hubiera `.env`
   ni `backups/` en el árbol remoto.

No fue necesario usar `sudo` para la operación de GitHub.

### 2.4 Cómo revisar los cambios desde otra sesión

```bash
cd /home/anthony/odoo

git status
git log --oneline --decorate --graph -10
git show --stat 169a35f
git show 24e08bf
git show f397f6f
git diff 9ff4aca..HEAD
```

Archivos de referencia:

- `CAMBIOS.md` (este documento)
- `AUDIT_DEPLOY_20261023.md` (auditoría, despliegue y rollback detallados)

### 2.5 Protección de secretos

El `.gitignore` local ignora, entre otros:

```gitignore
.env
backups/
.ruff_cache/
.pytest_cache/
*.dump
*.tar.gz
*.zip
```

Nota importante: el `.gitignore` que traía el repo inicial incluía el patrón `lib/`, que
habría excluido `addons/currency_rate_bcv/lib/`. Se reemplazó por una versión que no usa
ese patrón, para que `bcv.py` y los certificados públicos sí se versionen.

Verificación realizada antes del push:

- `.env` ignorado.
- `backups/` ignorado.
- Sin claves privadas ni tokens en los archivos staged.
- Sin archivos de datos pesados en el commit.

---

## 3. Entorno y versiones

| Elemento | Valor |
|---|---|
| Odoo | `19.0-20261015` |
| Contenedores | `odoo` y `odoo-db` (PostgreSQL 17) |
| BD producción | `odoo` |
| BD de pruebas conservadas | `odoo_pos_test`, `odoo_prod_rehearsal` |
| Addons | `./addons` montado en `/mnt/extra-addons` |
| Puerto | `8069` (`ODOO_BIND_IP`, por defecto `0.0.0.0`) |
| `currency_rate_bcv` | `19.0.1.0.0` |
| `pos_bcv_multi_currency` | `19.0.1.0.2` |

Las bases temporales `odoo_audit_test` y `odoo_audit_rehearsal` se crearon para pruebas y
luego se eliminaron.

---

## 4. Cambios de auditoría — commit `169a35f`

### 4.1 Workflow con subagentes

Se usaron 5 subagentes con archivos de propiedad disjunta:

| Subagente | Alcance | Resultado |
|---|---|---|
| A | `currency_rate_bcv/lib/bcv.py` | Parseo `Decimal`, `BCVError`, `BCVRate`, fecha opcional, SSL/timeout |
| B | Tasa BCV, company y settings | Separación de responsabilidades, errores específicos, helpers |
| C | `pos_session.py` | Reutilización del core en apertura, helpers de caja/diferencias |
| D | Config, pagos, order y currency POS | Validaciones core preservadas, helpers de pagos/tasas |
| E | Tooling, CI, compose y tests | Ruff, pre-commit, CI, `.env.example`, tests reforzados |

Los reportes se revisaron, se resolvieron conflictos de integración y se corrigieron los
hallazgos de Ruff antes de continuar.

### 4.2 Cambios funcionales

- `currency_rate_bcv/lib/bcv.py`
  - `_parse_decimal` admite `1.234,56`, `884.7496`, `1,234.56` y separadores mixtos.
  - Devuelve `Decimal` y lanza `BCVError` ante valores inválidos.
  - `_parse_date` devuelve `None` si no hay fecha válida.
  - Sin capturas genéricas de excepciones.
- `currency_rate_bcv/models/res_currency_rate.py`
  - `_update_bcv_rate` dividido en helpers: validación, fetch, persistencia y mensaje.
  - Contrato público de `action_update_bcv_rate` y `_cron_update_bcv_rate` intacto.
- `pos_bcv_multi_currency/models/pos_session.py`
  - `set_opening_control` reutiliza el core mediante `super()` y agrega el cuarto argumento BCV.
  - Helpers para caja, pagos y diferencias por diario.
  - `_post_statement_difference` conserva un helper propio para el caso `cash_control = False`.
- `pos_bcv_multi_currency/models/pos_config.py`
  - `_check_currencies` delega en el core usando `config.new({...})`.
  - Se añadió un test que demuestra que las validaciones core siguen activas.
- `pos_bcv_multi_currency/models/pos_payment.py` y `pos_order.py`
  - Helpers de tasa/importe, `RATE_EPSILON`, serialización y conversión a BCV.
- `pos_bcv_multi_currency/models/res_currency.py`
  - Dominio de monedas del POS corregido.

### 4.3 Tooling y seguridad

- `pyproject.toml`: Ruff `py312`, línea 100, reglas `E,W,F,I,UP,B,BLE,C4,C90,D`.
- `.pre-commit-config.yaml`: hooks de Ruff.
- `.github/workflows/ci.yml`: lint y tests de Odoo.
- `.gitignore`: exclusión de `.env`, backups y cachés.
- `.env.example`: plantilla sin credenciales reales.
- `docker-compose.yml`:
  - `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?define POSTGRES_PASSWORD en .env}`.
  - `PASSWORD: ${POSTGRES_PASSWORD:?...}` para Odoo.
  - `ports: "${ODOO_BIND_IP:-0.0.0.0}:8069:8069"` para no romper el acceso LAN del POS.
- Tests:
  - `currency_rate_bcv`: 12 tests.
  - `pos_bcv_multi_currency`: 8 tests.
  - Total: **14/14 OK**.

### 4.4 Lista completa de archivos del commit `169a35f`

<details>
<summary>Ver lista completa (48 archivos)</summary>

```text
A   .env.example
A   .github/workflows/ci.yml
M   .gitignore
A   .pre-commit-config.yaml
A   AUDIT_DEPLOY_20261023.md
A   addons/currency_rate_bcv/__init__.py
A   addons/currency_rate_bcv/__manifest__.py
A   addons/currency_rate_bcv/data/ir_cron.xml
A   addons/currency_rate_bcv/lib/__init__.py
A   addons/currency_rate_bcv/lib/bcv.py
A   addons/currency_rate_bcv/lib/certs/SectigoPublicServerAuthenticationCADVR36.pem
A   addons/currency_rate_bcv/lib/certs/SectigoPublicServerAuthenticationRootR46.pem
A   addons/currency_rate_bcv/models/__init__.py
A   addons/currency_rate_bcv/models/res_company.py
A   addons/currency_rate_bcv/models/res_config_settings.py
A   addons/currency_rate_bcv/models/res_currency_rate.py
A   addons/currency_rate_bcv/tests/__init__.py
A   addons/currency_rate_bcv/tests/test_bcv.py
A   addons/currency_rate_bcv/views/res_config_settings_views.xml
A   addons/currency_rate_bcv/views/res_currency_rate_views.xml
A   addons/pos_bcv_multi_currency/__init__.py
A   addons/pos_bcv_multi_currency/__manifest__.py
A   addons/pos_bcv_multi_currency/models/__init__.py
A   addons/pos_bcv_multi_currency/models/pos_config.py
A   addons/pos_bcv_multi_currency/models/pos_order.py
A   addons/pos_bcv_multi_currency/models/pos_payment.py
A   addons/pos_bcv_multi_currency/models/pos_payment_method.py
A   addons/pos_bcv_multi_currency/models/pos_session.py
A   addons/pos_bcv_multi_currency/models/res_currency.py
A   addons/pos_bcv_multi_currency/static/src/app/components/order_display/order_display.xml
A   addons/pos_bcv_multi_currency/static/src/app/components/popups/closing_popup/closing_popup.js
A   addons/pos_bcv_multi_currency/static/src/app/components/popups/closing_popup/closing_popup.xml
A   addons/pos_bcv_multi_currency/static/src/app/components/popups/opening_control_popup/opening_control_popup.js
A   addons/pos_bcv_multi_currency/static/src/app/components/popups/opening_control_popup/opening_control_popup.xml
A   addons/pos_bcv_multi_currency/static/src/app/models/pos_order.js
A   addons/pos_bcv_multi_currency/static/src/app/models/pos_payment.js
A   addons/pos_bcv_multi_currency/static/src/app/screens/payment_screen/payment_screen.js
A   addons/pos_bcv_multi_currency/static/src/app/screens/payment_screen/payment_screen.xml
A   addons/pos_bcv_multi_currency/static/src/app/screens/receipt_screen/order_receipt.xml
A   addons/pos_bcv_multi_currency/tests/__init__.py
A   addons/pos_bcv_multi_currency/tests/test_pos_bcv.py
A   addons/pos_bcv_multi_currency/views/pos_config_views.xml
A   addons/pos_bcv_multi_currency/views/pos_order_views.xml
A   addons/pos_bcv_multi_currency/views/pos_payment_method_views.xml
A   addons/pos_bcv_multi_currency/views/pos_payment_views.xml
A   addons/pos_bcv_multi_currency/views/pos_session_views.xml
A   docker-compose.yml
A   pyproject.toml
```

</details>

---

## 5. Cambios en la pantalla de pago del POS

### 5.1 Funcionalidad agregada — commit `24e08bf`

Se agregó el vuelto en bolívares debajo del estado `Change` de la pantalla de pago.

- Componente intervenido: `point_of_sale.PaymentScreenStatus`.
- Dato mostrado: `order.bcvChangeDisplay`, que calcula `order.change * bcvRate` y lo
  formatea en la moneda BCV.
- Versión del módulo: `19.0.1.0.1`.
- Archivos:
  - `addons/pos_bcv_multi_currency/__manifest__.py`
  - `addons/pos_bcv_multi_currency/static/src/app/screens/payment_screen/payment_screen.xml`

### 5.2 Incidente y corrección — commit `f397f6f`

La primera implementación usaba:

```xml
<xpath expr="//section[hasclass('paymentlines-container')]" position="inside">
```

Ese selector fallaba en el navegador porque la sección del template core define su clase
con `t-attf-class`, no con `class`. `hasclass` solo inspecciona el atributo `class`, así que
OWL no encontraba el nodo y lanzaba:

```text
Error: Element '<xpath ...>' cannot be located in element tree
```

El resultado era una pantalla de pago en blanco después de cobrar.

La corrección usa una clase literal del template core:

```xml
<xpath expr="//div[hasclass('payment-status-container')]" position="after">
    <div t-if="order.hasBcv and order.payment_ids.length and !isRemaining"
        class="payment-status-bcv d-flex justify-content-between align-items-baseline text-muted fs-4 pt-1 pe-5 me-5">
        <span>Change Bs</span>
        <span class="fw-bold" t-out="order.bcvChangeDisplay"/>
    </div>
</xpath>
```

- Se validó que `div.payment-status-container` existe con `class` literal.
- Se validó que el nuevo bundle incluye la extensión y la clase `payment-status-bcv`.
- Versión del módulo: `19.0.1.0.2`.
- Bundle servido en producción: `/web/assets/9f12006/point_of_sale._assets_pos.min.js`.

### 5.3 Acción requerida en terminales POS

Después de desplegar, hay que **cerrar las pestañas del POS y hacer recarga forzada**
(`Ctrl+Shift+R`) o limpiar la caché del sitio para que el navegador cargue el bundle
nuevo. Si el POS sigue abierto con el bundle anterior, el error puede persistir aunque el
servidor ya esté corregido.

---

## 6. Pruebas y validación

| Validación | Resultado |
|---|---|
| Ruff (`ruff check`, `ruff format --check`) | 0 errores, 21 archivos formateados |
| Compilación Python host y contenedor | OK |
| XML de templates POS | OK |
| Selector XPath contra template core | 1 coincidencia (`SELECTOR_OK`) |
| Tests Odoo en BD de prueba | **14/14 OK, 0 fallos** |
| Upgrade en BD de ensayo | OK |
| Upgrade en producción | OK |
| Bundle POS en producción | incluye `payment-status-bcv` y la extensión |
| HTTP producción | 200 |
| Contraseña antigua de PostgreSQL por red | rechazada |
| Contraseña nueva de PostgreSQL por red | aceptada |

Evidencia local (puede desaparecer si se reinicia el sistema, porque está en `/tmp`):

- `/tmp/odoo_test2.log` — tests iniciales 14/14.
- `/tmp/odoo_fix_test.log` — tests después del cambio POS 14/14.
- `/tmp/odoo_rehearsal.log` — upgrade de ensayo.
- `/tmp/prod_upgrade.log` — upgrade inicial de producción.
- `/tmp/prod_fix_upgrade.log` — upgrade de la versión `19.0.1.0.1`.
- `/tmp/prod_fix2_upgrade.log` — upgrade de la versión `19.0.1.0.2`.

---

## 7. Despliegue en producción

### 7.1 Secuencia general

1. Backup de la BD y del filestore.
2. Creación de `.env` con contraseña fuerte y permisos `600`.
3. Parada de Odoo.
4. Rotación de la contraseña del rol PostgreSQL `odoo`.
5. Upgrade de módulos con un contenedor temporal.
6. Recreación/arranque de contenedores.
7. Verificación de módulos, HTTP, logs y bundle del POS.

### 7.2 Comandos usados

Upgrade de auditoría:

```bash
docker compose stop odoo
docker compose run --rm --no-deps odoo odoo -d odoo \
  --http-port=8072 --stop-after-init \
  -u currency_rate_bcv,pos_bcv_multi_currency
docker compose up -d --force-recreate db
docker compose up -d --force-recreate odoo
```

Upgrade del cambio POS:

```bash
docker compose stop odoo
docker compose run --rm --no-deps odoo odoo -d odoo \
  --http-port=8072 --stop-after-init \
  -u pos_bcv_multi_currency
docker compose up -d odoo
```

### 7.3 Credenciales y configuración

- `.env` contiene `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` y `ODOO_BIND_IP`.
- `.env` tiene permisos `600` y **no** está en GitHub.
- La contraseña de PostgreSQL fue rotada; la anterior ya no funciona por red.
- `pg_hba.conf` mantiene `trust` para `127.0.0.1` dentro del contenedor de PostgreSQL
  (comportamiento estándar de la imagen). Las conexiones externas usan `scram-sha-256`.
- El rol `odoo` sigue siendo superusuario. Es una mejora pendiente, no un bloqueo.
- `ODOO_BIND_IP=0.0.0.0` se mantuvo para no romper el acceso LAN del POS. Si se pone
  detrás de un proxy inverso, cambiar a `127.0.0.1`.

---

## 8. Backups y rollback

### 8.1 Backups disponibles

| Archivo | Tamaño | Contenido |
|---|---:|---|
| `backups/audit_baseline_20261023-004226.tar.gz` | 22K | Código y compose previos a la auditoría |
| `backups/prod_pre_deploy_20261023-010622.dump` | 5.9M | BD de producción previa al deploy |
| `backups/filestore_prod_pre_deploy_20261023-010622.tar.gz` | 19M | Filestore previo al deploy |
| `backups/prod_pre_fix_20261023-021647.dump` | 5.9M | BD previa al cambio POS |

Los backups contienen datos sensibles y están ignorados por git.

### 8.2 Rollback de código

```bash
cd /home/anthony/odoo
mkdir -p /tmp/rollback
tar -xzf backups/audit_baseline_20261023-004226.tar.gz -C /tmp/rollback
cp -a /tmp/rollback/addons/. addons/
docker compose up -d --force-recreate odoo
```

Esto conserva el `.env`, la contraseña nueva y el compose endurecido.

Si se restaura también el `docker-compose.yml` baseline, hay que volver la contraseña de
PostgreSQL a `odoo` o adaptar el compose al `.env` actual.

Para revertir **solo** el cambio de la pantalla de pago (sin tocar la auditoría):

```bash
cd /home/anthony/odoo
git revert --no-edit f397f6f 24e08bf
docker compose stop odoo
docker compose run --rm --no-deps odoo odoo -d odoo \
  --http-port=8072 --stop-after-init -u pos_bcv_multi_currency
docker compose up -d odoo
```

También se puede usar el backup `backups/prod_pre_fix_20261023-021647.dump` si se necesita
volver la BD al estado previo a ese cambio.

### 8.3 Rollback de base de datos

```bash
cd /home/anthony/odoo
docker compose stop odoo
docker exec odoo-db dropdb -U odoo --if-exists odoo
docker exec odoo-db createdb -U odoo odoo
docker exec -i odoo-db pg_restore -U odoo -d odoo < backups/prod_pre_deploy_20261023-010622.dump
docker compose up -d --force-recreate odoo
```

### 8.4 Rollback de filestore

Solo si fuese necesario:

```bash
docker run --rm \
  -v odoo_odoo-data:/var/lib/odoo \
  -v "$PWD/backups":/backup \
  alpine sh -c 'tar -xzf /backup/filestore_prod_pre_deploy_20261023-010622.tar.gz -C /var/lib/odoo'
```

Después de cualquier rollback, verificar:

```bash
docker compose ps
docker compose logs --tail=100 odoo
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8069/web/database/selector
```

---

## 9. Estado actual y pendientes

### 9.1 Estado actual

- Producción `odoo` operativa.
- `pos_bcv_multi_currency` en `19.0.1.0.2`.
- `currency_rate_bcv` en `19.0.1.0.0`.
- Último commit de código en GitHub: `f397f6f`.
- `pos_preparation_display_atlas` está instalado solo en la base de prueba; aún no en producción.
- El bundle del POS con la corrección es `/web/assets/9f12006/point_of_sale._assets_pos.min.js`.
- Los tests de Python siguen en 14/14.

### 9.2 Acciones pendientes / recomendadas

1. En cada terminal POS: cerrar pestañas y hacer recarga forzada para cargar el bundle nuevo.
2. Verificar en el POS que al overpagar en Bs aparece `Change Bs` con el monto correcto.
3. Opcional: migrar el rol PostgreSQL `odoo` a un rol de mínimo privilegio.
4. Opcional: ejecutar y validar el workflow de GitHub Actions en el repo remoto.
5. Opcional: cambiar `ODOO_BIND_IP` a `127.0.0.1` si Odoo queda detrás de un proxy inverso.
6. Mantener los backups fuera de git y con acceso restringido.

---

## 10. Referencias rápidas

- Documento de auditoría y despliegue: `AUDIT_DEPLOY_20261023.md`
- Configuración de Ruff: `pyproject.toml`
- CI: `.github/workflows/ci.yml`
- Pre-commit: `.pre-commit-config.yaml`
- Variables de entorno de ejemplo: `.env.example`
- Compose: `docker-compose.yml`
- Repositorio: <https://github.com/nvznc/Odoo-Atlas>

---

## 11. Módulo POS Preparation Display (2026-10-23)

Se agregó el addon local `addons/pos_preparation_display_atlas` (`19.0.1.0.0`,
licencia `LGPL-3`) como implementación propia para Odoo 19 Community. No contiene
código de Odoo Enterprise.

### 11.1 Funcionalidad

- Pantalla de cocina autenticada en `/pos_preparation_display/web?display_id=...`.
- Pantalla pública de estado en `/pos-order-tracking?access_token=...`.
- Columnas públicas: `Preparando`, `Casi Listo` y `Listo`.
- Etapas por defecto: `Preparando`, `Listo` (penúltima) y `Completado`.
- Avance manual por pedido, reinicio, completado, marque de líneas y reinicio global.
- Temporizador por etapa, resaltado por `alert_timer`, notas, atributos, combos,
  cantidades canceladas y auto-limpieza de la pantalla pública.
- Activación por POS en Ajustes (`pos_prep_display_enabled`).
- Filtro de categorías por pantalla; vacío significa todas las categorías.
- Pedidos impagos: en POS no restaurante se envían durante `sync_from_ui`; en
  restaurante al usar “Enviar a cocina”. Los pedidos pagados también se envían.
- Sincronización en vivo por `pos.bus.mixin` (`LOAD_ORDERS` y `NEW_ORDERS`).
- Botones “Preparation Screen” y “Order Status Screen” en el formulario y kanban.
- Reglas multi-compañía y constraint `unique(pos_order_id)` en `pos.prep.order`.
- Cron diario que elimina preparaciones antiguas cerradas o completadas.

### 11.2 Archivos principales

- `__manifest__.py`, `models/`, `controllers/main.py`, `views/`, `security/`.
- `static/src/kitchen/`: pantalla de cocina.
- `static/src/status/`: pantalla pública.
- `static/src/pos/`: integración con el POS y categorías de preparación.
- `tests/test_preparation_display.py`: 10 tests.

### 11.3 Pruebas realizadas

- Base clonada `odoo_prep_display_test`; producción **no** fue modificada.
- Backup previo: `backups/odoo_before_prep_display_20261023_052237.dump`.
- Instalación y upgrades correctos.
- `10/10` tests OK (`--test-tags=/pos_preparation_display_atlas`).
- Verificación HTTP: cocina `200`, pública `200`, JSON `200`, token inválido `404`.
- Assets de cocina, estado y POS generados y validados con `node --check`.
- Se confirmó que el bundle del POS carga `prep_display_enabled`, las categorías y
  la pantalla `pos.prep.display`.
- Prueba real en Firefox headless con WebDriver sobre la base de prueba:
  - cocina renderizada con pedido, tabs, etapas, líneas y botones;
  - temporizador actualizado cada segundo;
  - `Avanzar`, `Completar` y `Reiniciar` actualizan etapa, tabs y tarjeta;
  - marcar/desmarcar línea persiste al recargar y `Reiniciar` la restaura;
  - `Reiniciar todo` deja la pantalla vacía y actualiza la pantalla pública;
  - la pantalla pública muestra solo `Preparando`, `Casi Listo` y `Listo`, y
    recibe el cambio por bus sin recargar la página.
- Corrección de reactividad Owl: los componentes que consumen el estado de los
  servicios usan `useState(service.state)`, de modo que las mutaciones del estado
  notifican y vuelven a renderizar. También se añadió secuencia de carga para
  ignorar respuestas antiguas.

Comando de upgrade/pruebas usado:

```bash
docker exec odoo sh -lc 'odoo -d odoo_prep_display_test -u pos_preparation_display_atlas \
  --test-enable --stop-after-init --http-port=8070 \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  --db_host=db --db_port=5432 --db_user="$USER" --db_password="$PASSWORD" \
  --log-level=test --test-tags=/pos_preparation_display_atlas 2>&1 | tail -120'
```

### 11.4 Pendientes

1. Instalar el módulo en producción cuando se autorice.
2. Probar la interacción real en la TV/terminal definitiva (sonido, tamaños y red local).
3. El addon y sus correcciones quedaron en commits locales (`cbb6e7b`, `ab20c2f`,
   `4467a98`); **no** se ha hecho push.
