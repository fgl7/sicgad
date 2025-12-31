# SICGAD – Project PRD

Este documento resume lo necesario para entender y operar el proyecto SICGAD sin recurrir a otras fuentes. Está dirigido al equipo técnico (y especialmente al agente Codex) para conocer alcance, lógica funcional, componentes implementados y estado actual.

---

## 1. Propósito y visión

- **Nombre**: Sistema Integral de Carga, Gestión y Análisis de Datos (SICGAD).
- **Objetivo**: centralizar la captura de datos operativos (principalmente producción), validarlos por niveles e institución, publicar datos confiables y proveer tableros operativos/certificados con trazabilidad completa.
- **Usuarios meta**: Cargadores, Validadores (varios niveles), Visualizadores, Administradores operativos y Superadmins técnicos.
- **Valor clave**:
  - Flexibilidad para versionar esquemas sin despliegues.
  - Soporte de datasets por periodicidad: **diaria**, **semanal**, **mensual** y **proyecciones** (periodicidad no definida).
  - Automatización del flujo diario vs certificación mensual (con consolidación automática del mes anterior, revisión mensual y alertas).
  - Auditoría exhaustiva y control de seguridad (forzado de cambio de contraseña; 2FA/rate limiting planificados).

---

## 2. Scope funcional

| Módulo | Objetivo | Puntos clave |
| --- | --- | --- |
| **Accounts** | Gestión de usuarios, roles, memberships y políticas de acceso. | `Membership` vincula User+Planta+Rol+Nivel+Institución, y flags de validación: `can_validate_daily`, `can_validate_weekly`, `can_validate_monthly`, `can_validate_projections`. `AccountProfile` fuerza cambio de contraseña (`must_change_password`) y registra “last seen” para notificaciones. Edición de usuarios permite modificar datos sin reingresar contraseña; si se cambia password, se vuelve a forzar `must_change_password`. |
| **Plants** | Catálogo de plantas operativas (PCS, PICP, etc.). | Se usa para permisos y para segmentar datasets/cargas. |
| **Schemas** | Definición y versionado de esquemas por planta y periodicidad. | `DatasetType`/`ColumnDef` con metadatos completos, flujo de aprobación. El cargador puede crear esquemas **DAILY/WEEKLY/MONTHLY/FLEXIBLE (proyecciones)** para plantas habilitadas por el admin (puede tener múltiples plantas o rol global). Los esquemas no-certificación se aprueban/rechazan por el Administrador. El admin puede crear esquemas de certificación mensual derivados de esquemas diarios. |
| **Ingest** | Descarga de plantillas, carga de archivos (archivo o captura manual) y carga histórica para diarios. | La importación histórica (`HistoricalImportBatch`) aplica a **datasets diarios**. `ingest/upload` bloquea solo la **carga diaria** hasta que exista histórico; para **semanal/mensual/proyecciones** no hay gating por histórico. Plantillas usan como encabezados los `name` de las columnas. |
| **Validation** | Flujo de aprobación por periodicidad y publicación automática. | `ValidationAction` documenta nivel, decisión y comentarios. Diarios: aprobación directa a `PUBLISHED`. Semanal/Mensual/Proyecciones: flujo multi-institución (según `Membership.validation_level` por institución) y permisos separados por flag. `materialize_instance` genera `PublishedDataPoint` al publicar. |
| **KPIs** | Visualización (ECharts) de datos publicados o borradores según permisos. | Selección dinámica de instancia, eje X/Y, múltiples KPIs, filtros de fecha, tablas y modo Published/Draft. |
| **Performance** | Cálculo de indicadores de desempeño productivo y eficiencia. | Define variables metodológicas por planta y permite al admin mapear columnas de esquemas a variables de fórmulas, calculando indicadores (enfoque mensual). |
| **Audit** | Registro y consulta de eventos críticos. | `AuditLog` almacena acción, módulo, objeto, usuario y detalles; vista filtrable. |
| **Core** | Utilidades comunes. | Placeholder para helpers/mixins reutilizables. |

---

## 3. Modelos y datos clave

### 3.1 Usuarios y permisos

- Se usa el modelo estándar de `User` con extensiones:
  - `Membership`: rol (`LOADER`, `VALIDATOR`, `VIEWER`, `ADMIN`), planta (opcional para rol global), institución, nivel de validación, y flags de participación: `can_validate_daily`, `can_validate_weekly`, `can_validate_monthly`, `can_validate_projections`.
  - `AccountProfile`: `must_change_password` y marcas `last_seen_*` (notificaciones / badges).
- Middleware `accounts.middleware.PasswordChangeRequiredMiddleware` fuerza cambio de contraseña antes de navegar (exceptúa rutas permitidas y superadmins).
- El admin puede editar datos de un usuario sin reingresar contraseña; si define una nueva, se marca `must_change_password=True` para el próximo login.

### 3.2 Esquemas y columnas

- `DatasetType` controla: planta, nombre (con versión), periodicidad (`DAILY`, `WEEKLY`, `MONTHLY`, `FLEXIBLE`), si es de certificación (`is_certification`), estado (`DRAFT`/`PENDING`/`APPROVED`/`REJECTED`), slug único y metadatos.
  - `FLEXIBLE` se usa para **proyecciones** (periodicidad no definida: anual/mensual según el detalle). A nivel de flujo se valida con un permiso propio (`can_validate_projections`).
  - Esquemas de certificación mensual son `MONTHLY` y `is_certification=True`, con `source_dataset` apuntando al esquema diario base.
- `ColumnDef` almacena campos dinámicos con tipos (`INTEGER`, `FLOAT`, `STRING`, `DATE`, `BOOLEAN`, `CHOICE`) y metadatos de visualización (unidad, rol de eje, agregación por defecto, KPI principal, orden, reglas simples como rangos/regex/choices).
- El campo `name` es el identificador interno (sin espacios) y el encabezado oficial en plantillas/archivos; `label` es descripción legible.

### 3.3 Instancias y datos publicados

- `DatasetInstance` representa una carga para un `DatasetType`, planta y `period` (fecha de referencia). Estados: `DRAFT`, `SUBMITTED`, `VALIDATED_L1`, `VALIDATED_L2`, `PUBLISHED`, `LOCKED`.
- `PublishedDataPoint` guarda valores publicados por celda para consumo por KPIs/Performance.

---

## 4. Flujos principales (resumen)

1. **Definición de esquema** (loader o admin) → **envío** (`PENDING`) → **aprobación/rechazo** por admin.
2. **Carga de datos** (archivo/manual):
   - Diarios: requiere histórico inicial (gating) y permite importación histórica masiva.
   - Semanal/Mensual/Proyecciones: sin gating de histórico.
3. **Validación**:
   - Diaria: aprobación directa a `PUBLISHED`.
   - Semanal/Mensual/Proyecciones: aprobación multi-institución por niveles → `PUBLISHED` al completar requisitos.
4. **Publicación**: al llegar a `PUBLISHED`, `materialize_instance` genera `PublishedDataPoint`.
5. **Certificación mensual**: consolidación automática del mes anterior (si hay cobertura diaria completa y publicada) para esquemas `is_certification=True`.

---

## 6. Estado actual

Implementado:

- CRUD de esquemas y columnas con aprobación de admin.
- Periodicidades soportadas en esquemas: **DAILY**, **WEEKLY**, **MONTHLY**, **FLEXIBLE (proyecciones)**.
- Validaciones con permisos por periodicidad: `can_validate_daily`, `can_validate_weekly`, `can_validate_monthly`, `can_validate_projections`.
- Consolidación automática del mes anterior para **certificación mensual** derivada de diarios, con sincronización lazy de estado/alertas.
- Importación histórica masiva para datasets diarios (`HistoricalImportBatch`) y validación masiva.
- Gating de histórico: bloquea solo la **carga diaria** hasta que exista histórico; semanal/mensual/proyecciones no bloquean.
- Edición de usuario por admin sin reingresar contraseña; cambio de password vuelve a forzar `must_change_password`.
- Ajustes de UX: `templates/landing.html` muestra “Volver a Home” si el usuario está autenticado y optimiza carga (fonts + imágenes).
- Configuración de UTF-8 para el repo: `.editorconfig` y `.vscode/settings.json`.

Pendiente / por completar:

- Integrar `django-otp` y `django-axes` en settings/login.
- Configurar Celery/Redis y tareas programadas para consolidaciones/alertas (hoy es lazy).
- Definir convención de `period` para WEEKLY/MONTHLY/FLEXIBLE (ej. inicio de semana / fin de mes / año) y ajustar UI para reducir errores.
- Implementar pruebas unitarias/integración (actualmente no hay tests).
- Internacionalización completa (textos mezclan español/inglés en algunas vistas/JS).
- Ajustes para despliegue a PostgreSQL y storage de archivos fuera del filesystem local.

---

## 7. Referencias rápidas

- `config/settings.py`: configuración general, apps registradas y middleware custom.
- `config/urls.py`: rutas principales (`landing`, `home`, `kpis`, `ingest`, `validate`, etc.).
- `accounts/models.py`, `accounts/forms.py`, `accounts/views.py`: roles, permisos por periodicidad, creación/edición de usuarios.
- `schemas/models.py`, `schemas/views.py`, `schemas/services.py`: CRUD/versionado de esquemas + consolidación de certificación mensual.
- `ingest/models.py`, `ingest/views.py`, `ingest/utils.py`: carga diaria/histórica, batches y materialización.
- `validation/views.py`, `validation/services.py`: bandejas y lógica de estado por periodicidad.
- `kpis/views.py`, `static/js/kpis_charts.js`: dashboards y API de datos para gráficos.
- `audit/utils.py`, `audit/views.py`: registro y consulta de auditoría.
- Docs complementarios: `docs/logic.md` (visión funcional alta) y `docs/tasks.md` (roadmap).

---

## 8. Suposiciones y riesgos

Suposiciones:

- Habrá al menos un Admin operativo distinto del superusuario para aprobar esquemas y gestionar cuentas.
- Los validadores tienen niveles numéricos consecutivos (por institución) que determinan el flujo.
- Los archivos de carga usan encabezados exactamente iguales a los `name` definidos en columnas.
- El gating de histórico aplica solo a datasets **diarios**.

Riesgos:

- Validaciones de negocio por columna aún son básicas (principalmente estructura/tipos). Falta motor de reglas.
- Escalabilidad limitada en SQLite; migración a PostgreSQL debe planificarse.
- Falta de tests incrementa riesgo de regresiones.
- Seguridad parcial (2FA/axes no conectados aún) puede dejar huecos si se despliega sin completar.
- Importaciones históricas grandes pueden ser lentas (ideal mover a jobs asíncronos).

---

## 9. Próximos pasos sugeridos

1. Completar `django-otp` + `django-axes` y endurecer seguridad de login.
2. Definir y documentar convención de `period` para WEEKLY/MONTHLY/FLEXIBLE (y ajustar UI/validaciones).
3. Añadir Celery y tareas programadas para consolidaciones/alertas.
4. Diseñar motor de validaciones de reglas basado en `ColumnDef` (rangos, regex, dependencias).
5. Implementar test suite (pytest/Django test runner) cubriendo flujos críticos (carga, validación, publicación, KPIs, certificación).
6. Planificar despliegue: PostgreSQL, STATIC/MEDIA, WSGI/ASGI, CI/CD.

---

### Resumen final

Con este PRD puedes continuar el desarrollo de SICGAD entendiendo: quiénes participan, cómo se modelan los datos, qué flujos existen, qué módulos conforman la solución y qué queda pendiente.
