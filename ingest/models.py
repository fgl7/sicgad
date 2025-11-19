from django.db import models

from accounts.models import Membership
from plants.models import Plant
from schemas.models import DatasetType


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

    row_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    last_error_summary = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("dataset_type", "plant", "period")

    def __str__(self) -> str:
        return f"{self.dataset_type} – {self.period}"

    @property
    def is_pending_validation(self) -> bool:
        return self.state in {
            self.STATE_SUBMITTED,
            self.STATE_VALIDATED_L1,
        }
