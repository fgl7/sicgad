from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("UPLOAD", "Carga de datos"),
        ("SUBMIT", "Envío a validación"),
        ("VALIDATION", "Validación"),
        ("EDIT", "Corrección de datos"),
        ("DELETE", "Eliminación de datos"),
        ("USER", "Gestión de usuarios"),
        ("SCHEMA", "Gestión de esquemas"),
        ("OTHER", "Otro"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default="OTHER")
    module = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        timestamp = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{timestamp} - {self.action} - {self.username or 'Anonymous'}"
