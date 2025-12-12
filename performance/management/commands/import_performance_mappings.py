from __future__ import annotations

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from performance.models import PerformanceVariable, PerformanceVariableMapping
from schemas.models import ColumnDef, DatasetType


def _parse_bool(raw: str) -> bool:
    v = (raw or "").strip().lower()
    return v in ("1", "true", "t", "yes", "y", "si", "s")


class Command(BaseCommand):
    help = "Importa mapeos de variables desde un CSV (solo actualiza/crea)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Ruta del CSV a importar.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valida y muestra resumen sin escribir en la BD.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path: str = options["csv_path"]
        dry_run: bool = options["dry_run"]

        created = 0
        updated = 0
        skipped = 0

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            required_cols = {"variable_key", "dataset_slug", "column_name"}
            if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
                raise CommandError(f"CSV debe contener columnas: {sorted(required_cols)}")

            for row in reader:
                variable_key = (row.get("variable_key") or "").strip()
                dataset_slug = (row.get("dataset_slug") or "").strip()
                column_name = (row.get("column_name") or "").strip()

                if not variable_key or not dataset_slug or not column_name:
                    skipped += 1
                    continue

                variable = PerformanceVariable.objects.filter(key=variable_key).first()
                if not variable:
                    raise CommandError(f"Variable no encontrada: {variable_key}")

                dataset = DatasetType.objects.filter(slug=dataset_slug).first()
                if not dataset:
                    raise CommandError(f"DatasetType no encontrado por slug: {dataset_slug}")

                column = ColumnDef.objects.filter(dataset_type=dataset, name=column_name).first()
                if not column:
                    raise CommandError(f"ColumnDef no encontrada: {dataset_slug}.{column_name}")

                aggregation = (row.get("aggregation") or "SUM").strip().upper()
                transform = (row.get("transform") or "NONE").strip().upper()
                stage = (row.get("stage") or "DRAFT").strip().upper() or "DRAFT"
                transform_value_raw = (row.get("transform_value") or "").strip()
                offset_months_raw = (row.get("offset_months") or "0").strip()
                notes = (row.get("notes") or "").strip()
                is_active = _parse_bool(row.get("is_active") or "1")

                transform_value = None
                if transform_value_raw != "":
                    try:
                        transform_value = float(transform_value_raw)
                    except ValueError:
                        raise CommandError(f"transform_value inválido para {variable_key}: {transform_value_raw}")

                try:
                    offset_months = int(offset_months_raw)
                except ValueError:
                    raise CommandError(f"offset_months inválido para {variable_key}: {offset_months_raw}")

                existing = PerformanceVariableMapping.objects.filter(
                    variable=variable,
                    dataset_type=dataset,
                    column=column,
                    offset_months=offset_months,
                    stage=stage,
                ).first()

                if dry_run:
                    created += 1 if existing is None else 0
                    updated += 1 if existing is not None else 0
                    continue

                if existing is None:
                    PerformanceVariableMapping.objects.create(
                        variable=variable,
                        dataset_type=dataset,
                        column=column,
                        aggregation=aggregation,
                        transform=transform,
                        transform_value=transform_value,
                        offset_months=offset_months,
                        stage=stage,
                        notes=notes,
                        is_active=is_active,
                    )
                    created += 1
                else:
                    existing.aggregation = aggregation
                    existing.transform = transform
                    existing.transform_value = transform_value
                    existing.notes = notes
                    existing.is_active = is_active
                    existing.save(update_fields=["aggregation", "transform", "transform_value", "notes", "is_active", "updated_at"])
                    updated += 1

        msg = f"Resumen: created={created}, updated={updated}, skipped={skipped}"
        if dry_run:
            msg += " (dry-run)"
        self.stdout.write(self.style.SUCCESS(msg))
