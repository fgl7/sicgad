from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from performance.models import PerformanceIndicator, PerformanceIndicatorResult
from performance.services import compute_indicator, month_window
from structure.models import Entity


class Command(BaseCommand):
    help = "Calcula indicadores de desempeno para una entidad y mes, usando mapeos Admin y PublishedDataPoint."

    def add_arguments(self, parser):
        parser.add_argument("--entity", help="Codigo de entidad.")
        parser.add_argument("--month", required=True, help="Mes en formato YYYY-MM.")
        parser.add_argument(
            "--frequency",
            choices=["MONTHLY", "DAILY"],
            default="MONTHLY",
            help="Frecuencia del calculo (MONTHLY por defecto).",
        )
        parser.add_argument("--dry-run", action="store_true", help="No escribe resultados en BD.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Sobrescribe resultados existentes para ese indicador/mes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        entity_code: str = (options.get("entity") or "").strip()
        month_raw: str = options["month"]
        dry_run: bool = options["dry_run"]
        overwrite: bool = options["overwrite"]
        frequency: str = options["frequency"]

        if not entity_code:
            raise CommandError("Debe indicar --entity CODIGO.")
        entity = Entity.objects.filter(code=entity_code, is_active=True).first()
        if not entity:
            raise CommandError(f"Entidad no encontrada: {entity_code}")

        try:
            year_s, month_s = month_raw.split("-", 1)
            year = int(year_s)
            month = int(month_s)
            if month < 1 or month > 12:
                raise ValueError
        except ValueError:
            raise CommandError("Formato invalido de --month. Use YYYY-MM (ej: 2025-10).")

        window = month_window(year, month)

        indicators = list(
            PerformanceIndicator.objects.filter(entity=entity, is_active=True)
            .prefetch_related("variables")
            .order_by("key")
        )
        if not indicators:
            self.stdout.write(self.style.WARNING(f"No hay indicadores activos para {entity.code}."))
            return

        created = 0
        updated = 0
        not_calculable = 0
        errors = 0

        for indicator in indicators:
            value, status, trace = compute_indicator(indicator, window, frequency=frequency)

            existing = PerformanceIndicatorResult.objects.filter(
                indicator=indicator,
                entity=entity,
                period_end=window.period_end,
                frequency=frequency,
            ).first()

            if existing and not overwrite:
                self.stdout.write(f"[skip] {indicator.key} (existe; use --overwrite)")
                continue

            if status == PerformanceIndicatorResult.STATUS_NOT_CALCULABLE:
                not_calculable += 1
            elif status == PerformanceIndicatorResult.STATUS_ERROR:
                errors += 1

            if dry_run:
                self.stdout.write(f"[dry] {indicator.key} -> {status} value={value}")
                continue

            if existing:
                existing.period_start = window.period_start
                existing.stage = "DRAFT"
                existing.frequency = frequency
                existing.status = status
                existing.numeric_value = value
                existing.text_value = ""
                existing.trace = trace
                existing.save(
                    update_fields=[
                        "period_start",
                        "stage",
                        "frequency",
                        "status",
                        "numeric_value",
                        "text_value",
                        "trace",
                        "computed_at",
                    ]
                )
                updated += 1
            else:
                PerformanceIndicatorResult.objects.create(
                    indicator=indicator,
                    entity=entity,
                    period_start=window.period_start,
                    period_end=window.period_end,
                    frequency=frequency,
                    stage="DRAFT",
                    status=status,
                    numeric_value=value,
                    text_value="",
                    trace=trace,
                )
                created += 1

            self.stdout.write(f"[ok] {indicator.key} -> {status} value={value}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Resumen: created={created}, updated={updated}, not_calculable={not_calculable}, errors={errors}"
                + (" (dry-run)" if dry_run else "")
            )
        )
