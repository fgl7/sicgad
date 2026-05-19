# SICGAD

SICGAD is a Django-based system for managing the full lifecycle of institutional data: schema definition, data ingestion, multi-level validation, KPI publication, auditing, and operational reporting.

The current functional domain is centered on `Entity`. The main organizational hierarchy is:

1. `Sector`
2. `Subsector`
3. `Category`
4. `Entity`

Operational associations for users, schemas, uploads, validations, KPIs, and projects are resolved through `Entity`.

## Main Modules

- `structure`: manages organizational levels (`Sector`, `Subsector`, `Category`, `Entity`).
- `accounts`: users, profiles, roles, and memberships by entity.
- `schemas`: data schema definition and approval workflow.
- `ingest`: periodic uploads, historical uploads, editing, and file handling.
- `validation`: validation inboxes, approval, publication, and data materialization.
- `kpis`: indicator and table visualization from published data.
- `performance`: performance formulas by entity and materialization of derived results.
- `projects`: project/agreement catalog, administrative approval, and executive reports.
- `audit`: traceability for relevant system actions.

## Roles and Scope

Operational roles are managed through `Membership`:

- `ADMIN`: operational system administrator.
- `LOADER`: creates schemas and uploads data within their entity scope.
- `VALIDATOR`: validates data according to enabled periodicities.
- `VIEWER`: consumes KPIs and reports according to their assigned scope.

Viewers can also have additional profile types:

- `STANDARD`
- `EXTERNAL_MONTHLY`
- `AUTHORITY_MHE`

Hierarchical viewer profiles (`EXTERNAL_MONTHLY` and `AUTHORITY_MHE`) can have multiple scopes across sectors, subsectors, categories, and entities. At runtime, navigation and access are built from the user's active memberships.

## General Operational Flow

1. The admin configures the institutional hierarchy in `structure`.
2. The admin creates users and assigns memberships by `Entity`.
3. The loader creates schemas in `schemas`.
4. The loader submits schemas for approval.
5. The admin approves or rejects schemas.
6. The loader uploads data in `ingest`.
7. Validators review and publish data in `validation`.
8. Publication materializes data into `PublishedDataPoint`.
9. KPIs, formulas, and reports consume published data.

## Schemas and Data

Schemas are mainly modeled with:

- `DatasetType`
- `ColumnDef`

Each `DatasetType` belongs operationally to an `Entity` and can have a daily, weekly, monthly, or flexible validation frequency. The main schema workflow is:

- `DRAFT`
- `PENDING`
- `APPROVED`
- `REJECTED`

Data uploads use `DatasetInstance`, with the following states:

- `DRAFT`
- `SUBMITTED`
- `VALIDATED_L1`
- `VALIDATED_L2`
- `PUBLISHED`
- `LOCKED`

The source of truth for analytics and KPIs is `PublishedDataPoint`. A published instance without materialized points does not appear in KPIs or analytical tables.

## Validation and Publication

Validators see inboxes according to:

- assigned entities,
- the `VALIDATOR` role,
- periodicity permissions.

When data is published:

- points are materialized into `PublishedDataPoint`,
- best-effort cleanup runs for already materialized ingest files,
- monthly consolidations are triggered when applicable,
- approved formulas can be recalculated automatically.

## KPIs and Viewers

The main consumption view is `/kpis/`.

Main templates:

- `kpis/charts.html`: standard viewer flow.
- `kpis/charts_external.html`: external monthly viewer.
- `kpis/charts_authority.html`: MHE authority viewer.

Key rules:

- Membership-based scope is always applied, except for global admins.
- Pure viewers are redirected from `/home/` to `/kpis/`.
- `EXTERNAL_MONTHLY` can only consume monthly datasets.
- `AUTHORITY_MHE` navigates by sector, subsector, category, and entity.
- Formula-derived datasets are excluded from the main selector to avoid duplication.

## Performance Formulas

The `performance` module allows admins to create formulas by entity using numeric columns from approved schemas.

Main capabilities:

- variables with aliases (`A`, `B`, `C`, etc.),
- expressions such as `(B/A)*100`,
- homogeneous periodicity validation,
- preview with chart and table,
- approval and materialization into a derived dataset,
- automatic recalculation when source data is published.

Derived datasets use short names in the format `formula-<formula_name>`.

## Projects and Reports

The `projects` module is anchored to `Category` and `Entity`; it does not replace the official `structure` hierarchy.

Workflow:

1. The loader creates a project, agreement, or other operational record.
2. The record remains `PENDING` and inactive.
3. The admin approves or rejects it.
4. Only `APPROVED` records become active for reports and related schema creation.

From an approved project, the loader can start creating related schemas. That flow pre-fills data such as `project_id`, a suggested name, and the selected entity, but the schema still follows the standard `schemas` workflow.

## Important Development Rules

- Always prioritize the `Entity` domain.
- Do not reintroduce dependencies on the legacy `plants` domain.
- Do not store real secrets in the repository.
- Use local/server `.env` files and keep `.env.example` as the safe template.
- In frontend work, avoid embedding CSS and JS directly in templates.
- Reuse existing assets in `static/css` and `static/js` first.
- For operational layouts, check `static/css/data_workbench.css` before creating new layout patterns.

## Security

The project already includes several hardening measures:

- login with `never_cache`,
- logout only via `POST`,
- middleware for mandatory password changes,
- native Django password validators in administrative user creation/editing,
- centralized upload validation,
- file extension and size restrictions,
- entity-based access control,
- open redirect mitigation in ingest flows,
- settings prepared for safer cookies and security headers in deployment.

## Recommended Verification

Base command:

```bash
python manage.py check
```

Relevant tests mentioned in the PRD:

```bash
python manage.py test validation.tests projects.tests ingest.tests
```

If monthly consolidations are modified, validate in a test environment:

```bash
python manage.py consolidate_certifications --backfill
```

## Key Files

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

## Practical Status

SICGAD already covers level management, users, schemas, historical and periodic uploads, validation, publication, KPIs, hierarchical viewers, performance formulas, projects/agreements, and executive reports.

The main technical debt is expanding test coverage, normalizing legacy text with encoding issues, cleaning up old documentation, and continuing to refine the formula builder UX.
