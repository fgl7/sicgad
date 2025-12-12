from __future__ import annotations

import csv

from django.core.management.base import BaseCommand

from performance.models import PerformanceVariable


class Command(BaseCommand):
    help = "Exporta un CSV plantilla para mapear variables metodológicas a fuentes SICGAD."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="performance_mapping_template.csv",
            help="Ruta del archivo CSV a generar.",
        )

    def handle(self, *args, **options):
        output_path: str = options["output"]

        fields = [
            "variable_key",
            "plant_code",
            "dataset_slug",
            "column_name",
            "stage",  # DRAFT/CERTIFIED
            "aggregation",  # SUM/AVG/MAX/MIN/LAST/NONE
            "transform",  # NONE/MULTIPLY/ADD
            "transform_value",
            "offset_months",
            "notes",
            "is_active",
        ]

        qs = PerformanceVariable.objects.select_related("plant").order_by("plant__code", "key")
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for v in qs:
                writer.writerow(
                    {
                        "variable_key": v.key,
                        "plant_code": v.plant.code,
                        "dataset_slug": "",
                        "column_name": "",
                        "stage": "DRAFT",
                        "aggregation": "SUM",
                        "transform": "NONE",
                        "transform_value": "",
                        "offset_months": "0",
                        "notes": "",
                        "is_active": "1",
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Generado: {output_path} ({qs.count()} filas)"))
