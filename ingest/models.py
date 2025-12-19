from django.db import models

from accounts.models import Membership
from plants.models import Plant
from schemas.models import DatasetType, ColumnDef


class DatasetInstance(models.Model):
    STATE_DRAFT = "DRAFT"
    STATE_SUBMITTED = "SUBMITTED"
    STATE_VALIDATED_L1 = "VALIDATED_L1"
    STATE_VALIDATED_L2 = "VALIDATED_L2"
    STATE_PUBLISHED = "PUBLISHED"
    STATE_LOCKED = "LOCKED"

    STATE_CHOICES = [
        (STATE_DRAFT, "Borrador"),
        (STATE_SUBMITTED, "Enviado"),
        (STATE_VALIDATED_L1, "Validado nivel 1"),
        (STATE_VALIDATED_L2, "Validado nivel 2"),
        (STATE_PUBLISHED, "Publicado"),
        (STATE_LOCKED, "Bloqueado"),
    ]

    dataset_type = models.ForeignKey(
        DatasetType,
        on_delete=models.CASCADE,
        related_name="instances",
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name="dataset_instances",
    )
    period = models.DateField(
        help_text="Fecha o día de referencia del dataset (para diarios).",
    )

    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default=STATE_DRAFT,
    )

    created_by = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_instances",
    )

    raw_file = models.FileField(
        upload_to="ingest/raw/",
        null=True,
        blank=True,
        help_text="Archivo fuente cargado (CSV/Excel).",
    )

    historical_batch = models.ForeignKey(
        "HistoricalImportBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instances",
        help_text="Batch de importación histórica que generó esta instancia (si aplica).",
    )

    row_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    last_error_summary = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("dataset_type", "plant", "period")

    def __str__(self) -> str:
        return f"{self.dataset_type} - {self.period}"

    @property
    def is_pending_validation(self) -> bool:
        return self.state in {
            self.STATE_SUBMITTED,
            self.STATE_VALIDATED_L1,
        }


class PublishedDataPoint(models.Model):
    """
    Representa un valor publicado (oficial) para una celda de un dataset.
    Se usa tanto para datasets diarios como para los de certificación mensual.
    """

    instance = models.ForeignKey(
        DatasetInstance,
        on_delete=models.CASCADE,
        related_name="published_points",
    )
    column = models.ForeignKey(
        ColumnDef,
        on_delete=models.CASCADE,
        related_name="published_points",
    )
    row_index = models.PositiveIntegerField(
        help_text="Índice de fila dentro del archivo original (comenzando en 1).",
    )

    numeric_value = models.FloatField(null=True, blank=True)
    text_value = models.TextField(blank=True)
    date_value = models.DateField(null=True, blank=True)
    bool_value = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["instance", "row_index", "column"]
        indexes = [
            models.Index(fields=["instance", "column"]),
            models.Index(fields=["column"]),
        ]

    def __str__(self) -> str:
        return f"{self.instance_id} - {self.column.name} - row {self.row_index}"


class DatasetChangeRequest(models.Model):
    instance = models.ForeignKey(
        DatasetInstance,
        on_delete=models.CASCADE,
        related_name="change_requests",
    )
    submitted_by = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_change_requests",
    )
    justification = models.TextField()
    target_instance = models.ForeignKey(
        DatasetInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_change_requests",
    )
    target_period = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        suffix = f" - {self.target_period}" if self.target_period else ""
        return f"Cambio {self.instance_id}{suffix}"


class DatasetChangeAttachment(models.Model):
    request = models.ForeignKey(
        DatasetChangeRequest,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="ingest/change_support/")
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return self.original_name or self.file.name


class HistoricalImportBatch(models.Model):
    STATUS_RUNNING = "RUNNING"
    STATUS_DONE = "DONE"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_RUNNING, "En proceso"),
        (STATUS_DONE, "Completado"),
        (STATUS_FAILED, "Fallido"),
    ]

    dataset_type = models.ForeignKey(
        DatasetType,
        on_delete=models.CASCADE,
        related_name="historical_imports",
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name="historical_imports",
    )
    created_by = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historical_imports",
    )
    source_file = models.FileField(
        upload_to="ingest/historical/",
        null=True,
        blank=True,
        help_text="Archivo original usado para cargar el histórico.",
    )
    date_column_name = models.CharField(
        max_length=100,
        help_text="Nombre del encabezado que contiene la fecha por fila.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
    )
    error_summary = models.TextField(blank=True)

    total_rows = models.PositiveIntegerField(default=0)
    total_days = models.PositiveIntegerField(default=0)
    created_instances = models.PositiveIntegerField(default=0)
    updated_instances = models.PositiveIntegerField(default=0)
    skipped_instances = models.PositiveIntegerField(default=0)

    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Histórico {self.dataset_type} ({self.plant.code}) - {self.created_at:%Y-%m-%d %H:%M}"
