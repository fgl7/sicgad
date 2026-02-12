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

## 3. Roles y permisos
Modelo: `accounts/models.py` -> `Membership`.
Roles:
- `ADMIN`
- `LOADER`
- `VALIDATOR`
- `VIEWER`

Reglas importantes:
- Un `LOADER` debe tener `entity` (no puede ser null).
- `VALIDATOR` puede tener permisos por periodicidad:
  - `can_validate_daily`
  - `can_validate_weekly`
  - `can_validate_monthly`
  - `can_validate_projections`
- `ADMIN` operativo (membership role ADMIN) es distinto de `superuser` tecnico.

Seguridad:
- `AccountProfile.must_change_password` forzado por middleware.
- Middleware: `accounts/middleware.py`.

## 4. Esquemas
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
4. Certificacion mensual la crea admin.

Vistas clave:
- `schemas/views.py`
- `templates/schemas/schema_list.html`
- `templates/schemas/schema_edit.html`
- `templates/schemas/schema_detail.html`

## 5. Carga de datos (ingest)
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

UX implementada recientemente:
- En `upload_historical`, spinner y barra de progreso de subida.
- Segunda fase visual: "procesando en servidor".

## 6. Validacion
Modelo:
- `validation/models.py` -> `ValidationAction`

Vistas:
- `validation/views.py`
- rutas bajo `/validate/`

Comportamiento:
- Validadores ven bandeja segun memberships y periodicidad.
- Publicacion final materializa datos a `PublishedDataPoint`.

## 7. Alertas en sidebar
Context processor:
- `accounts/context_processors.py`

Entrega a plantillas:
- pendientes de esquemas
- pendientes de validacion
- alertas de certificacion
- feedback loader (aprobado/rechazado)

Sidebar:
- `templates/partials/sidebar.html`

Nota: Auditoria esta visible para todos los usuarios autenticados.

## 8. Gestion de niveles (admin operativo)
Vista principal:
- `structure/views.py:manage_levels`

Capacidades:
- Crear/editar/eliminar/toggle de sector/subsector/categoria/entidad.
- Bloqueos de eliminacion/desactivacion si existen datos asociados.
- Se registran acciones en auditoria.

## 9. Politica de archivos y retencion
Objetivo: no crecer indefinidamente en `media/`.

Implementado:
- Señales de borrado automatico en reemplazo/delete:
  - `ingest/signals.py`
- Servicio de limpieza:
  - `ingest/file_cleanup.py`
- Middleware de limpieza automatica periodica:
  - `ingest/middleware.py`
- Comando opcional (manual/auditoria):
  - `ingest/management/commands/ingest_cleanup_files.py`
- Config en `config/settings.py` y `.env`:
  - `AUTO_INGEST_*`
  - `DATA_UPLOAD_MAX_NUMBER_FIELDS`
- Guia: `docs/storage_retention.md`

## 10. Rutas principales
Definidas en `config/urls.py`:
- `/accounts/`
- `/schemas/`
- `/ingest/`
- `/validate/`
- `/audit/`
- `/performance/`
- `/structure/`
- `/kpis/`

## 11. Deuda tecnica conocida (importante)
Hay mezcla parcial de modelo nuevo (`entity`) con referencias legacy (`plant/project`) en algunos puntos.

Principal foco:
- `ingest/views.py` contiene secciones aun referenciando `Plant`/`Project` y `select_related("plant")`.
- `structure/views.py` usa `Plant/Project` en conteos de impacto para bloqueos.
- `config/settings.py` mantiene apps `plants` y `projects` instaladas.

Impacto:
- Riesgo de `FieldError` en rutas que toquen ramas legacy.
- Riesgo de regresiones al tocar ingest/validation sin revisar referencias cruzadas.

Regla para desarrollo futuro:
- Priorizar siempre flujo por `entity`.
- Si se toca `ingest/views.py`, validar que no queden consultas `plant/project` incompatibles con modelos actuales.

## 12. Estado funcional practico (resumen)
Funciona y se usa activamente:
- Gestion de niveles por entidad.
- Creacion/aprobacion de esquemas.
- Creacion de usuarios y memberships por entidad.
- Carga historica con progreso visual.
- Sidebar con alertas operativas.
- Limpieza automatica de archivos en media.

Requiere refactor planificado:
- Remocion completa de legado `plant/project` en vistas/servicios restantes.
- Normalizacion de textos/encoding en plantillas antiguas.
- Cobertura de tests.

## 13. Checklist rapido antes de tocar codigo
1. Confirmar si el flujo es por `entity` (debe ser SI).
2. Revisar si el archivo toca ramas legacy `plant/project`.
3. Ejecutar:
   - `python manage.py check`
4. Si se modifica ingest/validation, probar manualmente:
   - carga historica
   - carga periodica
   - envio a validacion
   - acceso de admin y loader

## 14. Archivos que primero hay que abrir para entender el sistema
1. `structure/models.py`
2. `accounts/models.py`
3. `schemas/models.py`
4. `ingest/models.py`
5. `accounts/context_processors.py`
6. `templates/partials/sidebar.html`
7. `ingest/views.py` (con foco en deuda tecnica legacy)

---

Este documento reemplaza versiones anteriores mas generales. Esta escrito para operar y evolucionar el estado real actual del proyecto, no el diseño ideal historico.
