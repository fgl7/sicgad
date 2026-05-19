from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import AccountProfile, Institution, Membership
from audit.models import AuditLog
from ingest.models import DatasetInstance, PublishedDataPoint
from projects.models import Project, ProjectReportConfig
from schemas.models import ColumnDef, DatasetType
from structure.models import Category, Entity, Sector, Subsector
from validation.models import ValidationAction


DEMO_PASSWORD_ENV = "SICGAD_DEMO_PASSWORD"
DEMO_INSTITUTION_CODE = "ABEN"
DEMO_SECTOR_NAME = "Energía Nuclear y Aplicaciones Tecnológicas"

ENTITY_TREE = {
    "Medicina Nuclear y Radioterapia": {
        "category": "Centros de Medicina Nuclear y Radioterapia",
        "entities": [
            ("CMNYR_EA", "Centro de Medicina Nuclear y Radioterapia El Alto"),
            ("CMNYR_SCZ", "Centro de Medicina Nuclear y Radioterapia Santa Cruz"),
            ("CMNYR_LP", "Centro de Medicina Nuclear y Radioterapia La Paz"),
        ],
    },
    "Investigación y Desarrollo Nuclear": {
        "category": "Investigación, Reactores y Laboratorios",
        "entities": [
            ("CIDTN", "Centro de Investigación y Desarrollo en Tecnología Nuclear"),
            ("RNI", "Reactor Nuclear de Investigación"),
            ("RADFARM", "Laboratorio de Radiofarmacia"),
            ("DOSIM", "Laboratorio de Dosimetría"),
        ],
    },
    "Aplicaciones Nucleares e Irradiación": {
        "category": "Servicios de Irradiación y Aplicaciones",
        "entities": [
            ("PIM", "Planta de Irradiación Multipropósito"),
            ("IRRAD_IND", "Servicios de Irradiación Industrial"),
            ("AGR_NUC", "Aplicaciones Nucleares en Agricultura"),
            ("RRNN_NUC", "Aplicaciones Nucleares en Recursos Naturales"),
        ],
    },
    "Infraestructura y Equipamiento Tecnológico": {
        "category": "Activos e Infraestructura Tecnológica",
        "entities": [
            ("MANT_CRIT", "Mantenimiento de Equipos Críticos"),
            ("ACTIVOS_TEC", "Gestión de Activos Tecnológicos"),
            ("INFRA_ESP", "Infraestructura Especializada"),
        ],
    },
    "Gestión Institucional y Proyectos Estratégicos": {
        "category": "Gestión Institucional y Proyectos",
        "entities": [
            ("DGE", "Dirección General Ejecutiva"),
            ("PLAN_INST", "Planificación Institucional"),
            ("PROY_CONV", "Proyectos y Convenios"),
            ("COOP_INT", "Cooperación Técnica Internacional"),
        ],
    },
    "Seguridad, Calidad y Cumplimiento": {
        "category": "Seguridad, Calidad y Cumplimiento",
        "entities": [
            ("SEG_RAD_OP", "Seguridad Radiológica Operativa"),
            ("CALIDAD", "Gestión de Calidad"),
            ("AUD_TRACE", "Auditoría y Trazabilidad"),
            ("CUMPL_NORM", "Cumplimiento Normativo"),
        ],
    },
}

ABEN_ENTITY_CODES = tuple(code for node in ENTITY_TREE.values() for code, _ in node["entities"])
DEMO_USERNAMES = (
    "admin_aben",
    "cargador_cmnyr",
    "cargador_cidtn",
    "cargador_mantenimiento",
    "cargador_proyectos",
    "validador_salud_nuclear",
    "validador_tecnico_aben",
    "validador_planificacion",
    "director_aben",
    "seguimiento_mhe",
    "auditoria_aben",
)


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    label: str
    data_type: str = "FLOAT"
    unit: str = ""
    axis_role: str = "NONE"
    default_agg: str = "SUM"
    is_primary_kpi: bool = False
    required: bool = True


@dataclass(frozen=True)
class DatasetSpec:
    entity_code: str
    name: str
    columns: tuple[ColumnSpec, ...]


DATASET_SPECS = (
    DatasetSpec(
        "CMNYR_EA",
        "Atenciones en Medicina Nuclear",
        (
            ColumnSpec("fecha", "Fecha", "DATE", axis_role="X", default_agg="NONE"),
            ColumnSpec("pacientes_atendidos", "Pacientes atendidos", "INTEGER", "pacientes", is_primary_kpi=True),
            ColumnSpec("estudios_pet_ct", "Estudios PET-CT", "INTEGER", "estudios", is_primary_kpi=True),
            ColumnSpec("sesiones_radioterapia", "Sesiones de radioterapia", "INTEGER", "sesiones", is_primary_kpi=True),
            ColumnSpec("tratamientos_braquiterapia", "Tratamientos de braquiterapia", "INTEGER", "tratamientos"),
            ColumnSpec("tiempo_promedio_espera_dias", "Tiempo promedio de espera", "FLOAT", "dias", "NONE", "AVG", True),
            ColumnSpec("disponibilidad_equipo_pct", "Disponibilidad de equipo", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("observaciones", "Observaciones", "STRING", required=False, default_agg="NONE"),
        ),
    ),
    DatasetSpec(
        "RADFARM",
        "Producción y Distribución de Radiofármacos",
        (
            ColumnSpec("fecha", "Fecha", "DATE", axis_role="X", default_agg="NONE"),
            ColumnSpec("lotes_producidos", "Lotes producidos", "INTEGER", "lotes"),
            ColumnSpec("dosis_distribuidas", "Dosis distribuidas", "INTEGER", "dosis", is_primary_kpi=True),
            ColumnSpec("dosis_descartadas", "Dosis descartadas", "INTEGER", "dosis"),
            ColumnSpec("cumplimiento_calidad_pct", "Cumplimiento de calidad", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("entregas_a_tiempo_pct", "Entregas a tiempo", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("incidentes_calidad", "Incidentes de calidad", "INTEGER", "incidentes", is_primary_kpi=True),
            ColumnSpec("observaciones", "Observaciones", "STRING", required=False, default_agg="NONE"),
        ),
    ),
    DatasetSpec(
        "PIM",
        "Servicios de Irradiación Multipropósito",
        (
            ColumnSpec("fecha", "Fecha", "DATE", axis_role="X", default_agg="NONE"),
            ColumnSpec("lotes_irradiados", "Lotes irradiados", "INTEGER", "lotes", is_primary_kpi=True),
            ColumnSpec("toneladas_tratadas", "Toneladas tratadas", "FLOAT", "t", is_primary_kpi=True),
            ColumnSpec("servicios_agroindustriales", "Servicios agroindustriales", "INTEGER", "servicios"),
            ColumnSpec("servicios_medicos", "Servicios médicos", "INTEGER", "servicios"),
            ColumnSpec("servicios_investigacion", "Servicios de investigación", "INTEGER", "servicios"),
            ColumnSpec("disponibilidad_planta_pct", "Disponibilidad de planta", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("ingresos_estimados_bs", "Ingresos estimados ficticios", "FLOAT", "Bs", is_primary_kpi=True),
            ColumnSpec("observaciones", "Observaciones", "STRING", required=False, default_agg="NONE"),
        ),
    ),
    DatasetSpec(
        "MANT_CRIT",
        "Mantenimiento de Equipos Críticos",
        (
            ColumnSpec("fecha", "Fecha", "DATE", axis_role="X", default_agg="NONE"),
            ColumnSpec("equipos_criticos_operativos", "Equipos críticos operativos", "INTEGER", "equipos"),
            ColumnSpec("equipos_en_mantenimiento", "Equipos en mantenimiento", "INTEGER", "equipos"),
            ColumnSpec("mantenimientos_preventivos", "Mantenimientos preventivos", "INTEGER", "mantenimientos", is_primary_kpi=True),
            ColumnSpec("mantenimientos_correctivos", "Mantenimientos correctivos", "INTEGER", "mantenimientos", is_primary_kpi=True),
            ColumnSpec("tiempo_indisponibilidad_horas", "Tiempo de indisponibilidad", "FLOAT", "horas", "NONE", "SUM", True),
            ColumnSpec("cumplimiento_plan_mantenimiento_pct", "Cumplimiento del plan de mantenimiento", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("alertas_criticas", "Alertas críticas", "INTEGER", "alertas", is_primary_kpi=True),
            ColumnSpec("observaciones", "Observaciones", "STRING", required=False, default_agg="NONE"),
        ),
    ),
    DatasetSpec(
        "PROY_CONV",
        "Proyectos y Convenios Estratégicos",
        (
            ColumnSpec("fecha", "Fecha", "DATE", axis_role="X", default_agg="NONE"),
            ColumnSpec("proyectos_activos", "Proyectos activos", "INTEGER", "proyectos", is_primary_kpi=True),
            ColumnSpec("proyectos_en_retraso", "Proyectos en retraso", "INTEGER", "proyectos", is_primary_kpi=True),
            ColumnSpec("convenios_vigentes", "Convenios vigentes", "INTEGER", "convenios"),
            ColumnSpec("convenios_en_gestion", "Convenios en gestión", "INTEGER", "convenios"),
            ColumnSpec("avance_fisico_promedio_pct", "Avance físico promedio", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("avance_financiero_promedio_pct", "Avance financiero promedio", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("tramites_pendientes", "Trámites pendientes", "INTEGER", "trámites", is_primary_kpi=True),
            ColumnSpec("observaciones", "Observaciones", "STRING", required=False, default_agg="NONE"),
        ),
    ),
    DatasetSpec(
        "SEG_RAD_OP",
        "Cumplimiento, Seguridad y Calidad",
        (
            ColumnSpec("fecha", "Fecha", "DATE", axis_role="X", default_agg="NONE"),
            ColumnSpec("inspecciones_internas", "Inspecciones internas", "INTEGER", "inspecciones"),
            ColumnSpec("hallazgos_abiertos", "Hallazgos abiertos", "INTEGER", "hallazgos", is_primary_kpi=True),
            ColumnSpec("hallazgos_cerrados", "Hallazgos cerrados", "INTEGER", "hallazgos", is_primary_kpi=True),
            ColumnSpec("capacitaciones_seguridad", "Capacitaciones de seguridad", "INTEGER", "capacitaciones"),
            ColumnSpec("personal_capacitado", "Personal capacitado", "INTEGER", "personas", is_primary_kpi=True),
            ColumnSpec("incidentes_reportados", "Incidentes reportados", "INTEGER", "incidentes", is_primary_kpi=True),
            ColumnSpec("cumplimiento_normativo_pct", "Cumplimiento normativo", "FLOAT", "%", "NONE", "AVG", True),
            ColumnSpec("observaciones", "Observaciones", "STRING", required=False, default_agg="NONE"),
        ),
    ),
)

PROJECTS = (
    ("ABEN-DIGITAL", "Modernización de Gestión Digital ABEN", "Implementación de SICGAD para control institucional", 35, 20, "Implementación"),
    ("ABEN-CMNYR", "Programa de Fortalecimiento de Centros de Medicina Nuclear", "Seguimiento de disponibilidad, atención y calidad de servicio", 60, 50, "Ejecución"),
    ("ABEN-SMR", "Evaluación Estratégica de SMR para Bolivia", "Estudio preliminar de prefactibilidad para generación nucleoeléctrica modular", 10, 5, "Prefactibilidad"),
    ("ABEN-ACTIVOS", "Plan de Gestión de Activos Críticos", "Control de mantenimiento preventivo y correctivo de equipos especializados", 45, 30, "Ejecución"),
    ("ABEN-CALIDAD", "Programa de Seguridad, Calidad y Cumplimiento", "Monitoreo de inspecciones, hallazgos, capacitaciones y cumplimiento", 50, 40, "Ejecución"),
)


def _last_day(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _demo_periods() -> list[date]:
    periods = []
    year, month = 2025, 5
    for _ in range(12):
        periods.append(_last_day(year, month))
        month += 1
        if month > 12:
            year += 1
            month = 1
    return periods


def _metric_rows() -> dict[str, list[dict[str, object]]]:
    periods = _demo_periods()
    notes = [
        "Dato ficticio para demo ejecutiva ABEN.",
        "Seguimiento mensual demostrativo.",
        "Información validada en entorno demo.",
        "Registro institucional ficticio.",
    ]
    return {
        "Atenciones en Medicina Nuclear": [
            {
                "fecha": period,
                "pacientes_atendidos": 980 + idx * 22 + (idx % 3) * 18,
                "estudios_pet_ct": 210 + idx * 4 + (idx % 2) * 9,
                "sesiones_radioterapia": 760 + idx * 15 + (idx % 4) * 12,
                "tratamientos_braquiterapia": 32 + idx // 2 + (idx % 3),
                "tiempo_promedio_espera_dias": round(15.2 - idx * 0.55 + (idx % 2) * 0.2, 1),
                "disponibilidad_equipo_pct": round(91.0 + idx * 0.55 + (idx % 3) * 0.2, 1),
                "observaciones": notes[idx % len(notes)],
            }
            for idx, period in enumerate(periods)
        ],
        "Producción y Distribución de Radiofármacos": [
            {
                "fecha": period,
                "lotes_producidos": 42 + idx + (idx % 3),
                "dosis_distribuidas": 1480 + idx * 38 + (idx % 4) * 21,
                "dosis_descartadas": max(9, 18 - idx // 2 + (idx % 2)),
                "cumplimiento_calidad_pct": min(99.7, round(95.4 + idx * 0.33 + (idx % 2) * 0.15, 1)),
                "entregas_a_tiempo_pct": min(97.8, round(86.0 + idx * 0.95 + (idx % 3) * 0.25, 1)),
                "incidentes_calidad": 2 if idx < 3 else 1 if idx < 9 else 0,
                "observaciones": notes[(idx + 1) % len(notes)],
            }
            for idx, period in enumerate(periods)
        ],
        "Servicios de Irradiación Multipropósito": [
            {
                "fecha": period,
                "lotes_irradiados": 58 + idx * 5 + (idx % 4) * 2,
                "toneladas_tratadas": round(34.5 + idx * 2.9 + (idx % 3) * 1.1, 1),
                "servicios_agroindustriales": 24 + idx * 2 + (idx % 2),
                "servicios_medicos": 10 + idx + (idx % 3),
                "servicios_investigacion": 5 + idx // 2,
                "disponibilidad_planta_pct": round(90.5 + idx * 0.45 + (idx % 2) * 0.25, 1),
                "ingresos_estimados_bs": 185000 + idx * 18500 + (idx % 3) * 7200,
                "observaciones": "Ingreso estimado ficticio para fines demostrativos.",
            }
            for idx, period in enumerate(periods)
        ],
        "Mantenimiento de Equipos Críticos": [
            {
                "fecha": period,
                "equipos_criticos_operativos": 31 + min(idx // 3, 3),
                "equipos_en_mantenimiento": max(2, 7 - idx // 2),
                "mantenimientos_preventivos": 18 + idx * 2,
                "mantenimientos_correctivos": max(3, 12 - idx),
                "tiempo_indisponibilidad_horas": round(96 - idx * 5.5 + (idx % 2) * 2.0, 1),
                "cumplimiento_plan_mantenimiento_pct": round(78 + idx * 1.8 + (idx % 3) * 0.4, 1),
                "alertas_criticas": max(1, 9 - idx),
                "observaciones": notes[(idx + 2) % len(notes)],
            }
            for idx, period in enumerate(periods)
        ],
        "Proyectos y Convenios Estratégicos": [
            {
                "fecha": period,
                "proyectos_activos": 5 + (1 if idx >= 6 else 0),
                "proyectos_en_retraso": max(1, 4 - idx // 4),
                "convenios_vigentes": 7 + idx // 4,
                "convenios_en_gestion": max(2, 6 - idx // 3),
                "avance_fisico_promedio_pct": round(22 + idx * 3.1, 1),
                "avance_financiero_promedio_pct": round(15 + idx * 2.8, 1),
                "tramites_pendientes": max(12, 48 - idx * 3 - (4 if idx >= 5 else 0)),
                "observaciones": "Reducción ficticia de trámites asociada a gestión digital.",
            }
            for idx, period in enumerate(periods)
        ],
        "Cumplimiento, Seguridad y Calidad": [
            {
                "fecha": period,
                "inspecciones_internas": 6 + idx // 2,
                "hallazgos_abiertos": max(4, 18 - idx),
                "hallazgos_cerrados": 7 + idx,
                "capacitaciones_seguridad": 2 + idx // 3,
                "personal_capacitado": 38 + idx * 6 + (idx % 3) * 4,
                "incidentes_reportados": 1 if idx in (1, 6, 9) else 0,
                "cumplimiento_normativo_pct": round(92.5 + idx * 0.55 + (idx % 2) * 0.15, 1),
                "observaciones": notes[(idx + 3) % len(notes)],
            }
            for idx, period in enumerate(periods)
        ],
    }


class Command(BaseCommand):
    help = "Crea o regenera una demo institucional ABEN con datos ficticios publicados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina solo objetos demo ABEN conocidos y los vuelve a crear.",
        )
        parser.add_argument(
            "--password",
            default=os.environ.get(DEMO_PASSWORD_ENV, ""),
            help=f"Password for demo users. Can also be provided through {DEMO_PASSWORD_ENV}.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.demo_password = options["password"]
        if not self.demo_password:
            raise CommandError(f"Provide a demo password with --password or {DEMO_PASSWORD_ENV}.")

        if options["reset"]:
            self._reset_demo()

        institution = self._upsert_institution()
        entities = self._upsert_structure()
        users = self._upsert_users(institution, entities)
        loader_memberships, validator_memberships = self._upsert_memberships(institution, users, entities)
        datasets = self._upsert_datasets(entities)
        self._publish_metric_data(datasets, loader_memberships, validator_memberships)
        report_datasets = self._upsert_project_report_datasets(entities["PROY_CONV"])
        self._publish_project_report_data(report_datasets, loader_memberships["PROY_CONV"], validator_memberships["PROY_CONV"])
        projects = self._upsert_projects(users["admin_aben"], entities["PROY_CONV"])
        self._upsert_project_report_configs(projects, datasets["Proyectos y Convenios Estratégicos"], report_datasets)
        self._write_audit_logs(users)

        cache.clear()
        self.stdout.write(self.style.SUCCESS("Demo ABEN creada correctamente."))
        self.stdout.write(f"Usuarios demo: {', '.join(DEMO_USERNAMES)}")
        self.stdout.write(f"Contraseña demo configurada desde --password/{DEMO_PASSWORD_ENV}.")

    def _reset_demo(self):
        demo_entities = Entity.objects.filter(code__in=ABEN_ENTITY_CODES)
        demo_entity_ids = list(demo_entities.values_list("id", flat=True))

        ProjectReportConfig.objects.filter(project__code__startswith="ABEN-").delete()
        ProjectReportConfig.objects.filter(report_dataset__entity_id__in=demo_entity_ids).delete()
        Project.objects.filter(code__startswith="ABEN-").delete()
        DatasetType.objects.filter(entity_id__in=demo_entity_ids).delete()
        AuditLog.objects.filter(username__in=DEMO_USERNAMES).delete()
        AuditLog.objects.filter(details__contains="[ABEN_DEMO]").delete()

        Membership.objects.filter(user__username__in=DEMO_USERNAMES).delete()
        Membership.objects.filter(entity_id__in=demo_entity_ids).delete()

        get_user_model().objects.filter(username__in=DEMO_USERNAMES).delete()
        Institution.objects.filter(code=DEMO_INSTITUTION_CODE).delete()

        demo_categories = Category.objects.filter(subsector__sector__name=DEMO_SECTOR_NAME)
        demo_entities.delete()
        for category in demo_categories:
            if not category.entities.exists() and not category.projects.exists():
                category.delete()
        for subsector in Subsector.objects.filter(sector__name=DEMO_SECTOR_NAME):
            if not subsector.categories.exists():
                subsector.delete()
        Sector.objects.filter(name=DEMO_SECTOR_NAME, subsectors__isnull=True).delete()

    def _upsert_institution(self) -> Institution:
        institution, _ = Institution.objects.update_or_create(
            code=DEMO_INSTITUTION_CODE,
            defaults={
                "name": "Agencia Boliviana de Energía Nuclear",
                "description": "Institución demo ABEN para presentación ejecutiva SICGAD.",
                "is_active": True,
            },
        )
        return institution

    def _upsert_structure(self) -> dict[str, Entity]:
        sector, _ = Sector.objects.update_or_create(
            name=DEMO_SECTOR_NAME,
            defaults={
                "description": "Sector demo para funciones institucionales de ABEN.",
                "is_active": True,
            },
        )
        entities: dict[str, Entity] = {}
        for subsector_name, config in ENTITY_TREE.items():
            subsector, _ = Subsector.objects.update_or_create(
                sector=sector,
                name=subsector_name,
                defaults={"description": "Subsector institucional demo ABEN.", "is_active": True},
            )
            category, _ = Category.objects.update_or_create(
                subsector=subsector,
                name=config["category"],
                defaults={"description": "Categoría operativa demo ABEN.", "is_active": True},
            )
            for code, name in config["entities"]:
                entity, _ = Entity.objects.update_or_create(
                    category=category,
                    name=name,
                    defaults={
                        "code": code,
                        "description": "Entidad institucional demo ABEN con datos ficticios.",
                        "is_active": True,
                    },
                )
                if entity.code != code:
                    entity.code = code
                    entity.save(update_fields=["code"])
                entities[code] = entity
        return entities

    def _upsert_users(self, institution: Institution, entities: dict[str, Entity]):
        del institution, entities
        User = get_user_model()
        specs = {
            "admin_aben": ("Administrador", "ABEN", "Administrador ABEN", True),
            "cargador_cmnyr": ("Cargador", "CMNyR El Alto", "Cargador CMNyR El Alto", False),
            "cargador_cidtn": ("Cargador", "CIDTN", "Cargador CIDTN", False),
            "cargador_mantenimiento": ("Cargador", "Mantenimiento", "Cargador Mantenimiento", False),
            "cargador_proyectos": ("Cargador", "Proyectos", "Cargador Proyectos", False),
            "validador_salud_nuclear": ("Validador", "Salud Nuclear", "Validador Salud Nuclear", False),
            "validador_tecnico_aben": ("Validador", "Técnico ABEN", "Validador Técnico ABEN", False),
            "validador_planificacion": ("Validador", "Planificación", "Validador Planificación", False),
            "director_aben": ("Director", "ABEN", "Director ABEN", False),
            "seguimiento_mhe": ("Seguimiento", "Sectorial", "Seguimiento Sectorial", False),
            "auditoria_aben": ("Auditoría", "ABEN", "Auditoría ABEN", False),
        }
        users = {}
        for username, (first_name, last_name, full_name, is_staff) in specs.items():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@demo.aben.gob.bo",
                    "is_active": True,
                    "is_staff": is_staff,
                },
            )
            user.first_name = first_name
            user.last_name = last_name
            user.email = f"{username}@demo.aben.gob.bo"
            user.is_active = True
            user.is_staff = is_staff
            user.set_password(self.demo_password)
            user.save()
            profile, _ = AccountProfile.objects.get_or_create(user=user)
            profile.must_change_password = False
            if username in {"director_aben", "seguimiento_mhe"}:
                profile.viewer_profile_type = (
                    AccountProfile.VIEWER_AUTHORITY_MHE
                    if username == "director_aben"
                    else AccountProfile.VIEWER_EXTERNAL_MONTHLY
                )
            else:
                profile.viewer_profile_type = AccountProfile.VIEWER_STANDARD
            profile.save()
            if created:
                AuditLog.objects.create(
                    user=user,
                    username=username,
                    action="USER",
                    module="Seed ABEN",
                    object_repr=f"Usuario demo {full_name}",
                    details="[ABEN_DEMO] Usuario demo creado.",
                )
            users[username] = user
        return users

    def _membership(self, *, user, role, institution, entity=None, level=None, monthly=False):
        membership, _ = Membership.objects.update_or_create(
            user=user,
            role=role,
            entity=entity,
            validation_level=level,
            defaults={
                "institution": institution,
                "is_active": True,
                "can_validate_daily": False,
                "can_validate_weekly": False,
                "can_validate_monthly": monthly,
                "can_validate_projections": False,
            },
        )
        return membership

    def _upsert_memberships(self, institution, users, entities):
        loader_memberships = {
            "CMNYR_EA": self._membership(
                user=users["cargador_cmnyr"],
                role="LOADER",
                institution=institution,
                entity=entities["CMNYR_EA"],
            ),
            "CIDTN": self._membership(
                user=users["cargador_cidtn"],
                role="LOADER",
                institution=institution,
                entity=entities["CIDTN"],
            ),
            "MANT_CRIT": self._membership(
                user=users["cargador_mantenimiento"],
                role="LOADER",
                institution=institution,
                entity=entities["MANT_CRIT"],
            ),
            "PROY_CONV": self._membership(
                user=users["cargador_proyectos"],
                role="LOADER",
                institution=institution,
                entity=entities["PROY_CONV"],
            ),
        }
        loader_memberships["RADFARM"] = loader_memberships["CIDTN"]
        loader_memberships["PIM"] = loader_memberships["CIDTN"]
        loader_memberships["SEG_RAD_OP"] = loader_memberships["MANT_CRIT"]

        self._membership(user=users["admin_aben"], role="ADMIN", institution=institution, entity=None)
        for entity in entities.values():
            self._membership(
                user=users["director_aben"],
                role="VIEWER",
                institution=institution,
                entity=entity,
            )
            self._membership(
                user=users["seguimiento_mhe"],
                role="VIEWER",
                institution=institution,
                entity=entity,
            )

        validator_memberships = {}
        salud_codes = ["CMNYR_EA", "CMNYR_SCZ", "CMNYR_LP"]
        tecnico_codes = ["CIDTN", "RNI", "RADFARM", "DOSIM", "PIM", "IRRAD_IND", "AGR_NUC", "RRNN_NUC", "MANT_CRIT", "ACTIVOS_TEC", "INFRA_ESP"]
        gestion_codes = ["DGE", "PLAN_INST", "PROY_CONV", "COOP_INT"]
        seguridad_codes = ["SEG_RAD_OP", "CALIDAD", "AUD_TRACE", "CUMPL_NORM"]

        for code in salud_codes:
            validator_memberships[code] = self._membership(
                user=users["validador_salud_nuclear"],
                role="VALIDATOR",
                institution=institution,
                entity=entities[code],
                level=1,
                monthly=True,
            )
        for code in tecnico_codes:
            validator_memberships[code] = self._membership(
                user=users["validador_tecnico_aben"],
                role="VALIDATOR",
                institution=institution,
                entity=entities[code],
                level=1,
                monthly=True,
            )
        for code in gestion_codes:
            validator_memberships[code] = self._membership(
                user=users["validador_planificacion"],
                role="VALIDATOR",
                institution=institution,
                entity=entities[code],
                level=1,
                monthly=True,
            )
        for code in seguridad_codes:
            validator_memberships[code] = self._membership(
                user=users["validador_tecnico_aben"],
                role="VALIDATOR",
                institution=institution,
                entity=entities[code],
                level=1,
                monthly=True,
            )
            self._membership(
                user=users["auditoria_aben"],
                role="VIEWER",
                institution=institution,
                entity=entities[code],
            )
        return loader_memberships, validator_memberships

    def _upsert_datasets(self, entities):
        datasets = {}
        for spec in DATASET_SPECS:
            entity = entities[spec.entity_code]
            dataset, _ = DatasetType.objects.update_or_create(
                entity=entity,
                name=spec.name,
                version=1,
                defaults={
                    "validation_frequency": DatasetType.MONTHLY,
                    "is_certification": False,
                    "is_active": True,
                    "status": DatasetType.STATUS_APPROVED,
                    "status_comment": "Esquema aprobado para demo institucional ABEN.",
                    "is_one_time": False,
                },
            )
            self._sync_columns(dataset, spec.columns)
            datasets[spec.name] = dataset
        return datasets

    def _sync_columns(self, dataset, columns):
        active_names = []
        for idx, col in enumerate(columns, start=1):
            active_names.append(col.name)
            ColumnDef.objects.update_or_create(
                dataset_type=dataset,
                name=col.name,
                defaults={
                    "label": col.label,
                    "data_type": col.data_type,
                    "required": col.required,
                    "unit": col.unit,
                    "axis_role": col.axis_role,
                    "default_agg": col.default_agg,
                    "is_primary_kpi": col.is_primary_kpi,
                    "display_order": idx * 10,
                    "is_active": True,
                },
            )
        dataset.columns.exclude(name__in=active_names).update(is_active=False)

    def _publish_metric_data(self, datasets, loader_memberships, validator_memberships):
        rows_by_dataset = _metric_rows()
        for name, rows in rows_by_dataset.items():
            dataset = datasets[name]
            loader = loader_memberships[dataset.entity.code]
            validator = validator_memberships[dataset.entity.code]
            self._publish_rows(dataset, rows, loader, validator)

    def _publish_rows(self, dataset, rows, loader, validator):
        columns = {column.name: column for column in dataset.columns.filter(is_active=True)}
        for row in rows:
            period = row["fecha"]
            instance, _ = DatasetInstance.objects.update_or_create(
                dataset_type=dataset,
                entity=dataset.entity,
                period=period,
                defaults={
                    "state": DatasetInstance.STATE_PUBLISHED,
                    "created_by": loader,
                    "row_count": 1,
                    "error_count": 0,
                    "last_error_summary": "",
                    "submitted_at": timezone.now(),
                },
            )
            instance.published_points.all().delete()
            for col_name, value in row.items():
                column = columns[col_name]
                kwargs = {"instance": instance, "column": column, "row_index": 1}
                if column.data_type in {"INTEGER", "FLOAT"}:
                    kwargs["numeric_value"] = float(value)
                elif column.data_type == "DATE":
                    kwargs["date_value"] = value
                    kwargs["text_value"] = value.isoformat()
                elif column.data_type == "BOOLEAN":
                    kwargs["bool_value"] = bool(value)
                else:
                    kwargs["text_value"] = str(value)
                PublishedDataPoint.objects.create(**kwargs)

            instance.validation_actions.all().delete()
            ValidationAction.objects.create(
                dataset_instance=instance,
                validator=validator,
                user=validator.user,
                level=1,
                decision=ValidationAction.DECISION_APPROVE,
                comment="Validación demo ABEN: datos ficticios revisados y publicados.",
            )

    def _upsert_project_report_datasets(self, entity):
        specs = (
            DatasetSpec(
                "PROY_CONV",
                "Curva programada proyectos ABEN",
                (
                    ColumnSpec("mes", "Mes", "STRING", axis_role="X", default_agg="NONE"),
                    ColumnSpec("programado_pct", "Programado", "FLOAT", "%", is_primary_kpi=True),
                ),
            ),
            DatasetSpec(
                "PROY_CONV",
                "Curva ejecutada proyectos ABEN",
                (
                    ColumnSpec("mes", "Mes", "STRING", axis_role="X", default_agg="NONE"),
                    ColumnSpec("ejecutado_pct", "Ejecutado", "FLOAT", "%", is_primary_kpi=True),
                ),
            ),
        )
        datasets = {}
        for spec in specs:
            dataset, _ = DatasetType.objects.update_or_create(
                entity=entity,
                name=spec.name,
                version=1,
                defaults={
                    "validation_frequency": DatasetType.MONTHLY,
                    "is_certification": False,
                    "is_active": True,
                    "status": DatasetType.STATUS_APPROVED,
                    "status_comment": "Esquema de reporte aprobado para demo ABEN.",
                },
            )
            self._sync_columns(dataset, spec.columns)
            datasets[spec.name] = dataset
        return datasets

    def _publish_project_report_data(self, datasets, loader, validator):
        period = date(2026, 4, 30)
        month_labels = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
        program = [8, 16, 24, 32, 40, 48, 57, 66, 75, 84, 92, 100]
        executed = [6, 13, 19, 26, 34, 42, 49, 57, 64, 72, 80, 88]
        for dataset_name, values, value_key in (
            ("Curva programada proyectos ABEN", program, "programado_pct"),
            ("Curva ejecutada proyectos ABEN", executed, "ejecutado_pct"),
        ):
            dataset = datasets[dataset_name]
            columns = {column.name: column for column in dataset.columns.filter(is_active=True)}
            instance, _ = DatasetInstance.objects.update_or_create(
                dataset_type=dataset,
                entity=dataset.entity,
                period=period,
                defaults={
                    "state": DatasetInstance.STATE_PUBLISHED,
                    "created_by": loader,
                    "row_count": 12,
                    "error_count": 0,
                    "last_error_summary": "",
                    "submitted_at": timezone.now(),
                },
            )
            instance.published_points.all().delete()
            for idx, month in enumerate(month_labels, start=1):
                PublishedDataPoint.objects.create(
                    instance=instance,
                    column=columns["mes"],
                    row_index=idx,
                    text_value=month,
                )
                PublishedDataPoint.objects.create(
                    instance=instance,
                    column=columns[value_key],
                    row_index=idx,
                    numeric_value=float(values[idx - 1]),
                )
            instance.validation_actions.all().delete()
            ValidationAction.objects.create(
                dataset_instance=instance,
                validator=validator,
                user=validator.user,
                level=1,
                decision=ValidationAction.DECISION_APPROVE,
                comment="Validación demo ABEN: curva de proyecto ficticia aprobada.",
            )

    def _upsert_projects(self, admin_user, entity):
        projects = []
        category = entity.category
        for idx, (code, name, objective, physical, financial, stage) in enumerate(PROJECTS, start=1):
            project, _ = Project.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": objective,
                    "executor": "Agencia Boliviana de Energía Nuclear",
                    "location": "Bolivia",
                    "start_date": date(2026, 1, 1),
                    "end_date": date(2026, 12, 31),
                    "stage": stage,
                    "budget_mmbs": Decimal(str(8 + idx * 3)),
                    "category": category,
                    "workflow_status": Project.STATUS_APPROVED,
                    "workflow_comment": f"Avance físico {physical}% / financiero {financial}% (demo).",
                    "created_by": admin_user,
                    "approved_by": admin_user,
                    "approved_at": timezone.now(),
                    "is_active": True,
                },
            )
            project.entities.set([entity])
            projects.append(project)
        return projects

    def _upsert_project_report_configs(self, projects, summary_dataset, report_datasets):
        program_dataset = report_datasets["Curva programada proyectos ABEN"]
        executed_dataset = report_datasets["Curva ejecutada proyectos ABEN"]
        for project in projects:
            ProjectReportConfig.objects.update_or_create(
                project=project,
                name="Reporte ejecutivo ABEN",
                defaults={
                    "report_variant": ProjectReportConfig.VARIANT_PROJECT,
                    "report_dataset": summary_dataset,
                    "curve_program_dataset": program_dataset,
                    "curve_executed_dataset": executed_dataset,
                    "is_active": True,
                    "notes": "Configuración demo con datos ficticios ABEN.",
                },
            )

    def _write_audit_logs(self, users):
        admin = users["admin_aben"]
        logs = (
            ("SCHEMA", "Seed ABEN", "Esquemas demo ABEN aprobados", "Creación/actualización de esquemas mensuales [ABEN_DEMO]."),
            ("UPLOAD", "Seed ABEN", "Carga histórica demo ABEN", "Datos ficticios mensuales publicados para tablero ejecutivo [ABEN_DEMO]."),
            ("VALIDATION", "Seed ABEN", "Validación institucional demo ABEN", "Acciones de validación generadas para trazabilidad [ABEN_DEMO]."),
            ("OTHER", "Seed ABEN", "Proyectos demo ABEN", "Proyectos y reportes ejecutivos creados con información ficticia [ABEN_DEMO]."),
        )
        for action, module, obj, details in logs:
            AuditLog.objects.get_or_create(
                username=admin.username,
                action=action,
                module=module,
                object_repr=obj,
                details=details,
                defaults={"user": admin},
            )
