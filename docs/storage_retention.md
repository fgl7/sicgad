# Politica de Retencion de Archivos de Ingesta

## Objetivo
Evitar crecimiento no controlado de `media/` conservando trazabilidad operativa.

## Politica implementada
1. Al reemplazar o borrar registros con archivos (`DatasetInstance.raw_file`, `HistoricalImportBatch.source_file`, `DatasetChangeAttachment.file`), el archivo fisico se elimina automaticamente.
2. Al publicar y materializar correctamente, se limpia en el momento:
- Borra `raw_file` de instancias `PUBLISHED`/`LOCKED` con `PublishedDataPoint`.
- Borra `source_file` de historicos `DONE/FAILED` cuando ya no tienen instancias pendientes.
3. Limpieza automatica periodica dentro de la app (sin comando manual):
- Borra `raw_file` de instancias en `PUBLISHED/LOCKED`, ya materializadas, y fuera de retencion.
- Borra `source_file` de historicos `DONE/FAILED`, fuera de retencion, y sin instancias pendientes.
- Borra archivos huerfanos antiguos en `media/ingest/raw` y `media/ingest/historical`.

## Configuracion automatica (settings/.env)
- `AUTO_INGEST_CLEANUP_ENABLED` (default `True`)
- `AUTO_INGEST_CLEANUP_INTERVAL_SECONDS` (default `21600`, 6 horas)
- `AUTO_INGEST_CLEANUP_LOCK_TIMEOUT_SECONDS` (default `600`)
- `AUTO_INGEST_INSTANCE_RETENTION_DAYS` (default `90`)
- `AUTO_INGEST_BATCH_RETENTION_DAYS` (default `180`)
- `AUTO_INGEST_ORPHAN_RETENTION_DAYS` (default `7`)
- `AUTO_INGEST_SKIP_ORPHANS` (default `False`)

## Comando opcional (manual/auditoria)
`python manage.py ingest_cleanup_files`

Por defecto corre en **dry-run** (no borra):
`python manage.py ingest_cleanup_files`

Aplicar borrado real:
`python manage.py ingest_cleanup_files --apply`

## Exclusiones por auditoria
- Excluir instancias concretas:
`--keep-instance-ids 10 25 31`
- Excluir batches concretos:
`--keep-batch-ids 4 9`
