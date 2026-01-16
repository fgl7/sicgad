from django.db import models
from django.core.exceptions import ValidationError

from plants.models import Plant


class Project(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    executor = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    stage = models.CharField(max_length=120, blank=True)
    budget_mmbs = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    plants = models.ManyToManyField(
        Plant,
        related_name="projects",
        blank=True,
        help_text="Plantas o unidades operativas asociadas al proyecto.",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProjectReportConfig(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="report_configs",
    )
    name = models.CharField(max_length=255, default="Reporte de proyecto")
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

    def clean(self):
        errors = {}
        for field_name in (
            "report_dataset",
            "curve_program_dataset",
            "curve_executed_dataset",
        ):
            dataset = getattr(self, field_name, None)
            if dataset and dataset.project_id != self.project_id:
                errors[field_name] = "El esquema debe pertenecer al mismo proyecto."

        if self.curve_executed_dataset and self.curve_executed_dataset.validation_frequency not in (
            "WEEKLY",
            "MONTHLY",
        ):
            errors["curve_executed_dataset"] = (
                "El esquema ejecutado debe ser semanal o mensual."
            )

        if errors:
            raise ValidationError(errors)
