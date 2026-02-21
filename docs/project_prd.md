# SICGAD - PRD Operativo (estado real del codigo)

Documento de referencia rapida para desarrollo. Su objetivo es que cualquier agente (o dev) entienda el sistema sin reexplorar todo el repo.

## 1. Objetivo del sistema
SICGAD centraliza:
- Definicion de esquemas de datos.
- Carga de datos (archivo/manual/historico).
- Validacion por niveles e institucion.
- Publicacion de datos para KPIs.
- Auditoria de acciones.
- Gestion de niveles organizacionales (Sector > Subsector > Categoria > Entidad).

## 2. Dominio actual (fuente de verdad)
El dominio funcional vigente esta centrado en `Entity` (no en Plant como dominio principal de negocio).
Jerarquia:
1. `Sector`
2. `Subsector`
3. `Category`
4. `Entity`

Archivos clave:
- `structure/models.py`
- `structure/views.py`
- `templates/structure/manage_levels.html`
- `static/js/structure_manage_levels.js`

Regla clave: las asociaciones operativas de usuarios, esquemas y cargas se hacen por `Entity`.

## 3. Roles, membresias y perfiles de visualizador
Modelo principal: `accounts/models.py` -> `Membership`.
Roles:
- `ADMIN`
- `LOADER`
- `VALIDATOR`
- `VIEWER`

Perfil adicional en `AccountProfile`:
- `viewer_profile_type` con tipos:
  - `STANDARD`
  - `EXTERNAL_MONTHLY`
  - `AUTHORITY_MHE`

Reglas importantes:
- Un `LOADER` debe tener `entity` (no puede ser null).
- `VALIDATOR` puede tener permisos por periodicidad:
  - `can_validate_daily`
  - `can_validate_weekly`
  - `can_validate_monthly`
  - `can_validate_projections`
- Roles no validadores (incluyendo `VIEWER`) no deben conservar flags de validacion activos.
- `ADMIN` operativo (membership role `ADMIN`) es distinto de `superuser` tecnico.

Seguridad:
- `AccountProfile.must_change_password` forzado por middleware.
- Middleware: `accounts/middleware.py`.

## 4. Alcance para visualizadores jerarquicos (AUTHORITY_MHE y EXTERNAL_MONTHLY)
Configurado desde UX de admin en:
- `templates/accounts/admin_user_create.html`
- `templates/accounts/admin_user_edit.html`
- `accounts/forms.py`
- `static/js/accounts_user_scope.js`

Comportamiento:
- Para visualizadores jerarquicos (`AUTHORITY_MHE` y `EXTERNAL_MONTHLY`), el admin puede seleccionar multiples:
  - `sector`
  - `subsector`
  - `category`
  - `entity`
- Las validaciones del formulario aseguran consistencia jerarquica entre selecciones.
- Los memberships se crean por entidad efectiva (lista de entidades objetivo).
- Soporte de alcance global (legacy/compatibilidad): membership `VIEWER` con `entity=None`.
- En runtime, la navegacion jerarquica del sidebar se construye desde memberships activos del usuario.

## 5. Esquemas
Modelos en `schemas/models.py`:
- `DatasetType` (por `entity`)
- `ColumnDef`

Campos/ideas clave de `DatasetType`:
- `validation_frequency`: `DAILY|WEEKLY|MONTHLY|FLEXIBLE`
- `status`: `DRAFT|PENDING|APPROVED|REJECTED`
- `is_certification`
- `is_one_time`
- `source_dataset` (para certificacion derivada)

Flujo resumido:
1. Loader crea/edita esquema.
2. Loader envia (`PENDING`).
3. Admin aprueba/rechaza.
4. Certificacion mensual la crea admin (derivada de un dataset diario).
5. La certificacion mensual creada por admin nace `APPROVED` y `is_active=True`.

Vistas clave:
- `schemas/views.py`
- `templates/schemas/schema_list.html`
- `templates/schemas/schema_edit.html`
- `templates/schemas/schema_detail.html`

## 6. Carga de datos (ingest)
Modelos en `ingest/models.py`:
- `DatasetInstance`
- `PublishedDataPoint`
- `HistoricalImportBatch`
- `DatasetChangeRequest` / `DatasetChangeAttachment`

Estados de `DatasetInstance`:
- `DRAFT`
- `SUBMITTED`
- `VALIDATED_L1`
- `VALIDATED_L2`
- `PUBLISHED`
- `LOCKED`

Flujos UI:
- Carga periodica: `templates/ingest/upload.html`
- Carga historica: `templates/ingest/upload_historical.html`
- Historial: `templates/ingest/upload_history.html`
- JS principal: `static/js/ingest_upload.js`

Reglas de negocio activas:
- Si el esquema requiere historico inicial (diario/semanal/mensual segun implementacion de gate), se redirige a historico.
- Carga historica crea/actualiza multiples `DatasetInstance` desde un archivo.
- Descarga de plantilla usa columnas del esquema.
- En envios/aprobaciones historicas, el flujo operativo usa `entity` (no `plant/project`) en permisos y consultas.
- `materialize_instance` preserva puntos ya existentes cuando la instancia no tiene `raw_file`
  (caso consolidaciones mensuales), evitando perdida de `PublishedDataPoint`.

UX:
- En `upload_historical`, spinner y barra de progreso de subida.
- Segunda fase visual: "procesando en servidor".
- En validacion historica (`validate/inbox`), aprobacion con overlay de carga y progreso visual para evitar doble accion.

## 7. Validacion
Modelo:
- `validation/models.py` -> `ValidationAction`

Vistas:
- `validation/views.py`
- rutas bajo `/validate/`

Comportamiento:
- Validadores ven bandeja segun memberships y periodicidad.
- Publicacion final materializa datos a `PublishedDataPoint`.
- Tras publicar y materializar, se ejecuta limpieza inmediata de archivos de ingest:
  - borra `DatasetInstance.raw_file` de instancias `PUBLISHED/LOCKED` con puntos materializados.
  - en historicos, intenta borrar `HistoricalImportBatch.source_file` si el lote ya no tiene instancias pendientes.
  - esta limpieza es best-effort (si falla, no bloquea la aprobacion; se registra en logs).
- `approve_historical_batch` contempla re-materializacion de instancias historicas ya publicadas que no tengan puntos, para evitar lotes parciales.
- Si falla la materializacion de una instancia puntual, el proceso masivo continua y reporta conteo de errores.
- Al aprobar diarios (individual o historico), se dispara consolidacion mensual automatica para
  meses afectados via `consolidate_certifications_for_daily_periods`.
- La consolidacion mensual automatica crea/actualiza instancias de certificacion en `SUBMITTED`
  (no `DRAFT`) para que entren al flujo de validacion mensual.

Regla operativa importante:
- `DatasetInstance` publicado sin `PublishedDataPoint` no aparece en KPIs/tablas analiticas, aunque su estado sea `PUBLISHED`.

## 8. KPIs, plantillas por perfil y visibilidad
Vista principal:
- `kpis/views.py:charts`

Plantillas activas segun perfil:
- `kpis/charts.html` -> flujo estandar.
- `kpis/charts_external.html` -> visualizador externo mensual.
- `kpis/charts_authority.html` -> visualizador autoridad MHE.

Reglas en backend:
- Scope por memberships se aplica siempre (excepto admin global).
- Para `EXTERNAL_MONTHLY` (viewer puro, no admin/loader/validator):
  - solo datasets `MONTHLY`.
  - bloqueo de datasets no mensuales tambien en endpoint `dataset_data`.
  - al entrar a `/kpis/` se intenta consolidacion lazy del mes previo (`ensure_previous_month_consolidated`).
  - si no hay filtros jerarquicos, se redirige al primer `sector/subsector/category` disponible para poblar el selector.
- Para `AUTHORITY_MHE` (viewer puro):
  - UI con navegacion sector > subsector > categoria > entidad.
  - soporte de filtros por query params `sector/subsector/category/entity`.

Detalle de series:
- Los datos publicados y validados convergen en la misma base logica (`PublishedDataPoint`) y se consumen desde alli para charts/tablas.

## 9. Sidebar y contexto global
Context processor:
- `accounts/context_processors.py`

Entrega a plantillas:
- flags de rol: admin, loader, validator, viewer
- `viewer_profile_type`
- `is_authority_viewer`
- `is_external_monthly_viewer`
- `viewer_nav_sectors` para menu de autoridad
- pendientes de esquemas
- pendientes de validacion
- alertas de certificacion
- feedback loader (aprobado/rechazado)

Sidebar:
- base: `templates/partials/sidebar.html`
- autoridad MHE: `templates/partials/sidebar_authority_mhe.html`
- switch en `templates/base.html` segun `is_authority_viewer or is_external_monthly_viewer`

Nota: Auditoria esta visible para usuarios autenticados segun reglas actuales de navegacion.

## 10. Gestion de niveles (admin operativo)
Vista principal:
- `structure/views.py:manage_levels`

Capacidades:
- Crear/editar/eliminar/toggle de sector/subsector/categoria/entidad.
- Bloqueos de eliminacion/desactivacion si existen datos asociados.
- Se registran acciones en auditoria.

## 11. Politica de archivos y retencion
Objetivo: no crecer indefinidamente en `media/`.

Implementado:
- Senales de borrado automatico en reemplazo/delete:
  - `ingest/signals.py`
- Servicio de limpieza:
  - `ingest/file_cleanup.py`
- Limpieza inmediata al publicar/materializar:
  - `cleanup_files_after_publication` llamada desde `validation/views.py`
- Middleware de limpieza automatica periodica:
  - `ingest/middleware.py`
- Comando opcional (manual/auditoria):
  - `ingest/management/commands/ingest_cleanup_files.py`
- Config en `config/settings.py` y `.env`:
  - `AUTO_INGEST_*`
  - `DATA_UPLOAD_MAX_NUMBER_FIELDS`
- Guia: `docs/storage_retention.md`

Operacion mensual (certificaciones):
- Comando: `schemas/management/commands/consolidate_certifications.py`
- Modos:
  - consolidacion mes previo: `python manage.py consolidate_certifications`
  - backfill historico total: `python manage.py consolidate_certifications --backfill`
  - backfill por esquema: `python manage.py consolidate_certifications --backfill --schema-id <id>`
  - backfill por rango: `--from-date YYYY-MM-DD --to-date YYYY-MM-DD`

## 12. Rutas principales
Definidas en `config/urls.py`:
- `/accounts/`
- `/schemas/`
- `/ingest/`
- `/validate/`
- `/audit/`
- `/performance/`
- `/structure/`
- `/kpis/`

## 13. Deuda tecnica conocida (importante)
El legado de `plants` fue retirado y el flujo operativo ya esta alineado a `entity`.

Foco actual de deuda:
- Consolidar cobertura de pruebas (ingest, validation, kpis, performance).
- Normalizar textos/encoding en plantillas antiguas.
- Revisar y limpiar documentacion tecnica vieja que todavia menciona `plant/project`.

Impacto:
- Menor riesgo de `FieldError` por referencias legacy eliminadas.
- Riesgo principal restante: regresiones funcionales por refactor amplio sin suite completa de tests.

Regla para desarrollo futuro:
- Priorizar siempre flujo por `entity` en modelos, consultas, formularios, templates y APIs.
- No reintroducir aliases o nuevas dependencias al dominio eliminado (`plants`).
## 14. Estado funcional practico (resumen)
Funciona y se usa activamente:
- Gestion de niveles por entidad.
- Creacion/aprobacion de esquemas.
- Creacion de usuarios y memberships por entidad.
- Perfiles de visualizador diferenciados (`STANDARD`, `EXTERNAL_MONTHLY`, `AUTHORITY_MHE`).
- Alcance jerarquico para visualizadores `AUTHORITY_MHE` y `EXTERNAL_MONTHLY`
  (multi sector/subsector/categoria/entidad) desde UX de admin.
- Carga historica con progreso visual.
- Aprobacion historica con overlay de progreso para proceso largo.
- Aprobacion historica con rematerializacion de puntos faltantes.
- Aprobacion diaria/historica con trigger de consolidacion mensual automatica.
- Sidebar jerarquico compartido para autoridad MHE y visualizador externo mensual.
- Restriccion mensual para visualizador externo en charts y dataset_data.
- Limpieza inmediata post-publicacion/materializacion + limpieza periodica por retencion en media.
- KPIs de dataset con ventana temporal reciente (3 meses) cuando aplica columna fecha.

Requiere refactor planificado:
- Extender pruebas de regresion para cubrir flujos refactorizados a `entity`.
- Normalizacion de textos/encoding en plantillas antiguas (sin BOM en templates).
- Cobertura de tests automatizados por flujo critico.

## 15. Checklist rapido antes de tocar codigo
1. Confirmar si el flujo es por `entity` (debe ser SI).
2. Verificar consistencia del cambio con el dominio `entity` (modelos, consultas y templates).
3. Revisar si el cambio afecta perfiles de visualizador (`viewer_profile_type`).
4. Ejecutar:
   - `python manage.py check`
   - si hay cambios en consolidacion mensual: `python manage.py consolidate_certifications --backfill` (entorno de prueba)
5. Si se modifica ingest/validation, probar manualmente:
   - carga historica
   - carga periodica
   - envio a validacion
   - aprobacion historica
   - acceso de admin, loader, validator y viewer
6. Si hay diferencias entre instancias publicadas y datos en KPIs, verificar `PublishedDataPoint` por dataset/periodo.
   - para visualizador externo mensual, confirmar que las instancias mensuales esten en `PUBLISHED/LOCKED`.
7. Si se toca UX de cuentas, validar formulario crear/editar usuario y creacion de memberships esperados.

## 16. Archivos que primero hay que abrir para entender el sistema
1. `structure/models.py`
2. `accounts/models.py`
3. `accounts/forms.py`
4. `accounts/context_processors.py`
5. `schemas/models.py`
6. `ingest/models.py`
7. `kpis/views.py`
8. `templates/base.html`
9. `templates/partials/sidebar.html`
10. `templates/partials/sidebar_authority_mhe.html`
11. `performance/views.py` (builder y calculo por entidad)

---

Este documento reemplaza versiones anteriores mas generales. Esta escrito para operar y evolucionar el estado real actual del proyecto, no el diseno ideal historico.
