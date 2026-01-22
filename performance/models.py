from __future__ import annotations

from django.db import models

from plants.models import Plant
from schemas.models import ColumnDef, DatasetType


class PerformanceVariable(models.Model):
    """
    Variable metodológica "estable" (según la propuesta de desempeño).

    Estas variables no dependen de nombres de columnas en esquemas; el vínculo se
    hace vía PerformanceVariableMapping por IDs de DatasetType/ColumnDef.
    """

    VALUE_TYPE_CHOICES = [
        ("NUMBER", "Numérico"),
        ("TEXT", "Texto"),
        ("DATE", "Fecha"),
        ("BOOLEAN", "Booleano"),
    ]

    key = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Llave estable (ej: pcs.brine_volume_m3, kcl.feed_mass_tm).",
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name="performance_variables",
    )
    label = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, blank=True)
    value_type = models.CharField(
        max_length=20,
        choices=VALUE_TYPE_CHOICES,
        default="NUMBER",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plant__code", "key"]

    def __str__(self) -> str:
        return f"{self.plant.code} - {self.key}"


class PerformanceVariableMapping(models.Model):
    """
    Mapeo administrable (solo Admin): variable metodológica -> columna fuente SICGAD.

    Nota: Se enlaza por FK a DatasetType y ColumnDef para resistir renombres.
    """

    AGG_CHOICES = [
        ("SUM", "Suma"),
        ("AVG", "Promedio"),
        ("MAX", "Máximo"),
        ("MIN", "Mínimo"),
        ("LAST", "Último (por periodo)"),
        ("NONE", "Sin agregación"),
    ]

    TRANSFORM_CHOICES = [
        ("NONE", "Ninguna"),
        ("MULTIPLY", "Multiplicar por factor"),
        ("ADD", "Sumar factor"),
    ]

    STAGE_CHOICES = [
        ("DRAFT", "Draft"),
        ("CERTIFIED", "Certificado"),
    ]

    variable = models.ForeignKey(
        PerformanceVariable,
        on_delete=models.CASCADE,
        related_name="mappings",
    )
    dataset_type = models.ForeignKey(
        DatasetType,
        on_delete=models.PROTECT,
        related_name="performance_mappings",
    )
    column = models.ForeignKey(
        ColumnDef,
        on_delete=models.PROTECT,
        related_name="performance_mappings",
    )
    aggregation = models.CharField(max_length=10, choices=AGG_CHOICES, default="SUM")
    transform = models.CharField(max_length=10, choices=TRANSFORM_CHOICES, default="NONE")
    transform_value = models.FloatField(null=True, blank=True)
    offset_months = models.IntegerField(
        default=0,
        help_text="Desfase para fuentes mensuales (ej: PCS por lote). m -> m - offset_months.",
    )
    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="DRAFT",
        help_text="Permite definir mapeos distintos para resultados Draft vs Certificado.",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["variable__plant__code", "variable__key", "-is_active", "-updated_at"]
        unique_together = ("variable", "dataset_type", "column", "offset_months", "stage")

    def __str__(self) -> str:
        return f"{self.variable.key} -> {self.dataset_type.slug}:{self.column.name}"


class PerformanceIndicator(models.Model):
    """
    Definición de indicador (catálogo).

    La fórmula se implementará en el motor (Tarea 18) pero se versiona y describe aquí.
    """

    key = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Llave estable del indicador (ej: pcs.yield_monthly_pct).",
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name="performance_indicators",
    )
    label = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    formula_text = models.TextField(
        blank=True,
        help_text="Descripción textual de la fórmula (referencial, para auditoría).",
    )
    variables = models.ManyToManyField(
        PerformanceVariable,
        related_name="indicators",
        blank=True,
        help_text="Variables metodológicas requeridas.",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plant__code", "key"]

    def __str__(self) -> str:
        return f"{self.plant.code} - {self.key}"


class PerformanceIndicatorResult(models.Model):
    FREQ_DAILY = "DAILY"
    FREQ_MONTHLY = "MONTHLY"

    STATUS_SUCCESS = "SUCCESS"
    STATUS_NOT_CALCULABLE = "NOT_CALCULABLE"
    STATUS_ERROR = "ERROR"

    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Calculado"),
        (STATUS_NOT_CALCULABLE, "No calculable"),
        (STATUS_ERROR, "Error"),
    ]

    FREQ_CHOICES = [
        (FREQ_DAILY, "Diario"),
        (FREQ_MONTHLY, "Mensual"),
    ]

    indicator = models.ForeignKey(
        PerformanceIndicator,
        on_delete=models.CASCADE,
        related_name="results",
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name="performance_results",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    frequency = models.CharField(
        max_length=20,
        choices=FREQ_CHOICES,
        default=FREQ_MONTHLY,
        help_text="Frecuencia del resultado calculado.",
    )
    stage = models.CharField(
        max_length=20,
        choices=PerformanceVariableMapping.STAGE_CHOICES,
        default="DRAFT",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS)

    numeric_value = models.FloatField(null=True, blank=True)
    text_value = models.TextField(blank=True)

    trace = models.JSONField(default=dict, blank=True)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "plant__code", "indicator__key"]
        unique_together = ("indicator", "plant", "period_end", "frequency")

    def __str__(self) -> str:
        return f"{self.plant.code} {self.indicator.key} {self.period_end} {self.frequency} ({self.status})"

# Create your models here.
