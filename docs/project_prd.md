# SICGAD – Project PRD

Este documento resume todo lo necesario para entender y operar el proyecto SICGAD sin recurrir a otras fuentes. Está dirigido al equipo técnico (y especialmente al agente Codex) para conocer alcance, lógica funcional, componentes implementados y estado actual.

---

## 1. Propósito y visión

- **Nombre**: Sistema Integral de Carga, Gestión y Análisis de Datos (SICGAD).
- **Objetivo**: Centralizar la captura diaria de producción de plantas YLB/MHE, validar la información por niveles, publicar datos confiables y proveer tableros operativos/certificados con trazabilidad completa.
- **Usuarios meta**: Cargadores, Validadores (varios niveles), Visualizadores, Administradores operativos y Superadmins técnicos.
- **Valor clave**:
  - Flexibilidad para versionar esquemas sin despliegues.
  - Automatización del flujo diario vs certificación mensual (con consolidación automática, revisión mensual y alertas escalonadas).
  - Auditoría exhaustiva y control de seguridad (2FA planificada, rate limiting, must-change-password).

---

## 2. Scope funcional

| Módulo | Objetivo | Puntos clave |
| --- | --- | --- |
| **Accounts** | Gestión de usuarios, roles, membresías y políticas de acceso. | `Membership` vincula User+Planta+Rol+Nivel+Institución, `AccountProfile` fuerza cambio de contraseña y registra notificaciones (banderas `last_seen_*` para limpiar badges). Middleware especializado. |
| **Plants** | Catálogo de plantas operativas (PCS, PICP, etc.). | Se usa para permisos y para segmentar datasets/cargas. |
| **Schemas** | Definición y versionado de esquemas de datos por planta. | `DatasetType`/`ColumnDef` con metadatos completos, flujo de aprobación, creación de esquemas de certificación a partir de diarios. Los esquemas diarios los propone el cargador y los aprueba/rechaza el Administrador. |
| **Ingest** | Descarga de plantillas, carga de archivos diarios (archivo o captura manual) y carga histórica inicial obligatoria. | Soporta importación histórica masiva (`HistoricalImportBatch`) que crea múltiples `DatasetInstance` y permite envío/validación en conjunto. `ingest/upload` bloquea la carga diaria hasta que exista histórico y luego oculta “Importar histórico”. Las plantillas usan como encabezados los `name` de las columnas (export Excel). |
| **Validation** | Flujo de aprobación diario/mensual y publicación automática. | `ValidationAction` documenta nivel, decisión y comentarios; la bandeja filtra instancias ya aprobadas tras el último envío y actualiza `last_seen_certification_alert`. `materialize_instance` genera datos publicados cuando se llega a PUBLISHED. |
| **KPIs** | Visualización (ECharts) de datos publicados o borradores según permisos. | Selección dinámica de instancia, eje X/Y, múltiples KPIs, filtros de fecha, tablas y modo Published/Draft que refleja datos diarios certificados. |
| **Performance** | Cálculo de indicadores de desempeño productivo y eficiencia de procesos. | Define variables metodológicas por planta y permite al Administrador mapear columnas de esquemas a variables de las fórmulas (ej. Fórmula 1 PCS), calculando indicadores mensuales en estado Draft/Certificado. |
| **Audit** | Registro y consulta de eventos críticos. | `AuditLog` almacena acción, módulo, objeto, usuario, detalles; vista filtrable hasta 500 eventos. |
| **Core** | Placeholder para utilidades comunes (aún vacío). | Se espera usarlo para mixins/helpers reutilizables. |

---

## 3. Modelos y datos clave

### 3.1 Usuarios y permisos
- Se usa el modelo estándar de `User` con extensiones:
  - `Membership`: define rol (`LOADER`, `VALIDATOR`, `VIEWER`, `ADMIN`), planta, nivel de validación, flags `can_validate_daily/monthly` e institución (`YLB`/`MHE`).
  - `AccountProfile`: campos `must_change_password`, `last_seen_schema_status` y `last_seen_validation_status` (para limpiar notificaciones del loader al revisar su bandeja).
- Middleware `PasswordChangeRequiredMiddleware` fuerza cambio de contraseña antes de navegar, excepto para rutas permitidas y superadmins.
- Decoradores y context processors detectan flags de rol para UI/notificaciones.

### 3.2 Esquemas y columnas
- `DatasetType` controla: planta, nombre (con versión), frecuencia (`DAILY`/`MONTHLY`), si es de certificación, estado (`DRAFT`→`PENDING`→`APPROVED`/`REJECTED`), slug único y metadatos.
- `ColumnDef` almacena campos dinámicos con tipos (`INTEGER`, `FLOAT`, `STRING`, `DATE`, `BOOLEAN`, `CHOICE`), reglas (rangos, regex, choices), metadatos de visualización (unidad, rol de eje, agregación por defecto, KPI principal, orden). El campo `name` es el identificador interno (sin espacios) y además el encabezado oficial en plantillas/archivos; el campo `label` es una descripción legible que explica a qué se refiere la columna y qué datos espera.
- Los cargadores crean/editar borradores (si no son admins) desde una pantalla guiada que incluye ayuda sobre cada columna. Los admins aprueban/rechazan y pueden generar esquemas de certificación copiando columnas desde un dataset diario.

### 3.3 Instancias y datos publicados
- `DatasetInstance`: instancia de carga con referencias al esquema (`DatasetType`), planta, periodo (fecha), estado (DRAFT→SUBMITTED→VALIDATED_L1/L2→PUBLISHED→LOCKED), archivo cargado, métricas de error, `submitted_at` (tracking de envíos) y autor (`Membership`).
- `HistoricalImportBatch`: agrupa una importación histórica (un archivo) por `DatasetType`+planta, con rango detectado (`period_start`/`period_end`) y estado (`RUNNING`/`DONE`/`FAILED`). Cada fila del archivo crea una `DatasetInstance` ligada por `DatasetInstance.historical_batch` para habilitar envío/validación masiva.
- `PublishedDataPoint`: tabla desnormalizada que almacena cada valor publicado (numérico, texto, fecha, booleano) por fila/columna para servir a dashboards y KPIs.
- `materialize_instance(instance)`:
  1. Limpia puntos previos del dataset.
  2. Lee el archivo original (Excel/CSV) y mapea encabezados a columnas activas usando los `name` de las columnas como referencia principal (acepta `label` solo como compatibilidad hacia atrás).
  3. Convierte valores al tipo correcto y crea `PublishedDataPoint` masivamente.

### 3.4 Módulo de desempeño (Performance)
- Se modelan variables metodológicas por planta (`PerformanceVariable`), siguiendo las fórmulas del documento de propuesta (`prop_desemp.docx`) para PCS, KCl y Li2CO3.
- `PerformanceVariableMapping` permite al Administrador (rol `ADMIN`, no el superusuario técnico) asignar columnas de esquemas (`DatasetType`/`ColumnDef`) a cada variable de fórmula, especificando agregaciones (SUM/AVG/MAX/MIN/LAST/NONE), desfase de meses (`offset_months`, por ejemplo Δt en PCS) y etapa (`DRAFT`/`CERTIFIED`).
- `PerformanceIndicator` define indicadores (por ejemplo Fórmula 1 PCS, rendimiento mensual %), con descripción de la fórmula y lista de variables requeridas.
- `PerformanceIndicatorResult` almacena resultados por planta, mes y etapa (`DRAFT`/`CERTIFIED`), junto con trazas JSON que permiten reconstruir qué variables y fuentes se usaron.

---

## 4. Flujos principales

### 4.1 Definición/aprobación de esquemas
1. Loader crea/edita esquema y columnas desde el frontend (`schemas/schema_edit`).
2. Envía a aprobación (`STATUS_PENDING`); queda inactivo hasta que Admin actúe.
3. Admin revisa, aprueba (activo) o rechaza con comentario.
4. Para certificación mensual, Admin clona columnas seleccionadas de un dataset diario y crea un `DatasetType` `MONTHLY`/`is_certification=True`.

### 4.2 Carga y envío de datos
1. **Primera carga (histórico obligatorio)**: si el dataset aún no tiene datos, `ingest/upload` bloquea la carga diaria (UI borrosa/inhabilitada) y solo habilita “Importar histórico” con descarga de plantilla Excel.
2. La importación histórica (XLSX/CSV) crea un `HistoricalImportBatch` y genera múltiples `DatasetInstance` (uno por fecha/período) en `STATE_DRAFT`, vinculadas al batch.
3. El cargador envía el histórico completo a validación con un solo botón (`submit_historical_batch`), marcando todas las instancias del batch como `STATE_SUBMITTED` y registrando `submitted_at`.
4. **Carga diaria**: una vez publicado el histórico, se habilita el flujo normal: subir archivo diario (CSV/XLSX) **o** capturar manualmente desde `ingest/upload/manual`; ambos crean un `DatasetInstance` en borrador.
5. Al estar listo, envía (`submit_instance`) → estado `STATE_SUBMITTED` y se marca `submitted_at`. El historial del cargador muestra alertas amarillas (pendientes), rojas (rechazados) y el histórico de certificaciones con enlaces a la revisión mensual.

### 4.3 Validación
- **Histórico (validación masiva)**:
  - La bandeja incluye una sección de históricos pendientes (por batch). Al aprobar un histórico (`approve_historical_batch`), se publican todas las instancias del batch y se materializan para consumo/KPIs.
- **Diaria (operativa)**:
  - Solo nivel operativo (ej. Jefe de planta). Al aprobar, pasa directo a `PUBLISHED`, se materializa y alimenta KPIs diarios.
- **Mensual/certificación**:
  - A partir de los datasets diarios publicados, el sistema consolida automáticamente el mes anterior en una instancia mensual (cuando se crea el esquema y cada vez que cierra un mes). Los validadores reciben alertas el primer día hábil del nuevo mes hasta revisar la consolidación.
  - El cargador revisa la consolidación desde `certification_review`: ve todos los días del mes, se marcan los modificados, cada cambio requiere una justificación y soportes y puede enviarse a validación directamente desde esa pantalla (se registra `submitted_at`).
  - Secuencia de validadores `can_validate_monthly` por nivel. Cada `ValidationAction` registra decisión/comentario y la lógica compara los niveles ya aprobados (ignorando la acción actual) para fijar el estado real: `SUBMITTED` → `VALIDATED_L1` → … → `PUBLISHED`.
  - Rechazo devuelve a `DRAFT`, limpia `submitted_at` y guarda comentario en `last_error_summary`.

### 4.4 Visualización y consumo
- `kpis/charts` lista instancias publicadas y, si corresponde, borradores visibles para loaders/validadores/admins.
- El script `static/js/kpis_charts.js`:
  - Filtra instancias por modo (published/draft).
  - Permite elegir columnas para eje X y múltiples KPIs en eje Y.
  - Aplica filtros de fecha cuando exista una columna DATE en el eje X.
  - Permite alternar entre datos publicados o borradores (según permisos).
- `dataset_data` sirve JSON estructurado con metadatos, filas y estado actual.

### 4.5 Auditoría y notificaciones
- `record_action` registra cada evento relevante en `AuditLog`.
- Vistas y context processors muestran contadores de elementos pendientes para admins/validadores, notificaciones de esquemas aprobados/rechazados para cargadores y alertas de certificación mensual (chips en menú y panel en la bandeja). Los contadores consideran `last_seen_certification_alert` y si el validador ya aprobó el envío vigente.
- `validation/admin_overview` incluye un resumen de cobertura (último día diario publicado y última consolidación generada) para cada esquema de certificación.
- `audit/logs` permite filtrar logs por usuario, acción, rango de fechas o “solo mis eventos”.

---

## 5. Stack tecnológico

- **Backend**: Python 3.x, Django 5.2.8, SQLite (dev), `django-environ` para configuración.
- **Seguridad**: `django-axes`, `django-otp` (pendiente de integrar en vistas), 2FA planificado.
- **Asíncronía**: Celery + Redis contemplados en requirements (sin `config/celery.py`), mientras que las consolidaciones automáticas se ejecutan hoy mediante verificación lazy al iniciar sesión o con `manage.py consolidate_certifications`.
- **Frontend**: Plantillas Django, TailwindCSS via CDN, HTMX 2.0, Alpine.js 3.x, Apache ECharts para gráficos.
- **Recursos estáticos**: `static/css/app.css` (tema oscuro), `static/js` con scripts específicos por módulo.

---

## 6. Estado actual

- Proyecto inicializado con todas las apps y rutas principales funcionales.
- Modelos y vistas implementan el flujo completo básico (carga → validación → publicación → KPIs) usando SQLite.
- Consolidación automática del mes anterior para esquemas de certificación, con revisión mensual (justificaciones y adjuntos por día/mes), alertas sincronizadas con sidebar y lógica multi-nivel corregida.
- Historial del cargador ampliado con panel de certificaciones (pendientes, rechazadas e histórico) y badges por estado.
- UI de esquemas ajustada: edición solo en `DRAFT`/`REJECTED`; la lista/detalle muestran aprobador/estado y fecha de aprobación.
- Notificaciones en sidebar para cargadores: rechazos persisten hasta que el cargador modifique y re-envíe; aprobaciones se limpian al visitar la sección de esquemas.
- Importación histórica implementada: `ingest/upload` exige cargar histórico antes de habilitar carga diaria; el histórico se envía y valida en bloque (batch) y, una vez publicado, “Importar histórico” deja de mostrarse.
- Auditoría operativa y paneles básicos completados.
- Pendiente:
  - Integrar `django-otp` y `django-axes` en settings/login.
  - Configurar Celery/Redis y tareas programadas para ejecutar consolidaciones/alertas sin depender de tráfico interactivo (hoy es lazy).
  - Desarrollar UI para solicitud/aprobación de cambios de esquema más detallada (multi-niveles, comentarios).
  - Implementar pruebas unitarias/integración (actualmente no hay tests).
  - Internacionalización completa (textos mezclan español/inglés, falta traducción formal).
  - Ajustes para despliegue a PostgreSQL y manejo de storage de archivos fuera del filesystem local.

---

## 7. Referencias rápidas

- **Entradas principales**:
  - `config/settings.py` – configuración general, apps registradas y middleware custom.
  - `accounts/context_processors.py` – banderas de permisos, contadores y sección actual.
  - `schemas/views.py` – lógica de CRUD/versionado de esquemas.
  - `ingest/models.py` + `ingest/views.py` + `ingest/utils.py` – carga diaria/histórica, batches y materialización.
  - `templates/ingest/upload.html`, `templates/ingest/upload_historical.html`, `templates/ingest/upload_history.html`, `static/js/ingest_upload.js` – UI de carga, gating y plantilla Excel.
  - `validation/views.py` + `templates/validate/inbox.html` – bandejas, reglas de estado y validación masiva de históricos.
  - `kpis/views.py` + `static/js/kpis_charts.js` – dashboard de datos.
  - `audit/utils.py` + `audit/views.py` – registro y consulta de auditorías.
- **Docs complementarios**: `docs/logic.md` (visión funcional alta) y `docs/tasks.md` (roadmap paso a paso). Este PRD actúa como índice operativo unificado.

---

## 8. Suposiciones y riesgos

- **Suposiciones**:
  - Habrá al menos un Admin operativo distinto del superusuario para aprobar esquemas y gestionar cuentas.
  - Los validadores tienen niveles numéricos consecutivos que determinan el flujo.
  - Los archivos de carga utilizan encabezados exactamente iguales a los `name` definidos en las columnas; los `label` se usan solo como descripciones legibles para usuarios.
  - Todo dataset requiere una carga histórica inicial antes de habilitar la carga diaria (gating en `ingest/upload`).
- **Riesgos**:
  - Falta de validaciones de negocio en backend (solo estructura). Será necesario implementar reglas por columna/campo.
  - Escalabilidad limitada en SQLite; migración a PostgreSQL debe planificarse pronto.
  - Falta de test coverage incrementa riesgo de regresiones.
  - Seguridad parcial (2FA/axes no conectados aún) puede dejar huecos si se despliega sin completar.
  - Procesamiento síncrono de archivos históricos grandes puede ser lento; ideal mover import/validación masiva a jobs asíncronos (Celery).

---

## 9. Próximos pasos sugeridos

1. Finalizar integración de `django-otp` y `django-axes` con configuración de login/middleware.
2. Añadir Celery y tareas programadas para ejecutar consolidaciones/alertas sin depender de requests (recalcular certificaciones y disparar notificaciones a horas controladas).
3. Migrar base de datos a PostgreSQL y mover storage de archivos a un backend externo (S3, Azure Blob, etc.).
4. Diseñar motor de validaciones de reglas basado en `ColumnDef` (rangos, regex, dependencias entre columnas).
5. Implementar test suite (pytest/Django test runner) cubriendo flujos críticos (carga, aprobación, publicación, KPIs y certificación mensual).
6. Documentar e implementar proceso de despliegue (settings para prod, STATIC/MEDIA, WSGI/ASGI, CI/CD).

---

### Resumen final

Con este PRD puedes iniciar o continuar el desarrollo de SICGAD entendiendo: quiénes participan, cómo se modelan los datos, qué flujos existen, qué módulos conforman la solución y qué queda pendiente. Es el punto de partida para cualquier mejora o diagnóstico rápido del sistema.
