from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from performance.models import PerformanceVariable, PerformanceVariableMapping
from schemas.models import ColumnDef, DatasetType


@dataclass(frozen=True)
class MappingTemplate:
    variable_key: str
    dataset_name: str
    column_name: str
    aggregation: str


class Command(BaseCommand):
    help = "Crea mapeos por defecto (Admin) para las variables metodológicas usando los esquemas seed de Tarea 16."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe en BD.")

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]

        created = 0
        skipped = 0

        for tmpl in _templates():
            variable = PerformanceVariable.objects.filter(key=tmpl.variable_key).select_related("plant").first()
            if not variable:
                raise CommandError(f"Variable no encontrada: {tmpl.variable_key}")

            dataset = (
                DatasetType.objects.filter(
                    plant=variable.plant,
                    name=tmpl.dataset_name,
                )
                .order_by("-version")
                .first()
            )
            if not dataset:
                raise CommandError(f"DatasetType no encontrado: {variable.plant.code} / {tmpl.dataset_name}")

            column = ColumnDef.objects.filter(dataset_type=dataset, name=tmpl.column_name).first()
            if not column:
                raise CommandError(f"ColumnDef no encontrada: {dataset.slug}.{tmpl.column_name}")

            exists = PerformanceVariableMapping.objects.filter(
                variable=variable,
                dataset_type=dataset,
                column=column,
                offset_months=0,
                stage="DRAFT",
            ).exists()
            if exists:
                skipped += 1
                continue

            if not dry_run:
                PerformanceVariableMapping.objects.create(
                    variable=variable,
                    dataset_type=dataset,
                    column=column,
                    aggregation=tmpl.aggregation,
                    transform="NONE",
                    transform_value=None,
                    offset_months=0,
                    stage="DRAFT",
                    notes="Autogenerado por auto_map_performance_variables",
                    is_active=True,
                )
            created += 1

        msg = f"Resumen: created={created}, skipped={skipped}"
        if dry_run:
            msg += " (dry-run)"
        self.stdout.write(self.style.SUCCESS(msg))


def _templates() -> list[MappingTemplate]:
    return [
        # PCS
        MappingTemplate(
            "pcs.brine_volume_m3",
            "Desempeño PCS - Extracción de salmuera (por pozo)",
            "volumen_salm_m3",
            "SUM",
        ),
        MappingTemplate(
            "pcs.brine_density_g_cm3",
            "Desempeño PCS - Extracción de salmuera (por pozo)",
            "densidad_g_cm3",
            "AVG",
        ),
        MappingTemplate(
            "pcs.tds_pct",
            "Desempeño PCS - Extracción de salmuera (por pozo)",
            "tds_pct",
            "AVG",
        ),
        MappingTemplate(
            "pcs.salts_mass_tm",
            "Desempeño PCS - Producción de sales (por tipo)",
            "masa_producida_tm",
            "SUM",
        ),
        MappingTemplate(
            "pcs.pool_area_effective_m2",
            "Desempeño PCS - Operación de piscinas (evaporación/cristales)",
            "area_efectiva_m2",
            "AVG",
        ),
        MappingTemplate(
            "pcs.crystal_height_m",
            "Desempeño PCS - Operación de piscinas (evaporación/cristales)",
            "altura_cristal_m",
            "AVG",
        ),
        MappingTemplate(
            "pcs.evaporated_volume_real_m3",
            "Desempeño PCS - Operación de piscinas (evaporación/cristales)",
            "volumen_evaporado_real_m3",
            "SUM",
        ),
        MappingTemplate(
            "pcs.evaporated_volume_theoretical_m3",
            "Desempeño PCS - Evaporación teórica (modelo externo)",
            "volumen_evaporado_teorico_m3",
            "NONE",
        ),
        MappingTemplate(
            "pcs.energy_equivalent_boe",
            "Desempeño PCS - Energía equivalente",
            "energia_equiv_boe",
            "SUM",
        ),
        # KCl
        MappingTemplate(
            "kcl.feed_mass_tm",
            "Desempeño KCl - Alimentación materia prima (por corriente)",
            "masa_alimentada_tm",
            "SUM",
        ),
        MappingTemplate(
            "kcl.feed_k2o_pct",
            "Desempeño KCl - Alimentación materia prima (por corriente)",
            "k2o_pct",
            "AVG",
        ),
        MappingTemplate(
            "kcl.product_mass_tm",
            "Desempeño KCl - Producción (por tipo)",
            "masa_producida_tm",
            "SUM",
        ),
        MappingTemplate(
            "kcl.product_grade_pct",
            "Desempeño KCl - Producción (por tipo)",
            "pureza_pct",
            "AVG",
        ),
        MappingTemplate(
            "kcl.tails_mass_tm",
            "Desempeño KCl - Colas y pérdidas",
            "masa_colas_tm",
            "SUM",
        ),
        MappingTemplate(
            "kcl.tails_k_grade_pct",
            "Desempeño KCl - Colas y pérdidas",
            "ley_k_colas_pct",
            "AVG",
        ),
        MappingTemplate(
            "kcl.water_fresh_m3",
            "Desempeño KCl - Agua y energía",
            "agua_fresca_m3",
            "SUM",
        ),
        MappingTemplate(
            "kcl.water_recirculated_m3",
            "Desempeño KCl - Agua y energía",
            "agua_recirculada_m3",
            "SUM",
        ),
        MappingTemplate(
            "kcl.energy_equivalent_boe",
            "Desempeño KCl - Agua y energía",
            "energia_equiv_boe",
            "SUM",
        ),
        # Li2CO3
        MappingTemplate(
            "lic.feed_mass_tm",
            "Desempeño Li2CO3 - Materia prima (Sulfato de Litio)",
            "masa_sulfato_li_tm",
            "SUM",
        ),
        MappingTemplate(
            "lic.feed_li_grade_pct",
            "Desempeño Li2CO3 - Materia prima (Sulfato de Litio)",
            "ley_li_alimentacion_pct",
            "AVG",
        ),
        MappingTemplate(
            "lic.product_mass_tm",
            "Desempeño Li2CO3 - Producción",
            "masa_li2co3_tm",
            "SUM",
        ),
        MappingTemplate(
            "lic.product_purity_pct",
            "Desempeño Li2CO3 - Producción",
            "pureza_producto_pct",
            "AVG",
        ),
        MappingTemplate(
            "lic.residue_mass_tm",
            "Desempeño Li2CO3 - Residuos y pérdidas",
            "masa_residuos_tm",
            "SUM",
        ),
        MappingTemplate(
            "lic.residue_li_grade_pct",
            "Desempeño Li2CO3 - Residuos y pérdidas",
            "ley_li_residuos_pct",
            "AVG",
        ),
        MappingTemplate(
            "lic.energy_equivalent_boe",
            "Desempeño Li2CO3 - Agua y energía",
            "energia_equiv_boe",
            "SUM",
        ),
    ]
