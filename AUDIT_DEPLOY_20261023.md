# Auditoría, implementación y despliegue — 2026-10-23

## Resumen ejecutivo

Se implementaron los 8 pasos de la auditoría sobre los addons `currency_rate_bcv` y
`pos_bcv_multi_currency`, se validaron con tests y se desplegaron en producción con
backup previo, rotación de credenciales y plan de rollback.

- Entorno: Odoo `19.0-20261015`, Docker (`odoo` + `odoo-db` con PostgreSQL 17).
- Producción: base de datos `odoo`.
- Tests: **14/14 OK, 0 fallos**.
- Upgrade de producción: **OK**, módulos en `19.0.1.0.0`.
- Estado final: contenedores healthy, HTTP operativo, credenciales rotadas.
- No quedan acciones pendientes en producción.

## Entorno

| Elemento | Valor |
|---|---|
| Odoo | 19.0-20261015 |
| Contenedores | `odoo`, `odoo-db` (postgres:17) |
| BD producción | `odoo` |
| BD de pruebas conservadas | `odoo_pos_test`, `odoo_prod_rehearsal` |
| Addons | `./addons` montado en `/mnt/extra-addons` |
| Puerto | `8069` (`ODOO_BIND_IP`, por defecto `0.0.0.0`) |
| Credenciales | `.env` local con permisos `600` (no versionado) |

## Workflow con subagentes

| Subagente | Archivos principales | Resultado |
|---|---|---|
| A | `currency_rate_bcv/lib/bcv.py` | Parseo `Decimal` robusto, `BCVError`, `BCVRate` (`TypedDict`), fecha opcional, timeout y SSL |
| B | `currency_rate_bcv/models/res_currency_rate.py`, `res_company.py`, `res_config_settings.py` | Separación de responsabilidades, captura específica de errores, helpers y tipos |
| C | `pos_bcv_multi_currency/models/pos_session.py` | Reutilización del core en apertura, helpers de caja y diferencias, eliminación de duplicación |
| D | `pos_config.py`, `pos_payment.py`, `pos_order.py`, `res_currency.py`, `pos_payment_method.py` | Validaciones core preservadas, helpers de pagos/tasas, dominio POS corregido |
| E | `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.gitignore`, `.env.example`, `docker-compose.yml` | Lint, CI, pre-commit, secretos fuera del compose y tests reforzados |

Los reportes se revisaron y sintetizaron; se resolvieron conflictos de integración y se
corrigieron 34 hallazgos de Ruff antes del checkpoint final.

## Cambios funcionales relevantes

- `lib/bcv.py`
  - `_parse_decimal` soporta `1.234,56`, `884.7496`, `1,234.56` y valores con separadores
    mixtos, devolviendo `Decimal`.
  - `_parse_date` devuelve `None` si no hay fecha válida.
  - Excepciones acotadas a `BCVError`; sin capturas genéricas.
- `models/res_currency_rate.py`
  - `_update_bcv_rate` dividido en `_validate_bcv_company_currency`, `_fetch_bcv_rate`,
    `_persist_bcv_rate` y `_build_bcv_message`.
  - Contrato público de `action_update_bcv_rate` y `_cron_update_bcv_rate` intacto.
- `models/pos_session.py`
  - `set_opening_control` reutiliza el core mediante `super()` y añade el cuarto argumento BCV.
  - `_post_statement_difference` usa helpers propios para preservar el comportamiento
    cuando `cash_control` es falso (el core asume que es verdadero).
  - Helpers `_compute_cash_balance_for_journal`, `_sum_payments` y variantes por diario.
- `models/pos_config.py`
  - `_check_currencies` delega en el core usando `config.new({...})` con los campos
    necesarios; se añadió un test que demuestra que las validaciones core siguen activas.
- Tooling
  - Ruff con `py312`, línea 100, reglas `E,W,F,I,UP,B,BLE,C4,C90,D`.
  - Pre-commit, CI y `.gitignore` para `.env`, backups y cachés.

## Evidencia de validación

| Checkpoint | Comando / evidencia | Resultado |
|---|---|---|
| Estático | `ruff check .`, `ruff format --check .`, `compileall` host y contenedor | 0 errores; 21 archivos formateados; compilación OK |
| Tests | `odoo ... -d odoo_audit_test ... --test-enable --test-tags=/currency_rate_bcv,/pos_bcv_multi_currency` | **14/14 OK** (`/tmp/odoo_test2.log`) |
| Ensayo | Upgrade en `odoo_audit_rehearsal` | OK (`/tmp/odoo_rehearsal.log`); columnas verificadas |
| Producción | Upgrade en `odoo` | OK (`/tmp/prod_upgrade.log`); `19.0.1.0.0` |

Columnas verificadas en producción: `res_currency_rate.source`, `pos_order.bcv_rate`,
`pos_order.bcv_amount_total`, `pos_order.bcv_rate_date`, `pos_order.bcv_cash_journal_id`.

## Despliegue realizado

1. Backup de BD y filestore de producción.
2. Creación de `.env` con contraseña fuerte y permisos `600`.
3. Parada de Odoo y rotación de la contraseña del rol PostgreSQL `odoo`.
4. Upgrade de módulos con un contenedor temporal:
   `docker compose run --rm --no-deps odoo odoo -d odoo --http-port=8072 --stop-after-init -u currency_rate_bcv,pos_bcv_multi_currency`.
5. Recreación de `odoo-db` y `odoo` con la nueva configuración.
6. Verificación:
   - `/web/database/selector` → `200`; login → `303`.
   - Registro Odoo cargado: 72 módulos.
   - Prueba read-only vía `odoo shell`: `_parse_decimal("1.234,56") == 1234.56`,
     `_parse_decimal("884.7496") == 884.7496`, campo `source` presente.
   - Contraseña antigua rechazada por red (scram-sha-256); nueva aceptada.
   - Sin `PASSWORD=odoo` en el entorno del contenedor.
   - Bases de auditoría `odoo_audit_test` y `odoo_audit_rehearsal` eliminadas.

Nota: `pg_hba.conf` mantiene `trust` para `127.0.0.1` dentro del contenedor de PostgreSQL
(comportamiento estándar de la imagen); las conexiones externas usan `scram-sha-256`.

## Backups

| Archivo | Tamaño | Uso |
|---|---:|---|
| `backups/audit_baseline_20261023-004226.tar.gz` | 22K | Código y compose previos a la auditoría |
| `backups/prod_pre_deploy_20261023-010622.dump` | 5.9M | BD de producción previa al deploy |
| `backups/filestore_prod_pre_deploy_20261023-010622.tar.gz` | 19M | Filestore previo al deploy |

Mantener estos archivos fuera de git y con acceso restringido: contienen datos sensibles.

## Rollback

### Solo código (recomendado si hay un fallo funcional)

```bash
cd /home/anthony/odoo
mkdir -p /tmp/rollback
tar -xzf backups/audit_baseline_20261023-004226.tar.gz -C /tmp/rollback
cp -a /tmp/rollback/addons/. addons/
docker compose up -d --force-recreate odoo
```

Este rollback conserva el `.env`, la contraseña nueva y el `docker-compose.yml` endurecido.

### Código y compose baseline

Si se restaura también el `docker-compose.yml` baseline, la contraseña de la BD debe volver
a `odoo` o el compose debe adaptarse al `.env` actual. Para un rollback completo de
credenciales:

```bash
docker exec odoo-db psql -U odoo -d postgres -c "ALTER USER odoo WITH PASSWORD 'odoo';"
```

No se recomienda salvo que se esté revirtiendo toda la auditoría.

### Base de datos

```bash
cd /home/anthony/odoo
docker compose stop odoo
docker exec odoo-db dropdb -U odoo --if-exists odoo
docker exec odoo-db createdb -U odoo odoo
docker exec -i odoo-db pg_restore -U odoo -d odoo < backups/prod_pre_deploy_20261023-010622.dump
docker compose up -d --force-recreate odoo
```

### Filestore (solo si fuese necesario)

```bash
docker run --rm \
  -v odoo_odoo-data:/var/lib/odoo \
  -v "$PWD/backups":/backup \
  alpine sh -c 'tar -xzf /backup/filestore_prod_pre_deploy_20261023-010622.tar.gz -C /var/lib/odoo'
```

Verificar siempre después del rollback: `docker compose ps`, logs sin `ERROR/CRITICAL`,
`/web/database/selector` y una prueba read-only de `_parse_decimal`.

## Riesgos residuales y recomendaciones

- El job `odoo-tests` del CI está validado sintácticamente, pero no se ejecutó en GitHub
  Actions porque el directorio no es un repositorio git.
- `pos_config._check_currencies` usa un registro virtual (`config.new`) para delegar en el
  core; está cubierto por `test_core_currency_checks_are_preserved`.
- `set_opening_control` hereda del core pese a su docstring “DO NOT INHERIT”; el
  comportamiento se validó con tests.
- `_post_statement_difference` conserva un helper propio para no alterar el caso
  `cash_control = False`.
- El rol PostgreSQL `odoo` sigue siendo superusuario. Una siguiente fase podría migrar a un
  rol de mínimo privilegio con una BD propiedad del rol de Odoo.
- `ODOO_BIND_IP=0.0.0.0` se mantuvo para no romper el acceso LAN del POS. Si Odoo queda
  detrás de un proxy inverso, cambiar a `127.0.0.1` en `.env` y recrear el contenedor.
- Los backups y `.env` son sensibles; no deben versionarse ni compartirse.

## Archivos modificados y nuevos

Modificados:

- `addons/currency_rate_bcv/lib/bcv.py`
- `addons/currency_rate_bcv/models/res_company.py`
- `addons/currency_rate_bcv/models/res_config_settings.py`
- `addons/currency_rate_bcv/models/res_currency_rate.py`
- `addons/currency_rate_bcv/tests/test_bcv.py`
- `addons/pos_bcv_multi_currency/models/pos_config.py`
- `addons/pos_bcv_multi_currency/models/pos_order.py`
- `addons/pos_bcv_multi_currency/models/pos_payment_method.py`
- `addons/pos_bcv_multi_currency/models/pos_payment.py`
- `addons/pos_bcv_multi_currency/models/pos_session.py`
- `addons/pos_bcv_multi_currency/models/res_currency.py`
- `addons/pos_bcv_multi_currency/tests/test_pos_bcv.py`
- `docker-compose.yml`

Nuevos:

- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- `.gitignore`
- `.env.example`
- `.env` (local, permisos `600`, no versionar)
- `AUDIT_DEPLOY_20261023.md`

## Estado final

Producción estable y verificada. No hay cambios pendientes ni procesos de auditoría en
curso. Los artefactos de rollback están disponibles en `backups/`.
