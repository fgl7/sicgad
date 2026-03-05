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
- `entity` sigue siendo el scope operativo principal
- `project` (opcional) para vinculo explicito cuando el esquema nace desde `projects`
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
6. Los datasets derivados de formulas de desempeno (`performance`) se desactivan
   (`is_active=False`) cuando la formula es archivada/eliminada desde UI (soft delete),
   para que no sigan apareciendo como esquemas activos.

Vistas clave:
- `schemas/views.py`
- `templates/schemas/schema_list.html`
- `templates/schemas/schema_edit.html`
- `templates/schemas/schema_detail.html`

Nota operativa:
- La lista de esquemas muestra:
  - activos (`is_active=True`)
  - y tambien estados de workflow no activos (`DRAFT`, `PENDING`, `REJECTED`)
  - esto permite que admin vea y atienda los envios pendientes sin perder trazabilidad de borradores/rechazos recientes.
- Cuando un loader entra a `schemas:schema_create` desde un proyecto/convenio aprobado, el formulario puede venir
  "sembrado" desde `projects` con:
  - `project_id` (fuente de verdad para el vinculo; mas seguro que resolver solo por nombre)
  - nombre sugerido (`<proyecto> - resumen`)
  - entidad preseleccionada (si aplica)
  - guia operativa visible para crear al menos `resumen`, `curva programada` y `curva ejecutada`
  - el vinculo `DatasetType.project` se persiste al guardar el esquema si la siembra es valida
  - el esquema sigue el workflow normal de `schemas`: loader crea -> loader envia -> admin aprueba/rechaza
- Un esquema creado desde `Schemas > Nuevo Esquema` sin siembra desde `projects` sigue siendo un esquema general por `entity`
  y no queda ligado automaticamente a un `Project`.

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
- Para validador, la aprobacion historica usa `fetch` (AJAX) + polling de progreso real:
  - porcentaje por etapas
  - detalle de avance (incluye conteo de instancias cuando aplica)
  - badge visual de etapa (`Etapa X/4`) con color por fase
  - compatibilidad con redirect/mensajes Django al finalizar

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
- Endpoint de progreso para aprobacion historica del validador:
  - `validation/urls.py` -> `historical/<batch_id>/approve/progress/`
  - payload expone `percent`, `message`, `stage_index`, `stage_total`, `stage_label`

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
- `VIEWER` puro (sin rol admin/loader/validator) no usa dashboard `home`:
  - acceso a `/home/` redirige a `/kpis/` (vista principal de consumo).
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
- En `charts/charts_authority/charts_external`, el selector principal prioriza datasets fuente con datos y excluye datasets derivados de formulas (`performance`) para evitar duplicidad en consumo.
- Si el dataset seleccionado participa en una formula `APPROVED`, `charts.html` y `charts_authority.html` muestran un bloque contextual de "formula relacionada" dentro del mismo card del chart principal:
  - segundo chart de formula debajo del chart principal
  - panel derecho propio (formula, tipo de grafico, frecuencia informativa)
  - frecuencia mostrada como texto (sin selector desplegable)
- `charts_external.html` (visualizador externo mensual) no expone bloque de formula relacionada.
- Las tablas de detalle del KPI principal y de la formula relacionada se abren via boton `Mostrar tabla` en modales con export `CSV/EXCEL`.
- El panel derecho del chart principal usa ajuste dinamico de altura + scroll interno en `Indicadores (Eje Y)` para preservar visibilidad del boton de tabla.

### Modulo de desempeno / formulas (admin)
Objetivo funcional actual:
- Permitir al `ADMIN` crear formulas de desempeno/eficiencia por `entity`, usando columnas de esquemas aprobados, ver preview y materializar resultados calculados.

Modelos y servicios clave:
- `performance/models.py`
  - `PerformanceIndicator` (definicion de formula por entidad)
  - `PerformanceIndicatorInput` (variables/columnas fuente)
  - `PerformanceIndicatorResult` (resultado por periodo para preview y persistencia)
- `performance/services.py`
  - calculo de indicadores desde `PublishedDataPoint`
  - materializacion a dataset derivado (dataset + columnas + puntos publicados)

Estado implementado (MVP funcional):
- Builder por entidad en `/performance/formulas/` (solo admin).
- Variables seleccionadas desde `ColumnDef` de `DatasetType` `APPROVED` y activos de la entidad.
- Para el builder de formulas, las variables elegibles se filtran a columnas numericas (`INTEGER`, `FLOAT`).
  - No se muestran columnas no numericas (ej. `DATE` como `fecha`) en el selector de variables.
- Validacion de consistencia de periodicidad entre variables:
  - no permite mezclar columnas `DAILY`, `WEEKLY`, `MONTHLY`, etc. en una misma formula
  - si hay mezcla, bloquea guardado/aprobacion con mensaje de error
- Formula editable por texto (tokens tipo `A`, `B`, `C` + operadores `+ - * / ( )`).
- Soporta expresiones manuales tipo `(B/A)*100` usando aliases definidos en Variables.
- Preview de resultados:
  - grafico simple
  - tabla compacta (`periodo`, `valor`, `estado`)
  - usa solo periodos comunes con datos completos entre todas las variables (interseccion real)
  - rango mostrado se deriva del historico comun publicado (no solo del rango por defecto reciente)
- Flujo de aprobacion:
  - valida que existan variables y expresion
  - valida periodicidad homogenea y alinea frecuencia de materializacion con la detectada
  - aprueba formula (`PerformanceIndicator.status`)
  - materializa resultados en base de datos como dataset derivado
  - soporta progreso visual real (AJAX + polling) para procesos largos de materializacion
- Materializacion crea/actualiza:
  - `DatasetType` derivado asociado a la formula
  - nombre visible corto del derivado con formato `formula-<nombre_formula>` (evita nombres largos en lista de esquemas)
  - columnas de salida (valor y fecha/periodo segun implementacion actual)
  - `DatasetInstance` + `PublishedDataPoint`
  - en dataset derivado, la fecha materializada del resultado corresponde al `period_end` del periodo calculado
- Recalculo automatico:
  - al publicarse datos de origen (ingest/validation), formulas `APPROVED` pueden recalcularse y rematerializarse automaticamente.

Workflow y estado de formula:
- `PerformanceIndicator` maneja estado y metadatos de aprobacion:
  - `DRAFT`
  - `APPROVED`
  - `ARCHIVED` (soft delete desde UI)
- Campos de aprobacion/materializacion agregados:
  - `approved_at`
  - `approved_by`
  - referencias a dataset/columnas derivadas de salida

UX actual (iteracion en curso en `templates/performance/formulas.html`):
- Cabecera compacta:
  - nombre de formula (editable mientras no este aprobada)
  - selector de entidad
  - esquemas relacionados (referencia visual)
- El selector de entidad aplica cambios automaticamente al cambiar (GET); se elimino boton separado `Actualizar entidad`.
- Variables y Formula en cards separados (lado a lado) para evitar compresion/apilado.
- Card de Variables compactado:
  - selector con placeholder (`Selecciona una columna...`)
  - cards de variable con layout compacto (alias + acciones + selector de columna) para reducir espacio vacio
- Resumen informativo de entidad:
  - periodicidades con datos publicados
  - rango de fechas con datos publicados (min/max por `PublishedDataPoint`)
- Botones de gestion:
  - guardar nombre
  - guardar formula
  - cancelar/limpiar todo
  - aprobar formula (materializa directamente)
- Al aprobar (proceso largo):
  - modal de progreso con porcentaje real, etapa y mensaje de avance (fetch + polling)
- Tras aprobacion exitosa:
  - el builder vuelve limpio (misma entidad, sin formula seleccionada) para crear una nueva formula
- Accion explicita `Nueva formula` en cabecera para limpiar builder y mantener entidad actual.
- Lista de formulas creadas con acciones:
  - ver (carga formula + preview/grafico/tabla)
  - editar
  - eliminar (soft delete / archived) con modal de confirmacion estilizado (sin `confirm()` nativo)
- Preview de tabla con scroll vertical dedicado (para historicos largos) y scrollbar visual mejorado.
- Indicadores visuales de preview:
  - badge de frecuencia detectada
  - aviso con conteo de periodos comunes y omitidos por falta de solapamiento

Notas operativas / limitaciones actuales:
- El calculo/preview usa frecuencia/rango de trabajo en backend, pero el rango efectivo se recorta
  al historico comun publicado entre variables (periodos con datos completos).
- Flujo UX objetivo del builder: "crear columna calculada para todo el historico + nuevos datos futuros".
- Para evitar confusion con ese flujo objetivo, el card de formula no expone selector visible de periodicidad/rango; el backend conserva esos parametros de trabajo para preview/aprobacion.
- Acciones POST del builder (guardar nombre, variables, expresion) preservan el contexto de preview (`frequency`, `date_start`, `date_end`) via params ocultos/redirects.
- Aprobacion/materializacion soportada de forma controlada para `DAILY` y `MONTHLY` (alineacion con consumo en KPIs).
- El preview puede calcular por otras frecuencias (`WEEKLY`, `YEARLY`) segun implementacion backend, pero la materializacion sigue restringida a `DAILY`/`MONTHLY`.
- Cobertura automatizada de `performance` sigue baja (tests pendientes).

Rendimiento y UX reciente (`performance/formulas`):
- Apertura desde sidebar mas rapida:
  - el builder no autoselecciona formula ni recalcula preview pesado al entrar.
- Accion `Ver` reutiliza resultados guardados (`PerformanceIndicatorResult`) cuando no se pide recalc.
- Cambios de variables (agregar/guardar/eliminar) evitan recalc completo si aun no existe expresion.
- Fast path de preview por expresion:
  - precarga batch de `PublishedDataPoint` para variables fuente
  - calculo en memoria
  - persistencia de preview con `bulk_create` / `bulk_update` (evita `update_or_create` por periodo)

Mantenimiento / migraciones recientes:
- Migracion de workflow de `PerformanceIndicator` (campos de aprobacion/materializacion).
- Migracion de reparacion SQLite local para FKs legacy en tablas de performance que aun apuntaban a `plants_plant` en lugar de `structure_entity`
  (evita `IntegrityError: FOREIGN KEY constraint failed` al guardar previews/resultados).

Rendimiento y UX reciente (charts):
- Optimizaciones backend en `kpis/views.py`:
  - se evita construir `authority_dataset_tree` para usuarios que no lo requieren
  - listado de datasets con datos via consulta `EXISTS` (mejor que `JOIN + DISTINCT`)
  - cache corto para respuestas `published` del endpoint `dataset_data`
  - lectura de `PublishedDataPoint` con iteracion liviana (`values_list(...).iterator(...)`)
- Optimizaciones frontend en `static/js/kpis_charts.js`:
  - carga lazy de `xlsx` (solo al exportar Excel)
  - tabla de detalle renderiza inicialmente un subconjunto (con boton "Mostrar todas")
  - fix de cambio de tipo de grafico (`line/bar/stacked_bar`) que podia limpiar el chart por manejo de evento `change`
- Optimizaciones frontend en `static/js/performance_charts.js`:
  - carga lazy de `xlsx`
  - defer de tablas de desempeno en carga inicial (prioriza chart)
- Redisenio visual de charts (KPI y desempeno):
  - tooltip moderno, leyenda refinada, ejes/grid mas sobrios
  - barras con gradiente + esquinas redondeadas
  - lineas refinadas + area sutil (solo cuando aporta)
  - `dataZoom` inferior mejorado
  - formato corto de fechas en eje X (`10 dic`, `dic 25`, etc.) segun granularidad
- Modo ejecutivo opcional en charts:
  - menos ruido visual (menos labels/grid mas discreto/espaciado)
  - persistencia via `localStorage`
- Boton `Presentacion` por chart:
  - activa modo ejecutivo
  - abre fullscreen del chart
  - redimensiona ECharts al entrar/salir
  - ubicacion visual ajustada al extremo derecho superior del stage para no tapar info del chart
- En la UI actual no hay selector global `Operativo/Presentacion`; el control visible es local al chart principal.
- `charts_authority.html` fue alineado estructuralmente con `charts.html` en el bloque de charts para reducir divergencias visuales del panel derecho.
- Al entrar a fullscreen, cada chart muestra ayuda breve: `Presiona Esc para salir de presentacion`.

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

Logica vigente de alarmas/notificaciones (sidebar):
- Fuente unica: `accounts/context_processors.py` (`admin_flags`).
- Hay cache corta por usuario (`accounts:admin_flags:v3:user:<id>`, TTL 20s) para no recalcular en cada request.
- Las alarmas se "limpian" por dos vias:
  - por atencion de flujo (ej. aprobar/rechazar/enviar) con invalidacion explicita de cache.
  - por marca de "visto" (`last_seen_*`) en flujos donde aplica.
- Campos `last_seen_*` activos en `AccountProfile`:
  - `last_seen_schema_status` (feedback de esquemas para loader)
  - `last_seen_validation_status`
  - `last_seen_certification_alert`
  - `last_seen_project_status`
  - `last_seen_project_pending` (bandeja admin de proyectos pendientes)
- Workflow de `projects` ya invalida cache de alertas en submit/review/delete mediante
  `_invalidate_project_alert_caches(...)`.
- Workflow de `schemas` ya invalida cache de alertas en submit/approve/reject mediante
  `_invalidate_schema_alert_caches(...)` (admins/superusers/loaders afectados por entidad),
  evitando que el badge quede "pegado" tras atender una solicitud.

Sidebar:
- base: `templates/partials/sidebar.html`
- autoridad MHE: `templates/partials/sidebar_authority_mhe.html`
- switch en `templates/base.html` segun `is_authority_viewer or is_external_monthly_viewer`
- visualizadores puros (authority/external) no muestran `General > Inicio` en sidebar
- en sidebar base, `Inicio` se oculta para `VIEWER` puro (si no tiene tambien rol admin/loader/validator)

Topbar base:
- `templates/partials/topbar.html`
- estilo actual con clase `topbar-flat` (sin esquinas redondeadas / 90 grados)
- altura fija (no variable por contenido) para mantener consistencia visual entre paginas

Plantillas publicas y base visual:
- `templates/landing.html` y `templates/registration/login.html` fueron unificadas para extender `templates/base.html`.
- `templates/base.html` expone bloques adicionales para paginas publicas (sin sidebar/topbar) sin romper vistas internas:
  - `background_layer`
  - `page_layout`
  - `body_class` / `body_style`
  - `system_messages`
  - otros bloques auxiliares de estilo/transicion
- Se movieron fondos decorativos `position: fixed` (landing/login) fuera de `.app-shell` para evitar recortes visuales cuando hay `transform` durante transiciones.
- `static/css/login.css` aplica override local de `.app-shell` en login para evitar que reglas internas (`height:100vh` / `overflow:hidden`) rompan el centrado vertical.
- Transicion de rutas unificada en `base.html` con estilo `fade-through` neutro (sin "flash" azul).
- En transiciones `pane-only/query`, la animacion se aplica al contenido (`.route-content-pane`) y no al contenedor con topbar, evitando parpadeo visual del topbar.
- Layout interno con scroll contenido en `.route-main-pane`:
  - sidebar y topbar se mantienen visualmente fijos
  - `body` sin scroll vertical en paginas internas (`saas-hybrid`) para evitar doble scrollbar
  - se usa un unico scrollbar del panel principal

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
- `/projects/`

## 13. Deuda tecnica conocida (importante)
El legado de `plants` fue retirado y el flujo operativo ya esta alineado a `entity`.

Foco actual de deuda:
- Consolidar cobertura de pruebas (ingest, validation, kpis, performance).
- Normalizar textos/encoding en plantillas antiguas.
- Revisar y limpiar documentacion tecnica vieja que todavia menciona `plant/project`.
- Seguir simplificando UX del builder de formulas para alinearlo al flujo admin definido
  (entidad -> variables -> formula -> preview -> aprobacion/materializacion).

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
- Sidebar de visualizadores sin acceso visible a `Inicio` (enfoque en navegacion/KPIs).
- Restriccion mensual para visualizador externo en charts y dataset_data.
- Redireccion de `/home/` a `/kpis/` para visualizadores puros.
- Limpieza inmediata post-publicacion/materializacion + limpieza periodica por retencion en media.
- KPIs de dataset con ventana temporal reciente (3 meses) cuando aplica columna fecha.
- Charts KPI (admin y autoridad MHE) con bloque contextual de formula relacionada cuando el dataset fuente participa en una formula aprobada:
  - segundo chart dentro del mismo card del KPI principal
  - panel derecho propio con frecuencia informativa
  - tablas de detalle (KPI principal y formula) en modales con export `CSV/EXCEL`
- Selector principal de KPIs excluye datasets derivados de formulas para mantener el consumo sobre datasets fuente.
- Modulo `performance/formulas` con MVP funcional para admin:
  - creacion de formulas por entidad
  - seleccion de columnas desde esquemas aprobados
  - validacion de periodicidad homogenea entre variables (sin mezcla `DAILY/MONTHLY`)
  - expresion manual con aliases (`A`, `B`, `C`)
  - preview (grafico + tabla) sobre periodos comunes con datos completos
  - aprobacion y materializacion a dataset derivado en BD con progreso visual real
  - nombre corto de dataset derivado materializado (`formula-<nombre_formula>`)
  - auto-recalculo/rematerializacion para formulas aprobadas al publicarse datos fuente
  - acciones `Ver` y `Nueva formula`, limpieza del builder tras aprobacion exitosa
- Landing institucional con CTA de acceso refinado (una sola flecha) y favicon visible.
- Favicon del sistema generado desde `static/escudo.png` y enlazado en `base`, `landing` y `registration/login`.
- Mitigacion de microparpadeo (FOUC) en plantillas standalone (`templates/base.html`, `templates/landing.html`, `templates/registration/login.html`)
  mediante fondo inline inicial.
- Transicion visual de navegacion:
  - landing -> login con overlay/fade en `templates/landing.html` + `static/css/landing.css`
  - transicion global de entrada/salida en `templates/base.html` para navegacion full-page
    con exclusiones para HTMX/links especiales y opt-out via `data-no-route-transition`
- Estabilizacion visual de navegacion con scroll interno del panel principal (`.route-main-pane`)
  y bloqueo de scroll del `body` en paginas internas para evitar doble scrollbar.
- Modulo `projects` ya integrado:
  - rutas activas en `/projects/`
  - acceso desde sidebar base y sidebar de autoridad/external al visor de reportes
  - workflow de catalogo: loader crea/edita -> admin aprueba/rechaza
  - reportes solo visibles para proyectos aprobados
  - detalle de reportes con variantes `project` y `agreement`
  - bridge hacia `schemas` desde proyectos aprobados para sembrar creacion de esquemas
  - vinculo formal `DatasetType.project` cuando el esquema nace desde el flujo sembrado
  - autoconfiguracion inicial de `ProjectReportConfig` al aprobar el primer esquema semanal/mensual ligado al proyecto

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
5. Si se toca `projects` + `schemas`, validar manualmente:
   - proyecto `PENDING` no debe mostrar `Crear Esquemas` al loader
   - proyecto `APPROVED` si debe mostrar `Crear Esquemas`
   - el flujo sembrado debe abrir `schemas:schema_create` con nombre y `entity` precargados
   - al aprobar el primer esquema semanal/mensual ligado al proyecto debe crearse la `ProjectReportConfig` inicial
6. Si se modifica ingest/validation, probar manualmente:
   - carga historica
   - carga periodica
   - envio a validacion
   - aprobacion historica
   - acceso de admin, loader, validator y viewer
7. Si hay diferencias entre instancias publicadas y datos en KPIs, verificar `PublishedDataPoint` por dataset/periodo.
   - para visualizador externo mensual, confirmar que las instancias mensuales esten en `PUBLISHED/LOCKED`.
8. Si se toca UX de cuentas, validar formulario crear/editar usuario y creacion de memberships esperados.
9. Si se toca UX global / navegacion (`templates/base.html`, `templates/landing.html`, `templates/registration/login.html`):
   - probar paginas con y sin scroll vertical (sin salto visual notable)
   - confirmar que exista un solo scrollbar visible en paginas internas (sin doble barra viewport/panel)
   - probar links normales, links con query params, `target="_blank"` y formularios POST (logout)
   - confirmar que HTMX/Alpine no se vean interceptados por la transicion
   - usar `data-no-route-transition` en enlaces con JS propio si fuera necesario

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

## 17. Modulo `projects` (estado implementado actual)
Decision arquitectonica vigente:
- `Project` NO es un nuevo nivel oficial de `structure`.
- El dominio maestro se mantiene en `Entity`.
- `projects` opera como modulo de negocio anclado a `Category` + `Entity`, reutilizando `schemas`, `ingest`, `validation` y `PublishedDataPoint`.

Estado de integracion real:
- La app `projects` esta montada en `config/urls.py` bajo `/projects/`.
- Hay accesos en:
  - `templates/partials/sidebar.html`
  - `templates/partials/sidebar_authority_mhe.html`
- El modulo expone:
  - catalogo de proyectos/convenios (`project_list`)
  - alta/edicion/borrado operativo para loaders
  - revision administrativa (`project_review`)
  - configuracion de reportes (`ProjectReportConfig`)
  - `report_list` / `report_detail`

Modelo operativo vigente:
- `Project`:
  - pertenece a una `Category`
  - se asocia a una o varias `Entity` de esa categoria
  - incorpora workflow:
    - `PENDING`
    - `APPROVED`
    - `REJECTED`
  - guarda metadatos de workflow:
    - `created_by`
    - `approved_by`
    - `approved_at`
    - `workflow_comment`
- `ProjectReportConfig`:
  - referencia datasets validos del proyecto
  - incluye `report_variant` configurable y extensible
  - es el enlace formal entre el visor de `projects` y los esquemas `DatasetType`
  - puede crearse manualmente por admin o autogenerarse al aprobar el primer esquema operativo del proyecto

Reglas de negocio implementadas:
- El admin NO crea proyectos/convenios/etc.
- El admin crea usuarios y memberships operativos (`LOADER`, `VALIDATOR`, etc.).
- Los loaders crean y editan proyectos/convenios/etc. dentro de su alcance por entidad.
- Todo proyecto nuevo o modificado por loader vuelve a:
  - `workflow_status=PENDING`
  - `is_active=False`
- El admin aprueba o rechaza el registro.
- Solo los proyectos `APPROVED` quedan activos para:
  - aparecer en reportes
  - ser seleccionables en `ProjectReportConfig`
  - sembrar la creacion de esquemas relacionados
- Mientras el proyecto este `PENDING` o `REJECTED`, el loader no ve la accion `Crear Esquemas` en el catalogo.

Alarmas de workflow (contrato operativo actual):
- Loader:
  - ve badges de `PENDING` / `APPROVED` / `REJECTED` de sus proyectos en sidebar.
  - los contadores se filtran por `created_by` y ventana `last_seen_project_status`.
- Admin:
  - ve badge de proyectos pendientes para revision.
  - el contador usa `last_seen_project_pending` para limpiar lo ya visto.
- Esquemas:
  - admin ve badge de pendientes en `Esquemas`.
  - submit/approve/reject invalidan cache de alertas para refresco inmediato del badge.

Seguridad y consistencia ya endurecidas:
- Todas las `entities` elegidas en `Project` deben pertenecer a `Project.category`.
- Los datasets de `ProjectReportConfig` deben pertenecer a entidades incluidas en `project.entities`.
- `report_list` y `report_detail` filtran solo proyectos activos y aprobados.
- El acceso a un proyecto/reporte se resuelve por interseccion real entre `Membership.entity` y `Project.entities`.
- La vista de borradores (`source=draft`) ya NO se habilita por rol mezclado fuera de alcance:
  - `LOADER/VALIDATOR` solo ven `draft` si ese rol aplica a una entidad efectiva del proyecto
  - caso cubierto: `VIEWER(A) + LOADER(B)` no desbloquea borradores de A
- `report_detail` ignora instancias legacy fuera del alcance de entidades del proyecto.

Workflow operativo vigente (proyectos/convenios):
1. Admin crea/ajusta niveles (`Sector/Subsector/Category/Entity`) en `structure`.
2. Admin crea usuarios y memberships por `Entity`.
3. Loader registra un proyecto/convenio/etc. en `projects`.
4. El registro queda pendiente y sin activacion.
5. Admin revisa y aprueba/rechaza el registro.
6. Una vez aprobado, el loader puede iniciar la creacion de esquemas relacionados desde el propio catalogo.
7. El loader crea los esquemas en `schemas`.
8. El admin aprueba los esquemas en el workflow normal de `schemas`.
9. El loader carga datos en `ingest`.
10. Los validadores designados por admin revisan/publican en `validation`.
11. El reporte ejecutivo queda disponible para usuarios con scope.

Puente `projects` -> `schemas` (implementado):
- Desde un proyecto aprobado, el loader tiene acceso a `Crear Esquemas`.
- Ese enlace abre `schemas:schema_create` con contexto sembrado:
  - `project_id` (usado para resolver el proyecto y persistir el vinculo real)
  - nombre sugerido basado en el proyecto
  - entidad preseleccionada cuando el scope lo permite
  - bloque visual de guia en `templates/schemas/schema_edit.html`
- La UX actual exige esperar la aprobacion del proyecto antes de habilitar esa accion.
- Si el loader entra por el acceso generico de `schemas` sin pasar por `Crear Esquemas`, no hay selector visible de proyecto;
  en ese caso el esquema no queda ligado automaticamente al proyecto.
- La guia recuerda el patron operativo recomendado:
  - `resumen`
  - `curva programada`
  - `curva ejecutada`
- Aun con ese sembrado, el esquema sigue el flujo oficial:
  - loader crea/edita
  - loader envia a aprobacion
  - admin aprueba/rechaza
- Si el esquema sembrado queda ligado a un `Project` y el admin aprueba un esquema `WEEKLY` o `MONTHLY`,
  se crea automaticamente una `ProjectReportConfig` inicial para reducir errores operativos.
- En esa autoconfiguracion inicial, el mismo esquema aprobado se usa temporalmente como:
  - `report_dataset`
  - `curve_program_dataset`
  - `curve_executed_dataset`
- Esa configuracion automatica es un baseline operativo; en una iteracion posterior puede refinarse
  para separar `resumen`, `curva programada` y `curva ejecutada` en datasets distintos.

Contrato operativo de variantes y datasets (implementacion vigente):
- `ProjectReportConfig.report_variant` ahora es configurable y extensible:
  - usar `auto` para deteccion automatica
  - usar `project` para forzar layout de proyecto
  - usar `agreement` para forzar layout de convenio
  - se puede guardar cualquier otro slug futuro; por ahora cae temporalmente al layout base (`project`) hasta que exista plantilla propia
- Recomendacion de datasets por reporte semanal:
  - `report_dataset`: resumen ejecutivo / contractual del corte semanal
  - `curve_program_dataset`: plan base o curva programada
  - `curve_executed_dataset`: avance ejecutado semanal (o mensual cuando aplique)
- Contrato recomendado para `report_dataset` en variante `project`:
  - identificacion y contexto: `ubicacion`, `ejecutor`, `descripcion`, `fecha_inicio`, `fecha_conclusion`, `etapa_actual`
  - KPIs: `presupuesto_mmbs`, `ejecucion_fisica_pct`, `ejecucion_financiera_mmbs`, `programado_mmbs`, `ejecutado_mmbs`
  - narrativa: `estado_situacion`, `justificacion_desviacion`, `acciones_preventivas`, `fecha_corte`
- Contrato recomendado para `report_dataset` en variante `agreement`:
  - identificacion contractual: `empresa`, `ubicacion`, `objeto_convenio`, `suscripcion_convenio`, `adendas`, `plazo_ejecucion`, `etapa_actual`
  - KPIs: `porcentaje_planificado`, `porcentaje_ejecutado`, `fecha_corte`
  - narrativa: `estado_situacion`, `acciones_preventivas`
- Contrato recomendado para `curve_program_dataset` y `curve_executed_dataset`:
  - variante `project`:
    - formato mensual ancho: columnas por mes (`ENE..DIC`) con porcentajes
    - o formato tabular: columna `mes` + columna numerica (`programado_pct` / `ejecutado_pct`)
  - variante `agreement`:
    - formato por hitos: columna categorica (`hito`, `actividad`, `etapa`, `fase`, `indicador`, `concepto`, etc.) + columna numerica (`programado_pct` / `ejecutado_pct`)
    - fallback minimo: si no hay filas por hitos, el visor usa `porcentaje_planificado` y `porcentaje_ejecutado` del `report_dataset`
- Flujo semanal recomendado para operacion:
  1. Crear y aprobar los 3 esquemas por `entity` (`report`, `program`, `executed`).
  2. Cargar semanalmente el `report_dataset` y el `curve_executed_dataset`.
  3. Mantener `curve_program_dataset` como carga base (one-time) o actualizarlo cuando cambie la planificacion.
  4. Enviar a validacion semanal.
  5. Publicar en `validation` para que el visor consuma `PublishedDataPoint`.
  6. Usuarios con scope consultan `projects:report_detail` por semana o por gestion.

Cobertura automatizada actual del modulo:
- Ya existen pruebas en `projects/tests.py` para:
  - entidades fuera de categoria en `ProjectForm`
  - bloqueo de datasets fuera de `project.entities`
  - control de borradores por alcance efectivo
  - variante `agreement`
  - fallback para variantes futuras
  - contencion de instancias legacy fuera de scope
  - workflow basico loader/admin (crear y aprobar)
- Ya existe prueba en `schemas/tests.py` para el flujo sembrado desde `projects` hacia `schema_create`.

Pendientes practicos (siguientes iteraciones):
- Definir y crear los esquemas reales (`DatasetType`/`ColumnDef`) para:
  - resumen de proyecto
  - resumen de convenio
  - curvas programada/ejecutada
- Alinear los aliases del visor 1:1 con los nombres reales de columnas que se adopten.
- Hacer pruebas manuales de extremo a extremo con datos reales semanales.
