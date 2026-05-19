# SICGAD

SICGAD es un sistema Django para gestionar el ciclo completo de datos institucionales: definicion de esquemas, carga de informacion, validacion por niveles, publicacion para KPIs, auditoria y reportes operativos.

El dominio funcional vigente esta centrado en `Entity`. La jerarquia organizacional principal es:

1. `Sector`
2. `Subsector`
3. `Category`
4. `Entity`

Las asociaciones operativas de usuarios, esquemas, cargas, validaciones, KPIs y proyectos se resuelven por `Entity`.

## Modulos principales

- `structure`: administra niveles organizacionales (`Sector`, `Subsector`, `Category`, `Entity`).
- `accounts`: usuarios, perfiles, roles y memberships por entidad.
- `schemas`: definicion y workflow de esquemas de datos.
- `ingest`: carga periodica, carga historica, edicion y gestion de archivos.
- `validation`: bandejas de validacion, aprobacion, publicacion y materializacion de datos.
- `kpis`: visualizacion de indicadores y tablas desde datos publicados.
- `performance`: formulas de desempeno por entidad y materializacion de resultados derivados.
- `projects`: catalogo de proyectos/convenios, aprobacion administrativa y reportes ejecutivos.
- `audit`: trazabilidad de acciones relevantes.

## Roles y alcance

Los roles operativos se gestionan mediante `Membership`:

- `ADMIN`: administrador operativo del sistema.
- `LOADER`: carga esquemas y datos dentro de su entidad.
- `VALIDATOR`: valida datos segun periodicidades habilitadas.
- `VIEWER`: consume KPIs y reportes segun su alcance.

Los visualizadores pueden tener perfiles adicionales:

- `STANDARD`
- `EXTERNAL_MONTHLY`
- `AUTHORITY_MHE`

Los perfiles jerarquicos (`EXTERNAL_MONTHLY` y `AUTHORITY_MHE`) pueden tener alcance multiple por sector, subsector, categoria y entidad. En ejecucion, la navegacion y el acceso se construyen desde los memberships activos.

## Flujo operativo general

1. El admin configura la jerarquia institucional en `structure`.
2. El admin crea usuarios y asigna memberships por `Entity`.
3. El loader crea esquemas en `schemas`.
4. El loader envia los esquemas a aprobacion.
5. El admin aprueba o rechaza los esquemas.
6. El loader carga datos en `ingest`.
7. Los validadores revisan y publican en `validation`.
8. La publicacion materializa datos en `PublishedDataPoint`.
9. KPIs, formulas y reportes consumen datos publicados.

## Esquemas y datos

Los esquemas se modelan principalmente con:

- `DatasetType`
- `ColumnDef`

Cada `DatasetType` pertenece operativamente a una `Entity` y puede tener frecuencia de validacion diaria, semanal, mensual o flexible. El workflow principal de esquemas es:

- `DRAFT`
- `PENDING`
- `APPROVED`
- `REJECTED`

Las cargas de datos usan `DatasetInstance`, con estados:

- `DRAFT`
- `SUBMITTED`
- `VALIDATED_L1`
- `VALIDATED_L2`
- `PUBLISHED`
- `LOCKED`

La fuente de verdad para analitica y KPIs es `PublishedDataPoint`. Una instancia publicada sin puntos materializados no aparece en KPIs o tablas analiticas.

## Validacion y publicacion

Los validadores ven bandejas segun:

- entidades asignadas,
- rol `VALIDATOR`,
- permisos por periodicidad.

Al publicar datos:

- se materializan puntos en `PublishedDataPoint`,
- se ejecuta limpieza best-effort de archivos de ingest ya materializados,
- se disparan consolidaciones mensuales cuando aplican,
- las formulas aprobadas pueden recalcularse automaticamente.

## KPIs y visualizadores

La vista principal de consumo es `/kpis/`.

Plantillas principales:

- `kpis/charts.html`: visualizador estandar.
- `kpis/charts_external.html`: visualizador externo mensual.
- `kpis/charts_authority.html`: autoridad MHE.

Reglas destacadas:

- El scope por memberships se aplica siempre, salvo admin global.
- Los viewers puros son redirigidos de `/home/` a `/kpis/`.
- `EXTERNAL_MONTHLY` solo consume datasets mensuales.
- `AUTHORITY_MHE` navega por sector, subsector, categoria y entidad.
- Los datasets derivados de formulas se excluyen del selector principal para evitar duplicidad.

## Formulas de desempeno

El modulo `performance` permite al admin crear formulas por entidad usando columnas numericas de esquemas aprobados.

Capacidades principales:

- variables con aliases (`A`, `B`, `C`, etc.),
- expresiones como `(B/A)*100`,
- validacion de periodicidad homogenea,
- preview con grafico y tabla,
- aprobacion y materializacion a dataset derivado,
- recalculo automatico cuando se publican datos fuente.

Los datasets derivados usan nombres cortos del tipo `formula-<nombre_formula>`.

## Proyectos y reportes

El modulo `projects` esta anclado a `Category` y `Entity`; no reemplaza la jerarquia oficial de `structure`.

Workflow:

1. El loader crea un proyecto, convenio u otro registro operativo.
2. El registro queda `PENDING` e inactivo.
3. El admin aprueba o rechaza.
4. Solo registros `APPROVED` quedan activos para reportes y creacion de esquemas relacionados.

Desde un proyecto aprobado, el loader puede iniciar la creacion de esquemas relacionados. Ese flujo siembra datos como `project_id`, nombre sugerido y entidad preseleccionada, pero el esquema sigue el workflow normal de `schemas`.

## Reglas importantes de desarrollo

- Priorizar siempre el dominio `Entity`.
- No reintroducir dependencias al dominio legado `plants`.
- No dejar secretos reales en el repositorio.
- Usar `.env` local/servidor y `.env.example` como plantilla segura.
- En frontend, evitar CSS y JS embebido en templates.
- Reutilizar primero los assets existentes en `static/css` y `static/js`.
- Para layouts operativos, revisar antes `static/css/data_workbench.css`.

## Seguridad

El proyecto incluye endurecimientos ya aplicados:

- login con `never_cache`,
- logout solo por `POST`,
- middleware para cambio obligatorio de contrasena,
- validadores nativos de Django en alta/edicion administrativa,
- validacion centralizada de uploads,
- restricciones de extensiones y tamanos de archivo,
- control de acceso por entidad,
- mitigacion de open redirect en ingest,
- settings preparados para cookies y headers seguros en despliegue.

## Verificacion recomendada

Comando base:

```bash
python manage.py check
```

Pruebas relevantes mencionadas en el PRD:

```bash
python manage.py test validation.tests projects.tests ingest.tests
```

Si se modifican consolidaciones mensuales, validar en entorno de prueba:

```bash
python manage.py consolidate_certifications --backfill
```

## Archivos clave

- `structure/models.py`
- `accounts/models.py`
- `accounts/forms.py`
- `accounts/views.py`
- `config/settings.py`
- `schemas/models.py`
- `schemas/views.py`
- `ingest/models.py`
- `ingest/security.py`
- `validation/views.py`
- `kpis/views.py`
- `performance/views.py`
- `projects/models.py`
- `templates/base.html`
- `templates/partials/sidebar.html`
- `templates/partials/sidebar_authority_mhe.html`

## Estado practico

SICGAD ya cubre gestion de niveles, usuarios, esquemas, cargas historicas y periodicas, validacion, publicacion, KPIs, visualizadores jerarquicos, formulas de desempeno, proyectos/convenios y reportes ejecutivos.

La deuda tecnica principal esta en ampliar cobertura de pruebas, normalizar textos legacy con problemas de encoding, limpiar documentacion antigua y seguir refinando la UX del builder de formulas.
