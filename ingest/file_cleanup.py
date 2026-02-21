from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ingest.models import DatasetInstance, HistoricalImportBatch


def safe_file_size(file_field) -> int:
    try:
        return int(file_field.size or 0)
    except Exception:
        return 0


def format_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


@dataclass
class CleanupResult:
    instance_count: int = 0
    instance_bytes: int = 0
    batch_count: int = 0
    batch_bytes: int = 0
    orphan_count: int = 0
    orphan_bytes: int = 0

    @property
    def total_count(self) -> int:
        return self.instance_count + self.batch_count + self.orphan_count

    @property
    def total_bytes(self) -> int:
        return self.instance_bytes + self.batch_bytes + self.orphan_bytes

    def as_dict(self) -> dict:
        return {
            "instance_count": self.instance_count,
            "instance_bytes": self.instance_bytes,
            "batch_count": self.batch_count,
            "batch_bytes": self.batch_bytes,
            "orphan_count": self.orphan_count,
            "orphan_bytes": self.orphan_bytes,
            "total_count": self.total_count,
            "total_bytes": self.total_bytes,
        }


def cleanup_ingest_files(
    *,
    apply_changes: bool,
    instance_retention_days: int = 90,
    batch_retention_days: int = 180,
    orphan_retention_days: int = 7,
    skip_orphans: bool = False,
    keep_instance_ids: set[int] | None = None,
    keep_batch_ids: set[int] | None = None,
) -> CleanupResult:
    now = timezone.now()
    instance_cutoff = now - timedelta(days=max(0, instance_retention_days))
    batch_cutoff = now - timedelta(days=max(0, batch_retention_days))
    orphan_cutoff = now - timedelta(days=max(0, orphan_retention_days))

    keep_instance_ids = keep_instance_ids or set()
    keep_batch_ids = keep_batch_ids or set()

    result = CleanupResult()

    instance_result = _cleanup_instance_raw_files(
        cutoff=instance_cutoff,
        apply_changes=apply_changes,
        keep_ids=keep_instance_ids,
    )
    result.instance_count = instance_result["count"]
    result.instance_bytes = instance_result["bytes"]

    batch_result = _cleanup_historical_source_files(
        cutoff=batch_cutoff,
        apply_changes=apply_changes,
        keep_ids=keep_batch_ids,
    )
    result.batch_count = batch_result["count"]
    result.batch_bytes = batch_result["bytes"]

    if not skip_orphans:
        orphan_result = _cleanup_orphans(
            cutoff=orphan_cutoff,
            apply_changes=apply_changes,
        )
        result.orphan_count = orphan_result["count"]
        result.orphan_bytes = orphan_result["bytes"]

    return result


def cleanup_files_after_publication(
    *,
    instance_ids: set[int] | None = None,
    batch_ids: set[int] | None = None,
    apply_changes: bool = True,
) -> CleanupResult:
    """
    Limpia de inmediato archivos de instancias/batches ya publicables-materializados.

    Se usa al finalizar aprobaciones para no esperar a la ventana de retención
    periódica del middleware.
    """
    result = CleanupResult()

    if instance_ids:
        instance_result = _cleanup_instance_raw_files(
            cutoff=None,
            apply_changes=apply_changes,
            keep_ids=set(),
            only_ids=set(instance_ids),
        )
        result.instance_count = instance_result["count"]
        result.instance_bytes = instance_result["bytes"]

    if batch_ids:
        batch_result = _cleanup_historical_source_files(
            cutoff=None,
            apply_changes=apply_changes,
            keep_ids=set(),
            only_ids=set(batch_ids),
        )
        result.batch_count = batch_result["count"]
        result.batch_bytes = batch_result["bytes"]

    return result


def _cleanup_instance_raw_files(
    *,
    cutoff=None,
    apply_changes: bool,
    keep_ids: set[int],
    only_ids: set[int] | None = None,
):
    queryset = (
        DatasetInstance.objects.filter(
            state__in=[DatasetInstance.STATE_PUBLISHED, DatasetInstance.STATE_LOCKED],
        )
        .exclude(raw_file="")
        .filter(raw_file__isnull=False)
        .exclude(pk__in=keep_ids)
        .filter(published_points__isnull=False)
        .distinct()
    )
    if cutoff is not None:
        queryset = queryset.filter(updated_at__lt=cutoff)
    if only_ids is not None:
        if not only_ids:
            return {"count": 0, "bytes": 0}
        queryset = queryset.filter(pk__in=only_ids)

    removed_count = 0
    removed_bytes = 0

    for instance in queryset.iterator(chunk_size=200):
        if not (instance.raw_file and instance.raw_file.name):
            continue
        file_size = safe_file_size(instance.raw_file)

        if apply_changes:
            instance.raw_file.delete(save=False)
            instance.raw_file = ""
            instance.save(update_fields=["raw_file"])

        removed_count += 1
        removed_bytes += file_size

    return {"count": removed_count, "bytes": removed_bytes}


def _cleanup_historical_source_files(
    *,
    cutoff=None,
    apply_changes: bool,
    keep_ids: set[int],
    only_ids: set[int] | None = None,
):
    pending_states = [
        DatasetInstance.STATE_DRAFT,
        DatasetInstance.STATE_SUBMITTED,
        DatasetInstance.STATE_VALIDATED_L1,
        DatasetInstance.STATE_VALIDATED_L2,
    ]

    queryset = (
        HistoricalImportBatch.objects.filter(
            status__in=[
                HistoricalImportBatch.STATUS_DONE,
                HistoricalImportBatch.STATUS_FAILED,
            ],
        )
        .exclude(source_file="")
        .filter(source_file__isnull=False)
        .exclude(pk__in=keep_ids)
        .exclude(instances__state__in=pending_states)
        .distinct()
    )
    if cutoff is not None:
        queryset = queryset.filter(created_at__lt=cutoff)
    if only_ids is not None:
        if not only_ids:
            return {"count": 0, "bytes": 0}
        queryset = queryset.filter(pk__in=only_ids)

    removed_count = 0
    removed_bytes = 0

    for batch in queryset.iterator(chunk_size=100):
        if not (batch.source_file and batch.source_file.name):
            continue
        file_size = safe_file_size(batch.source_file)

        if apply_changes:
            batch.source_file.delete(save=False)
            batch.source_file = ""
            batch.save(update_fields=["source_file"])

        removed_count += 1
        removed_bytes += file_size

    return {"count": removed_count, "bytes": removed_bytes}


def _cleanup_orphans(*, cutoff, apply_changes: bool):
    media_root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    if not media_root.exists() or not media_root.is_dir():
        return {"count": 0, "bytes": 0}

    referenced = set(
        DatasetInstance.objects.exclude(raw_file="")
        .filter(raw_file__isnull=False)
        .values_list("raw_file", flat=True)
    )
    referenced.update(
        HistoricalImportBatch.objects.exclude(source_file="")
        .filter(source_file__isnull=False)
        .values_list("source_file", flat=True)
    )

    target_dirs = [media_root / "ingest" / "raw", media_root / "ingest" / "historical"]

    removed_count = 0
    removed_bytes = 0

    for root in target_dirs:
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(media_root).as_posix()
            if rel in referenced:
                continue

            modified = timezone.make_aware(
                timezone.datetime.fromtimestamp(path.stat().st_mtime),
                timezone.get_current_timezone(),
            )
            if modified >= cutoff:
                continue

            file_size = int(path.stat().st_size)
            if apply_changes:
                path.unlink(missing_ok=True)

            removed_count += 1
            removed_bytes += file_size

    return {"count": removed_count, "bytes": removed_bytes}
