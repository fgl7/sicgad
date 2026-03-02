from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from structure.models import Entity


class Project(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente de aprobacion"),
        (STATUS_APPROVED, "Aprobado"),
        (STATUS_REJECTED, "Rechazado"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    executor = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    stage = models.CharField(max_length=120, blank=True)
    budget_mmbs = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    category = models.ForeignKey(
        "structure.Category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="projects",
    )
    entities = models.ManyToManyField(
        Entity,
        related_name="projects",
        blank=True,
        help_text="Entidades operativas asociadas al proyecto.",
    )
    workflow_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    workflow_comment = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_projects",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        if self.category_id and self.pk:
            invalid_entities = self.entities.exclude(category_id=self.category_id)
            if invalid_entities.exists():
                raise ValidationError(
                    {
                        "entities": (
                            "Todas las entidades del proyecto deben pertenecer "
                            "a la categoria seleccionada."
                        )
                    }
                )


class ProjectReportConfig(models.Model):
    VARIANT_AUTO = "auto"
    VARIANT_PROJECT = "project"
    VARIANT_AGREEMENT = "agreement"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="report_configs",
    )
    name = models.CharField(max_length=255, default="Reporte de proyecto")
    report_variant = models.CharField(
        max_length=50,
        default=VARIANT_AUTO,
        help_text=(
            "Variante del visor. Use 'auto' para deteccion automatica o un slug "
            "explicito como 'project', 'agreement' u otra variante futura."
        ),
    )
    report_dataset = models.ForeignKey(
        "schemas.DatasetType",
        on_delete=models.PROTECT,
        related_name="project_report_configs",
        help_text="Esquema principal para los datos del reporte.",
    )
    curve_program_dataset = models.ForeignKey(
        "schemas.DatasetType",
        on_delete=models.PROTECT,
        related_name="project_curve_program_configs",
        help_text="Esquema con la curva programada (carga unica).",
    )
    curve_executed_dataset = models.ForeignKey(
        "schemas.DatasetType",
        on_delete=models.PROTECT,
        related_name="project_curve_executed_configs",
        help_text="Esquema con la curva ejecutada (semanal o mensual).",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name", "name"]
        unique_together = ("project", "name")

    def __str__(self) -> str:
        return f"{self.project} - {self.name}"

    def normalized_report_variant(self) -> str:
        raw_value = (self.report_variant or self.VARIANT_AUTO).strip().lower()
        if raw_value in {"convenio", "agreement"}:
            return self.VARIANT_AGREEMENT
        if raw_value in {"proyecto", "project"}:
            return self.VARIANT_PROJECT
        if raw_value == self.VARIANT_AUTO:
            return self.VARIANT_AUTO
        normalized = slugify(raw_value)
        return normalized or self.VARIANT_AUTO

    def save(self, *args, **kwargs):
        self.report_variant = self.normalized_report_variant()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        project_entity_ids = set()
        if self.project_id:
            project_entity_ids = set(
                self.project.entities.values_list("id", flat=True)
            )
            if not project_entity_ids:
                errors["project"] = (
                    "El proyecto debe tener al menos una entidad asociada antes de "
                    "configurar reportes."
                )

        for field_name in (
            "report_dataset",
            "curve_program_dataset",
            "curve_executed_dataset",
        ):
            dataset = getattr(self, field_name, None)
            if dataset and self.project and self.project.category_id:
                if not dataset.entity_id or dataset.entity.category_id != self.project.category_id:
                    errors[field_name] = "El esquema debe pertenecer a la misma categoria del proyecto."
                    continue
                if project_entity_ids and dataset.entity_id not in project_entity_ids:
                    errors[field_name] = (
                        "El esquema debe pertenecer a una de las entidades asociadas "
                        "al proyecto."
                    )

        if self.curve_executed_dataset and self.curve_executed_dataset.validation_frequency not in (
            "WEEKLY",
            "MONTHLY",
        ):
            errors["curve_executed_dataset"] = (
                "El esquema ejecutado debe ser semanal o mensual."
            )

        if errors:
            raise ValidationError(errors)
