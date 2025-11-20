from django.db import models
from django.utils.text import slugify

from plants.models import Plant


class DatasetType(models.Model):
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"

    VALIDATION_FREQUENCY_CHOICES = [
        (DAILY, "Diaria"),
        (MONTHLY, "Mensual"),
    ]

    STATUS_DRAFT = "DRAFT"
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Borrador"),
        (STATUS_PENDING, "Pendiente aprobación"),
        (STATUS_APPROVED, "Aprobado"),
        (STATUS_REJECTED, "Rechazado"),
    ]

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name="dataset_types",
    )
    name = models.CharField(
        max_length=255,
        help_text="Nombre del dataset, por ejemplo 'Producción diaria PICP'.",
    )
    version = models.PositiveIntegerField(default=1)
    validation_frequency = models.CharField(
        max_length=20,
        choices=VALIDATION_FREQUENCY_CHOICES,
        default=DAILY,
        help_text="Define si este dataset se valida a diario o como consolidado mensual.",
    )
    is_certification = models.BooleanField(
        default=False,
        help_text="Indica si este esquema es para certificación mensual creada por Administración.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Solo un esquema por familia (planta+nombre) deberia estar activo a la vez.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        help_text="Estado de aprobación del esquema.",
    )
    status_comment = models.TextField(
        blank=True,
        help_text="Comentario de la última decisión de aprobación/rechazo.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plant__code", "name", "-version"]
        unique_together = ("plant", "name", "version")

    def __str__(self) -> str:
        return f"{self.plant.code} - {self.name} v{self.version}"

    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="Slug legible para URLs, basado en planta, nombre y versión.",
    )

    def save(self, *args, **kwargs):
        if not self.slug and self.plant_id and self.name and self.version:
            base = f"{self.plant.code}-{self.name}-v{self.version}"
            self.slug = slugify(base)
        super().save(*args, **kwargs)


class ColumnDef(models.Model):
    DATA_TYPE_CHOICES = [
        ("INTEGER", "Entero"),
        ("FLOAT", "Decimal"),
        ("STRING", "Texto"),
        ("DATE", "Fecha"),
        ("BOOLEAN", "Booleano"),
        ("CHOICE", "Categórico"),
    ]

    AXIS_ROLE_CHOICES = [
        ("NONE", "Ninguno"),
        ("X", "Eje X"),
        ("Y", "Eje Y"),
        ("SERIES", "Serie"),
        ("FILTER", "Filtro"),
    ]

    DEFAULT_AGG_CHOICES = [
        ("SUM", "Suma"),
        ("AVG", "Promedio"),
        ("MAX", "Máximo"),
        ("MIN", "Mínimo"),
        ("COUNT", "Conteo"),
        ("NONE", "Sin agregación"),
    ]

    dataset_type = models.ForeignKey(
        DatasetType,
        on_delete=models.CASCADE,
        related_name="columns",
    )
    name = models.CharField(
        max_length=100,
        help_text="Nombre interno del campo (sin espacios).",
    )
    label = models.CharField(
        max_length=255,
        help_text="Nombre legible para usuarios.",
    )
    data_type = models.CharField(
        max_length=20,
        choices=DATA_TYPE_CHOICES,
        default="FLOAT",
    )
    required = models.BooleanField(default=False)

    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    regex = models.CharField(
        max_length=255,
        blank=True,
        help_text="Expresión regular opcional para validar texto.",
    )
    choices_raw = models.TextField(
        blank=True,
        help_text="Lista de opciones para campos categóricos, una por línea.",
    )

    unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Unidad para KPIs y gráficos (t/día, m3, kWh, %...).",
    )
    axis_role = models.CharField(
        max_length=10,
        choices=AXIS_ROLE_CHOICES,
        default="NONE",
        help_text="Rol principal en gráficos (eje X, Y, serie o filtro).",
    )
    default_agg = models.CharField(
        max_length=10,
        choices=DEFAULT_AGG_CHOICES,
        default="SUM",
        help_text="Tipo de agregación por defecto para KPIs.",
    )
    is_primary_kpi = models.BooleanField(
        default=False,
        help_text="Indica si el campo es un KPI principal que debería aparecer por defecto.",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Orden sugerido para mostrar en tablas y formularios.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Permite desactivar una columna sin borrar el historial.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["dataset_type", "display_order", "name"]
        unique_together = ("dataset_type", "name")

    def __str__(self) -> str:
        return f"{self.dataset_type} - {self.name}"
