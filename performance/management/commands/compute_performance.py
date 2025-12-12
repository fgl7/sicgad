from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from performance.models import PerformanceIndicator, PerformanceIndicatorResult
from performance.services import compute_indicator_for_stage, month_window
from plants.models import Plant


class Command(BaseCommand):
    help = "Calcula indicadores de desempeño para una planta y mes, usando mapeos Admin y PublishedDataPoint."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True, help="Código de planta (PCS/PIKCL/PICL).")
        parser.add_argument("--month", required=True, help="Mes en formato YYYY-MM.")
        parser.add_argument("--dry-run", action="store_true", help="No escribe resultados en BD.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Sobrescribe resultados existentes para ese indicador/mes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        plant_code: str = options["plant"]
        month_raw: str = options["month"]
        dry_run: bool = options["dry_run"]
        overwrite: bool = options["overwrite"]

        plant = Plant.objects.filter(code=plant_code).first()
        if not plant:
            raise CommandError(f"Planta no encontrada: {plant_code}")

        try:
            year_s, month_s = month_raw.split("-", 1)
            year = int(year_s)
            month = int(month_s)
            if month < 1 or month > 12:
                raise ValueError
        except ValueError:
            raise CommandError("Formato inválido de --month. Use YYYY-MM (ej: 2025-10).")

        window = month_window(year, month)

        indicators = list(
            PerformanceIndicator.objects.filter(plant=plant, is_active=True)
            .prefetch_related("variables")
            .order_by("key")
        )
        if not indicators:
            self.stdout.write(self.style.WARNING(f"No hay indicadores activos para {plant.code}."))
            return

        created = 0
        updated = 0
        not_calculable = 0
        errors = 0

        for indicator in indicators:
            for stage in ("DRAFT", "CERTIFIED"):
                value, status, trace = compute_indicator_for_stage(indicator, window, stage=stage)

                existing = PerformanceIndicatorResult.objects.filter(
                    indicator=indicator,
                    plant=plant,
                    period_end=window.period_end,
                    stage=stage,
                ).first()

                if existing and not overwrite:
                    self.stdout.write(f"[skip] {indicator.key} {stage} (existe; use --overwrite)")
                    continue

                if status == PerformanceIndicatorResult.STATUS_NOT_CALCULABLE:
                    not_calculable += 1
                elif status == PerformanceIndicatorResult.STATUS_ERROR:
                    errors += 1

                if dry_run:
                    self.stdout.write(f"[dry] {indicator.key} {stage} -> {status} value={value}")
                    continue

                if existing:
                    existing.period_start = window.period_start
                    existing.stage = stage
                    existing.status = status
                    existing.numeric_value = value
                    existing.text_value = ""
                    existing.trace = trace
                    existing.save(
                        update_fields=[
                            "period_start",
                            "stage",
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
                        plant=plant,
                        period_start=window.period_start,
                        period_end=window.period_end,
                        stage=stage,
                        status=status,
                        numeric_value=value,
                        text_value="",
                        trace=trace,
                    )
                    created += 1

                self.stdout.write(f"[ok] {indicator.key} {stage} -> {status} value={value}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Resumen: created={created}, updated={updated}, not_calculable={not_calculable}, errors={errors}"
                + (" (dry-run)" if dry_run else "")
            )
        )
