from django.conf import settings
from django.db import models

from accounts.models import Membership
from ingest.models import DatasetInstance


class ValidationAction(models.Model):
    DECISION_APPROVE = "APPROVE"
    DECISION_REJECT = "REJECT"

    DECISION_CHOICES = [
        (DECISION_APPROVE, "Aprobar"),
        (DECISION_REJECT, "Rechazar"),
    ]

    dataset_instance = models.ForeignKey(
        DatasetInstance,
        on_delete=models.CASCADE,
        related_name="validation_actions",
    )
    validator = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validation_actions",
        help_text="Membresía del validador que tomó la acción.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manual_validation_actions",
    )
    level = models.PositiveIntegerField(
        help_text="Nivel de validación (1, 2, 3...).",
    )
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.dataset_instance} – L{self.level} – {self.decision}"
