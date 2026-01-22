# SICGAD – Visión general funcional

SICGAD (Sistema Integral de Carga, Gestión y Análisis de Datos) es una plataforma web basada en Django que permite:

- Definir y versionar **esquemas** de datos por planta o por proyecto, y por periodicidad.
- Cargar datos (archivo o captura manual) para distintos tipos de datasets.
- Validar los datos con un flujo de aprobación por **niveles** y por **institución**.
- Publicar y visualizar datos confiables (KPIs) con trazabilidad y auditoría.
- Consolidar automáticamente la **certificación mensual** derivada de datos diarios (cuando existe cobertura completa y publicada).
- Configurar y visualizar **reportes de proyectos** (resumen + curvas) para seguimiento de inversiones.

El sistema está orientado a YLB y MHE para seguimiento operativo y certificación de producción.

---

## Tipos de usuarios y permisos

Los permisos se asignan mediante `Membership` (usuario + rol + planta/proyecto opcional + institución + nivel + flags). Un `Membership` con `plant = NULL` y `project = NULL` representa un rol **global** (todas las plantas/proyectos).

### Roles

- **Cargador (LOADER)**
  - Puede crear y proponer esquemas para las plantas/proyectos que el admin le habilitó.
  - Puede cargar datasets según esquemas aprobados.
  - Puede ver datos en borrador y publicados (según reglas de cada módulo).

- **Validador (VALIDATOR)**
  - Revisa y aprueba/rechaza datasets enviados a validación.
  - Tiene un `validation_level` y una `institution` obligatoria.
  - El admin define en el membership qué flujos puede validar:
    - `can_validate_daily`
    - `can_validate_weekly`
    - `can_validate_monthly`
    - `can_validate_projections` (proyecciones / periodicidad no definida)

- **Visualizador (VIEWER)**
  - Acceso a visualización de datos publicados (oficiales).

- **Administrador (ADMIN)**
  - Gestiona usuarios/memberships.
  - Aprueba/rechaza esquemas propuestos por cargadores.
  - Crea esquemas de **certificación mensual** derivados de esquemas diarios.

- **Superadmin**
  - Usuario técnico (Django superuser).

### Seguridad

- Cambio de contraseña obligatorio en el primer inicio (`AccountProfile.must_change_password`), enforced por `PasswordChangeRequiredMiddleware`.
- Recomendado: 2FA + rate limiting (pendiente de integrar).

---

## Periodicidades de los datasets

`DatasetType.validation_frequency` soporta:

- `DAILY`: carga y validación diaria (operación).
- `WEEKLY`: carga y validación semanal.
- `MONTHLY`: carga y validación mensual (no-certificación) y también certificación mensual (cuando `is_certification=True`).
- `FLEXIBLE`: “periodicidad no definida”, usada para **proyecciones** (pueden ser anuales o mensuales según el detalle).

Nota: la convención exacta del campo `DatasetInstance.period` para WEEKLY/MONTHLY/FLEXIBLE debe definirse y documentarse (pendiente). Hoy se usa un `DateField`.

---

## Flujo general de datos

1. **Definir esquema** (tipo de dataset).
2. **Aprobar esquema** (admin) cuando aplica.
3. **Cargar datos** (archivo o manual) → se crea `DatasetInstance` en `DRAFT`.
4. **Enviar a validación** → estado `SUBMITTED`.
5. **Validar**:
   - `DAILY`: aprobación directa a `PUBLISHED`.
   - `WEEKLY`/`MONTHLY`/`FLEXIBLE`: aprobación multi-institución por niveles hasta completar requisitos → `PUBLISHED`.
6. **Publicar**:
   - Al llegar a `PUBLISHED`, se materializa a `PublishedDataPoint` para consumo por KPIs.
7. **Certificación mensual** (especial):
   - Se consolidan automáticamente datasets mensuales de certificación (derivados de diarios) para el mes anterior cuando hay cobertura diaria completa publicada.

---

## 1) Definición y versionado de esquemas

En lugar de crear/alterar tablas físicas por cada cambio, SICGAD define **esquemas lógicos versionados**:

- `DatasetType`: define planta **o proyecto**, nombre, versión, periodicidad, estado, y si es certificación.
- `ColumnDef`: define las columnas del esquema (nombre técnico `name`, etiqueta `label`, tipo, unidad, orden, etc.).

Flujo de aprobación:

- El cargador crea/edita esquemas **no-certificación** y los envía a aprobación (`PENDING`).
- El admin aprueba (`APPROVED`) o rechaza (`REJECTED`).
- El admin crea esquemas de **certificación mensual** (`MONTHLY`, `is_certification=True`) a partir de un esquema diario base (`source_dataset`).

Controles adicionales en esquemas:

- El LOADER puede eliminar esquemas en `DRAFT` siempre que aún no hayan sido enviados a aprobación y no existan cargas asociadas.
- El ADMIN puede marcar esquemas como **carga única** (`DatasetType.is_one_time=True`) para proteger esquemas estáticos (por ejemplo, proyecciones o valores iniciales). Cuando un esquema es de carga única, el sistema evita recargas y exige justificación para correcciones controladas.

---

## 2) Carga de datos (Ingest)

### Carga normal (archivo / manual)

- El cargador sube archivos o captura manualmente datos para un `DatasetType` aprobado.
- Se crea una `DatasetInstance` en `DRAFT`.
- Luego la envía a validación (`SUBMITTED`).

Controles adicionales en carga:

- Esquemas de **carga única** (`DatasetType.is_one_time=True`): si ya existe una instancia, el esquema no aparece para cargar nuevamente; para corregir una instancia existente se exige **justificación** y se registra en auditoría.
- Curvas acumuladas semanales por mes (caso especial): para esquemas tipo `curva_s_ejecutado_*` (semanales con columnas Enero..Diciembre), al cargar una semana solo se permite modificar el mes del periodo; los meses anteriores quedan bloqueados y el sistema valida que no se alteren (aplica tanto a carga por archivo como captura manual).

### Carga histórica (solo diarios)

Para `DAILY`, existe importación histórica masiva:

- `HistoricalImportBatch` divide un archivo con múltiples fechas en múltiples `DatasetInstance`.
- Puede enviarse a validación en bloque y aprobarse masivamente.

Gating:

- El “bloqueo por histórico” aplica solo para `DAILY`.
- Para `WEEKLY`/`MONTHLY`/`FLEXIBLE` no se exige histórico previo.

---

## 3) Validación y publicación

### Estados principales

`DatasetInstance.state`: `DRAFT` → `SUBMITTED` → `VALIDATED_L1/L2` → `PUBLISHED` (y `LOCKED` para escenarios especiales).

### Lógica por periodicidad

- **Diaria (`DAILY`)**: aprobación directa a `PUBLISHED`.
- **Semanal (`WEEKLY`)**: multi-institución/multi-nivel si así está configurado por memberships.
- **Mensual (`MONTHLY`)**:
  - No-certificación: multi-institución/multi-nivel.
  - Certificación (`is_certification=True`): instancia mensual derivada de diarios (con revisión/justificaciones si aplica).
- **Proyecciones (`FLEXIBLE`)**: se valida con permisos específicos (`can_validate_projections`) y misma lógica multi-institución.

### Publicación (materialización)

Al publicar, `materialize_instance` convierte el archivo bruto en `PublishedDataPoint`, que es la fuente para KPIs y cálculos posteriores.

---

## 4) KPIs y visualización

El módulo de KPIs consume datos publicados (y, según permisos, también borradores):

- ECharts para gráficos.
- Selección dinámica de dataset, columnas, series y rangos de fecha.

---

## 5) Certificación mensual (consolidación automática)

Para esquemas de certificación mensual (derivados de diarios):

- El sistema consolida el mes anterior si hay cobertura diaria completa y publicada.
- Genera/actualiza una `DatasetInstance` mensual para el último día del mes anterior y la deja lista para su validación mensual.
- La consolidación y sincronización de alertas se ejecuta de forma **lazy** al iniciar sesión/navegar (pendiente mover a jobs programados).

---

## 6) Performance (desempeño)

El módulo de desempeño está pensado para calcular indicadores (mensuales) a partir de datos publicados:

- Variables metodológicas por planta, mapeo de columnas a variables, fórmulas versionadas.
- Soporte de desfases `delta_t` (PCS: mes de extracción vs mes de cristalización) y trazabilidad de cálculos.

---

## 7) Proyectos y reportes (upstream recursos evaporíticos)

Además del dominio de producción por planta, SICGAD incorpora un dominio de **proyectos** para seguimiento de inversiones en upstream:

- `Project` permite asociar un proyecto a múltiples plantas/unidades operativas.
- Los esquemas (`DatasetType`) pueden ser por **proyecto** (en vez de planta), permitiendo capturar información de ejecución/curvas y reportes de gestión.
- `ProjectReportConfig` permite al ADMIN configurar, por proyecto, qué esquemas alimentan un reporte:
  - dataset principal (resumen),
  - curva S programada,
  - curva S ejecutada.
- La vista de reporte soporta filtros por gestión, fuente (publicados/borradores según permisos) y selección semanal cuando el ejecutado es semanal (el reporte alinea resumen y curvas al corte seleccionado).

---

## Plantillas HTML principales (referencia)

- Base/layout: `templates/base.html`, `templates/partials/sidebar.html`, `templates/partials/topbar.html`
- Landing: `templates/landing.html` (si el usuario está autenticado muestra “Volver a Home”)
- Accounts: `templates/accounts/admin_user_list.html`, `templates/accounts/admin_user_create.html`, `templates/accounts/admin_user_edit.html`
- Schemas: `templates/schemas/schema_list.html`, `templates/schemas/schema_detail.html`, `templates/schemas/schema_edit.html`
- Ingest: `templates/ingest/upload.html`, `templates/ingest/upload_historical.html`, `templates/ingest/upload_history.html`
- Validation: `templates/validate/inbox.html`, `templates/validate/detail.html`, `templates/validate/admin_overview.html`
- KPIs: `templates/kpis/charts.html`, `templates/kpis/home.html`
- Audit: `templates/audit/events.html`
- Projects: `templates/projects/project_list.html`, `templates/projects/project_form.html`, `templates/projects/report_list.html`, `templates/projects/report_detail.html`

---

## Pendientes recomendados (técnicos)

- Definir convención de `period` para WEEKLY/MONTHLY/FLEXIBLE y validar input en UI/backend.
- Integrar `django-otp` + `django-axes`.
- Mover consolidación/alertas a tareas programadas (Celery/Redis).
- Motor de validación por reglas basado en `ColumnDef`.
- Formalizar qué esquemas requieren reglas especiales (por ejemplo, bloqueo mensual para `curva_s_ejecutado_*`) usando un flag/modelo dedicado en vez de depender solo de nombre/slug.
- Suite de tests.
