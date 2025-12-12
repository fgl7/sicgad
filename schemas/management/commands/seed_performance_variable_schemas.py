from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from plants.models import Plant
from schemas.models import ColumnDef, DatasetType


@dataclass(frozen=True)
class ColumnTemplate:
    name: str
    label: str
    data_type: str = "FLOAT"
    required: bool = False
    unit: str = ""
    axis_role: str = "NONE"
    default_agg: str = "SUM"
    is_primary_kpi: bool = False


@dataclass(frozen=True)
class DatasetTemplate:
    plant_code: str
    name: str
    validation_frequency: str
    columns: list[ColumnTemplate]


def _upsert_dataset(template: DatasetTemplate, *, dry_run: bool) -> tuple[DatasetType | None, bool]:
    try:
        plant = Plant.objects.get(code=template.plant_code)
    except Plant.DoesNotExist:
        return None, False

    existing = (
        DatasetType.objects.filter(plant=plant, name=template.name)
        .order_by("-version")
        .first()
    )
    if existing:
        return existing, False

    if dry_run:
        return None, True

    created = DatasetType.objects.create(
        plant=plant,
        name=template.name,
        version=1,
        validation_frequency=template.validation_frequency,
        is_certification=False,
        is_active=True,
        status=DatasetType.STATUS_APPROVED,
    )
    return created, True


def _upsert_columns(dataset: DatasetType, templates: list[ColumnTemplate], *, dry_run: bool) -> int:
    existing_by_name = {c.name: c for c in dataset.columns.all()}
    created_count = 0
    for idx, col in enumerate(templates, start=1):
        if col.name in existing_by_name:
            continue
        if dry_run:
            created_count += 1
            continue
        ColumnDef.objects.create(
            dataset_type=dataset,
            name=col.name,
            label=col.label,
            data_type=col.data_type,
            required=col.required,
            unit=col.unit,
            axis_role=col.axis_role,
            default_agg=col.default_agg,
            is_primary_kpi=col.is_primary_kpi,
            display_order=idx * 10,
            is_active=True,
        )
        created_count += 1
    return created_count


class Command(BaseCommand):
    help = "Crea DatasetType/ColumnDef mínimos para capturar variables de desempeño (PCS/PIKCL/PICL)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué crearía, sin escribir en la BD.",
        )
        parser.add_argument(
            "--plants",
            nargs="*",
            default=["PCS", "PIKCL", "PICL"],
            help="Códigos de planta a incluir (default: PCS PIKCL PICL).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        selected_plants: set[str] = set(options["plants"] or [])

        templates = _build_templates()
        templates = [t for t in templates if t.plant_code in selected_plants]

        if not templates:
            self.stdout.write(self.style.WARNING("No hay plantillas para ejecutar."))
            return

        missing_plants = sorted({t.plant_code for t in templates} - set(Plant.objects.values_list("code", flat=True)))
        if missing_plants:
            self.stdout.write(
                self.style.WARNING(
                    "Plantas no encontradas (se omiten): " + ", ".join(missing_plants)
                )
            )

        created_datasets = 0
        created_columns = 0

        for tmpl in templates:
            dataset, created = _upsert_dataset(tmpl, dry_run=dry_run)
            if created:
                created_datasets += 1
                self.stdout.write(f"[dataset] {'CREAR' if dry_run else 'CREADO'}: {tmpl.plant_code} / {tmpl.name}")
            else:
                if dataset:
                    self.stdout.write(f"[dataset] OK: {tmpl.plant_code} / {tmpl.name} (v{dataset.version})")
                else:
                    self.stdout.write(f"[dataset] OMITIDO (planta no existe): {tmpl.plant_code} / {tmpl.name}")
                    continue

            if not dataset and dry_run:
                # dry-run: dataset "creado" pero no existe aún para agregar columnas
                created_columns += len(tmpl.columns)
                continue

            assert dataset is not None
            added = _upsert_columns(dataset, tmpl.columns, dry_run=dry_run)
            created_columns += added
            if added:
                self.stdout.write(f"  [columns] +{added}")

        summary = f"Resumen: datasets +{created_datasets}, columnas +{created_columns}"
        if dry_run:
            summary += " (dry-run)"
        self.stdout.write(self.style.SUCCESS(summary))


def _build_templates() -> list[DatasetTemplate]:
    """
    Plantillas mínimas para capturar variables requeridas por la metodología de desempeño.
    La idea es que el Admin pueda luego ajustar/expandir columnas sin tocar el backend.
    """

    return [
        # PCS (Concentración de Sales)
        DatasetTemplate(
            plant_code="PCS",
            name="Desempeño PCS - Extracción de salmuera (por pozo)",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="pozo_codigo",
                    label="Pozo (código)",
                    data_type="STRING",
                    required=True,
                    axis_role="FILTER",
                    default_agg="NONE",
                ),
                ColumnTemplate(
                    name="volumen_salm_m3",
                    label="Volumen de salmuera extraída (m3)",
                    required=True,
                    unit="m3",
                    axis_role="Y",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
                ColumnTemplate(
                    name="densidad_g_cm3",
                    label="Densidad de salmuera (g/cm3)",
                    unit="g/cm3",
                    default_agg="AVG",
                ),
                ColumnTemplate(
                    name="tds_pct",
                    label="TDS / fracción másica de sólidos (%)",
                    unit="%",
                    default_agg="AVG",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PCS",
            name="Desempeño PCS - Operación de piscinas (evaporación/cristales)",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="piscina_codigo",
                    label="Piscina (código)",
                    data_type="STRING",
                    required=True,
                    axis_role="FILTER",
                    default_agg="NONE",
                ),
                ColumnTemplate(
                    name="area_efectiva_m2",
                    label="Área efectiva operativa (m2)",
                    unit="m2",
                    default_agg="AVG",
                ),
                ColumnTemplate(
                    name="altura_cristal_m",
                    label="Altura de cristal (m)",
                    unit="m",
                    default_agg="AVG",
                ),
                ColumnTemplate(
                    name="volumen_evaporado_real_m3",
                    label="Volumen de agua evaporada real (m3)",
                    unit="m3",
                    default_agg="SUM",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PCS",
            name="Desempeño PCS - Producción de sales (por tipo)",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="producto_tipo",
                    label="Tipo de sal / producto",
                    data_type="STRING",
                    required=True,
                    axis_role="FILTER",
                    default_agg="NONE",
                ),
                ColumnTemplate(
                    name="masa_producida_tm",
                    label="Masa producida (TM)",
                    required=True,
                    unit="TM",
                    axis_role="Y",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PCS",
            name="Desempeño PCS - Composición iónica mensual",
            validation_frequency=DatasetType.MONTHLY,
            columns=[
                ColumnTemplate(name="na", label="Na+ (concentración)", unit="g/L", default_agg="NONE"),
                ColumnTemplate(name="k", label="K+ (concentración)", unit="g/L", default_agg="NONE"),
                ColumnTemplate(name="li", label="Li+ (concentración)", unit="g/L", default_agg="NONE"),
                ColumnTemplate(name="mg", label="Mg2+ (concentración)", unit="g/L", default_agg="NONE"),
                ColumnTemplate(name="ca", label="Ca2+ (concentración)", unit="g/L", default_agg="NONE"),
                ColumnTemplate(name="cl", label="Cl- (concentración)", unit="g/L", default_agg="NONE"),
                ColumnTemplate(name="so4", label="SO4 2- (concentración)", unit="g/L", default_agg="NONE"),
            ],
        ),
        DatasetTemplate(
            plant_code="PCS",
            name="Desempeño PCS - Energía equivalente",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="energia_equiv_boe",
                    label="Energía equivalente consumida (boe)",
                    unit="boe",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PCS",
            name="Desempeño PCS - Evaporación teórica (modelo externo)",
            validation_frequency=DatasetType.MONTHLY,
            columns=[
                ColumnTemplate(
                    name="volumen_evaporado_teorico_m3",
                    label="Volumen de agua evaporada teórica (m3)",
                    unit="m3",
                    default_agg="NONE",
                ),
            ],
        ),
        # PIKCL (Industrial KCl)
        DatasetTemplate(
            plant_code="PIKCL",
            name="Desempeño KCl - Alimentación materia prima (por corriente)",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="corriente",
                    label="Corriente alimentada (Silvinita/Mixtas/Halita/etc.)",
                    data_type="STRING",
                    required=True,
                    axis_role="FILTER",
                    default_agg="NONE",
                ),
                ColumnTemplate(
                    name="masa_alimentada_tm",
                    label="Masa alimentada (TM)",
                    required=True,
                    unit="TM",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
                ColumnTemplate(
                    name="humedad_pct",
                    label="Humedad (%)",
                    unit="%",
                    default_agg="AVG",
                ),
                ColumnTemplate(
                    name="k2o_pct",
                    label="% K2O",
                    unit="%",
                    default_agg="AVG",
                ),
                ColumnTemplate(
                    name="insolubles_pct",
                    label="% insolubles",
                    unit="%",
                    default_agg="AVG",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PIKCL",
            name="Desempeño KCl - Producción (por tipo)",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="tipo_kcl",
                    label="Tipo de KCl (Estándar/Tipo 1/Tipo 2/etc.)",
                    data_type="STRING",
                    required=True,
                    axis_role="FILTER",
                    default_agg="NONE",
                ),
                ColumnTemplate(
                    name="masa_producida_tm",
                    label="Producción (TM)",
                    required=True,
                    unit="TM",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
                ColumnTemplate(
                    name="pureza_pct",
                    label="Pureza / ley del producto (%)",
                    unit="%",
                    default_agg="AVG",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PIKCL",
            name="Desempeño KCl - Reactivos consumidos",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="reactivo",
                    label="Reactivo (colector/floculante/espumante/ácido/etc.)",
                    data_type="STRING",
                    required=True,
                    axis_role="FILTER",
                    default_agg="NONE",
                ),
                ColumnTemplate(
                    name="masa_consumida_kg",
                    label="Masa consumida (kg)",
                    unit="kg",
                    default_agg="SUM",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PIKCL",
            name="Desempeño KCl - Agua y energía",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="agua_fresca_m3",
                    label="Agua fresca (m3)",
                    unit="m3",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
                ColumnTemplate(
                    name="agua_recirculada_m3",
                    label="Agua recirculada (m3)",
                    unit="m3",
                    default_agg="SUM",
                ),
                ColumnTemplate(
                    name="energia_equiv_boe",
                    label="Energía equivalente consumida (boe)",
                    unit="boe",
                    default_agg="SUM",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PIKCL",
            name="Desempeño KCl - Colas y pérdidas",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="masa_colas_tm",
                    label="Masa de colas (TM)",
                    unit="TM",
                    default_agg="SUM",
                ),
                ColumnTemplate(
                    name="ley_k_colas_pct",
                    label="Ley de K en colas (%)",
                    unit="%",
                    default_agg="AVG",
                ),
                ColumnTemplate(
                    name="eventos",
                    label="Eventos (derrames/fugas/paros/fallas) - detalle",
                    data_type="STRING",
                    default_agg="NONE",
                ),
            ],
        ),
        # PICL (Industrial Li2CO3)
        DatasetTemplate(
            plant_code="PICL",
            name="Desempeño Li2CO3 - Materia prima (Sulfato de Litio)",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="masa_sulfato_li_tm",
                    label="Sulfato de Litio procesado (TM)",
                    required=True,
                    unit="TM",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
                ColumnTemplate(
                    name="ley_li_alimentacion_pct",
                    label="Concentración/Pureza de Li en alimentación (%)",
                    unit="%",
                    default_agg="AVG",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PICL",
            name="Desempeño Li2CO3 - Producción",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="masa_li2co3_tm",
                    label="Li2CO3 producido (TM)",
                    required=True,
                    unit="TM",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
                ColumnTemplate(
                    name="pureza_producto_pct",
                    label="Pureza del producto final (%)",
                    unit="%",
                    default_agg="AVG",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PICL",
            name="Desempeño Li2CO3 - Reactivos consumidos",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="reactivo",
                    label="Reactivo (carbonato/cal/precipitante/adsorbente/etc.)",
                    data_type="STRING",
                    required=True,
                    axis_role="FILTER",
                    default_agg="NONE",
                ),
                ColumnTemplate(
                    name="masa_consumida_kg",
                    label="Masa consumida (kg)",
                    unit="kg",
                    default_agg="SUM",
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PICL",
            name="Desempeño Li2CO3 - Agua y energía",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="agua_fresca_m3",
                    label="Agua fresca (m3)",
                    unit="m3",
                    default_agg="SUM",
                ),
                ColumnTemplate(
                    name="agua_recirculada_m3",
                    label="Agua recirculada (m3)",
                    unit="m3",
                    default_agg="SUM",
                ),
                ColumnTemplate(
                    name="energia_equiv_boe",
                    label="Energía equivalente consumida (boe)",
                    unit="boe",
                    default_agg="SUM",
                    is_primary_kpi=True,
                ),
            ],
        ),
        DatasetTemplate(
            plant_code="PICL",
            name="Desempeño Li2CO3 - Residuos y pérdidas",
            validation_frequency=DatasetType.DAILY,
            columns=[
                ColumnTemplate(
                    name="masa_residuos_tm",
                    label="Masa de lodos/barros (TM)",
                    unit="TM",
                    default_agg="SUM",
                ),
                ColumnTemplate(
                    name="ley_li_residuos_pct",
                    label="Contenido de Li en residuos (%)",
                    unit="%",
                    default_agg="AVG",
                ),
                ColumnTemplate(
                    name="eventos",
                    label="Eventos/Fallas críticas - detalle",
                    data_type="STRING",
                    default_agg="NONE",
                ),
            ],
        ),
    ]

