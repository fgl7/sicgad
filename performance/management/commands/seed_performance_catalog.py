from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from performance.models import PerformanceIndicator, PerformanceVariable
from structure.models import Entity


@dataclass(frozen=True)
class VariableTemplate:
    entity_code: str
    key: str
    label: str
    unit: str = ""
    value_type: str = "NUMBER"
    description: str = ""


@dataclass(frozen=True)
class IndicatorTemplate:
    entity_code: str
    key: str
    label: str
    unit: str = ""
    description: str = ""
    formula_text: str = ""
    variable_keys: list[str] = None  # type: ignore[assignment]


class Command(BaseCommand):
    help = "Crea la plantilla de variables metodológicas y el catálogo mínimo de indicadores (Tarea 17)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe en la BD.")

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]

        vars_created = 0
        inds_created = 0

        for v in _variables():
            entity = Entity.objects.filter(code=v.entity_code, is_active=True).first()
            if not entity:
                self.stdout.write(self.style.WARNING(f"[var] OMITIDA (entidad no existe): {v.entity_code} / {v.key}"))
                continue

            if PerformanceVariable.objects.filter(key=v.key).exists():
                continue

            if dry_run:
                vars_created += 1
                continue

            PerformanceVariable.objects.create(
                key=v.key,
                entity=entity,
                label=v.label,
                unit=v.unit,
                value_type=v.value_type,
                description=v.description,
                is_active=True,
            )
            vars_created += 1

        # indicadores mínimos (placeholder) para que el Admin tenga catálogo.
        variables_by_key = {pv.key: pv for pv in PerformanceVariable.objects.all()}
        for ind in _indicators():
            entity = Entity.objects.filter(code=ind.entity_code, is_active=True).first()
            if not entity:
                self.stdout.write(self.style.WARNING(f"[ind] OMITIDO (entidad no existe): {ind.entity_code} / {ind.key}"))
                continue

            if PerformanceIndicator.objects.filter(key=ind.key).exists():
                continue

            if dry_run:
                inds_created += 1
                continue

            indicator = PerformanceIndicator.objects.create(
                key=ind.key,
                entity=entity,
                label=ind.label,
                unit=ind.unit,
                description=ind.description,
                formula_text=ind.formula_text,
                is_active=True,
            )
            for k in ind.variable_keys or []:
                pv = variables_by_key.get(k)
                if pv:
                    indicator.variables.add(pv)
            inds_created += 1

        summary = f"Resumen: variables +{vars_created}, indicadores +{inds_created}"
        if dry_run:
            summary += " (dry-run)"
        self.stdout.write(self.style.SUCCESS(summary))


def _variables() -> list[VariableTemplate]:
    # Variables seleccionadas (mínimas) para arrancar el catálogo y permitir mapeo.
    # Se puede ampliar sin tocar backend: seed crea solo las faltantes.
    return [
        # PCS
        VariableTemplate("PCS", "pcs.f1.msales_tm", "Msales(m) - Masa total de sales cosechadas en el mes", "TM"),
        VariableTemplate(
            "PCS",
            "pcs.f1.msalmuera_tm",
            "Msalmuera(m-delta_t) - Masa total de salmuera del mes de extracción (ajustada a base seca)",
            "TM",
        ),
        VariableTemplate(
            "PCS",
            "pcs.f1.xsolids_frac",
            "Xsolids(m-delta_t) - Fracción másica de sólidos en salmuera (p/p)",
            "p/p",
        ),
        VariableTemplate("PCS", "pcs.brine_volume_m3", "Volumen de salmuera extraída", "m3"),
        VariableTemplate("PCS", "pcs.brine_density_g_cm3", "Densidad de salmuera", "g/cm3"),
        VariableTemplate("PCS", "pcs.tds_pct", "TDS / fracción másica de sólidos", "%"),
        VariableTemplate("PCS", "pcs.salts_mass_tm", "Masa de sales cristalizadas/producidas", "TM"),
        VariableTemplate("PCS", "pcs.pool_area_effective_m2", "Área efectiva operativa", "m2"),
        VariableTemplate("PCS", "pcs.crystal_height_m", "Altura de cristal", "m"),
        VariableTemplate("PCS", "pcs.evaporated_volume_real_m3", "Volumen evaporado real", "m3"),
        VariableTemplate("PCS", "pcs.evaporated_volume_theoretical_m3", "Volumen evaporado teórico", "m3"),
        VariableTemplate("PCS", "pcs.energy_equivalent_boe", "Energía equivalente consumida", "boe"),
        # KCl
        VariableTemplate("PIKCL", "kcl.feed_mass_tm", "Masa alimentada (base seca ideal)", "TM"),
        VariableTemplate("PIKCL", "kcl.feed_k2o_pct", "% K2O en alimentación", "%"),
        VariableTemplate("PIKCL", "kcl.product_mass_tm", "Producción total de KCl", "TM"),
        VariableTemplate("PIKCL", "kcl.product_grade_pct", "Ley/pureza del producto", "%"),
        VariableTemplate("PIKCL", "kcl.tails_mass_tm", "Masa de colas", "TM"),
        VariableTemplate("PIKCL", "kcl.tails_k_grade_pct", "Ley de K en colas", "%"),
        VariableTemplate("PIKCL", "kcl.water_fresh_m3", "Agua fresca utilizada", "m3"),
        VariableTemplate("PIKCL", "kcl.water_recirculated_m3", "Agua recirculada", "m3"),
        VariableTemplate("PIKCL", "kcl.energy_equivalent_boe", "Energía equivalente consumida", "boe"),
        # Li2CO3
        VariableTemplate("PICL", "lic.feed_mass_tm", "Sulfato de Litio procesado (base seca ideal)", "TM"),
        VariableTemplate("PICL", "lic.feed_li_grade_pct", "Ley/concentración de Li en alimentación", "%"),
        VariableTemplate("PICL", "lic.product_mass_tm", "Li2CO3 producido", "TM"),
        VariableTemplate("PICL", "lic.product_purity_pct", "Pureza del producto final", "%"),
        VariableTemplate("PICL", "lic.residue_mass_tm", "Masa de lodos/barros", "TM"),
        VariableTemplate("PICL", "lic.residue_li_grade_pct", "Contenido de Li en residuos", "%"),
        VariableTemplate("PICL", "lic.energy_equivalent_boe", "Energía equivalente consumida", "boe"),
    ]


def _indicators() -> list[IndicatorTemplate]:
    # Indicadores mínimos (placeholder, para catálogo). La implementación numérica llega en Tarea 18.
    return [
        IndicatorTemplate(
            "PCS",
            "pcs.formula1_yield_pct",
            "Fórmula 1 - Rendimiento de Producción Mensual",
            "%",
            formula_text="R(m) = Msales(m) / (Msalmuera(m-delta_t) * Xsolids(m-delta_t)) * 100",
            variable_keys=["pcs.f1.msales_tm", "pcs.f1.msalmuera_tm", "pcs.f1.xsolids_frac"],
        ),
        IndicatorTemplate(
            "PCS",
            "pcs.energy_specific_boe_per_tm",
            "Consumo específico de energía",
            "boe/TM",
            formula_text="E_spec = E_boe / sum(productos_TM) (mensual)",
            variable_keys=["pcs.energy_equivalent_boe", "pcs.salts_mass_tm"],
        ),
        IndicatorTemplate(
            "PIKCL",
            "kcl.yield_pct",
            "Rendimiento de producción de KCl",
            "%",
            formula_text="R = (KCl_producido_TM / MP_procesada_TM) * 100 (mensual)",
            variable_keys=["kcl.product_mass_tm", "kcl.feed_mass_tm"],
        ),
        IndicatorTemplate(
            "PICL",
            "lic.yield_pct",
            "Rendimiento de producción de Li2CO3",
            "%",
            formula_text="R = (Li2CO3_producido_TM / MP_procesada_TM) * 100 (mensual)",
            variable_keys=["lic.product_mass_tm", "lic.feed_mass_tm"],
        ),
    ]


