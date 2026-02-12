from __future__ import annotations

from django.core.management.base import BaseCommand

from ingest.file_cleanup import cleanup_ingest_files, format_bytes


class Command(BaseCommand):
    help = (
        "Limpia archivos en media asociados a ingest. "
        "Por defecto corre en dry-run y no borra nada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica borrados reales. Sin esta bandera solo reporta.",
        )
        parser.add_argument(
            "--instance-retention-days",
            type=int,
            default=90,
            help=(
                "Retencion (dias) para raw_file de instancias publicadas/bloqueadas "
                "ya materializadas."
            ),
        )
        parser.add_argument(
            "--batch-retention-days",
            type=int,
            default=180,
            help="Retencion (dias) para source_file de historicos DONE/FAILED.",
        )
        parser.add_argument(
            "--orphan-retention-days",
            type=int,
            default=7,
            help="Retencion minima (dias) para eliminar archivos huerfanos en disco.",
        )
        parser.add_argument(
            "--skip-orphans",
            action="store_true",
            help="No escanear ni eliminar huerfanos en media/ingest/raw y media/ingest/historical.",
        )
        parser.add_argument(
            "--keep-instance-ids",
            nargs="*",
            type=int,
            default=[],
            help="IDs de DatasetInstance a excluir de limpieza.",
        )
        parser.add_argument(
            "--keep-batch-ids",
            nargs="*",
            type=int,
            default=[],
            help="IDs de HistoricalImportBatch a excluir de limpieza.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        keep_instance_ids = set(options["keep_instance_ids"] or [])
        keep_batch_ids = set(options["keep_batch_ids"] or [])

        self.stdout.write(
            self.style.WARNING("Modo APPLY activo: se borraran archivos.")
            if apply_changes
            else self.style.WARNING("Modo DRY-RUN: no se borra nada.")
        )

        result = cleanup_ingest_files(
            apply_changes=apply_changes,
            instance_retention_days=options["instance_retention_days"],
            batch_retention_days=options["batch_retention_days"],
            orphan_retention_days=options["orphan_retention_days"],
            skip_orphans=options["skip_orphans"],
            keep_instance_ids=keep_instance_ids,
            keep_batch_ids=keep_batch_ids,
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Resumen de limpieza"))
        self.stdout.write(
            f"- raw_file instancias: {result.instance_count} ({format_bytes(result.instance_bytes)})"
        )
        self.stdout.write(
            f"- source_file historicos: {result.batch_count} ({format_bytes(result.batch_bytes)})"
        )
        self.stdout.write(
            f"- huerfanos en disco: {result.orphan_count} ({format_bytes(result.orphan_bytes)})"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Total {'eliminado' if apply_changes else 'detectado'}: "
                f"{result.total_count} archivos ({format_bytes(result.total_bytes)})"
            )
        )
