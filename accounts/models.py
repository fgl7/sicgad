from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from plants.models import Plant


class Membership(models.Model):
    ROLE_CHOICES = [
        ("LOADER", "Cargador"),
        ("VALIDATOR", "Validador"),
        ("VIEWER", "Visualizador"),
        ("ADMIN", "Administrador"),
    ]
    INSTITUTION_CHOICES = [
        ("YLB", "YLB"),
        ("MHE", "MHE"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name="memberships",
        null=True,
        blank=True,
        help_text="Dejar vacio solo para roles globales (por ejemplo, Admin global).",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    validation_level = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Nivel de validacion (1, 2, 3, ...). Solo aplica a validadores.",
    )
    can_validate_daily = models.BooleanField(
        default=False,
        help_text="Si es validador, puede participar en el flujo diario.",
    )
    can_validate_monthly = models.BooleanField(
        default=False,
        help_text="Si es validador, puede participar en el flujo mensual/certificacion.",
    )
    institution = models.CharField(
        max_length=10,
        choices=INSTITUTION_CHOICES,
        default="YLB",
        help_text="Institucion a la que pertenece este rol (YLB o MHE).",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"
        unique_together = ("user", "plant", "role", "validation_level")

    def __str__(self) -> str:
        plant_label = self.plant.code if self.plant else "GLOBAL"
        return f"{self.user.username} - {self.get_role_display()} - {plant_label}"


class AccountProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text="Si esta activo, el usuario debe cambiar su contrasena antes de usar el sistema.",
    )
    last_seen_schema_status = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha/hora en la que el usuario vio por ultima vez el estado de esquemas.",
    )
    last_seen_validation_status = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha/hora en la que el usuario vio por ultima vez el estado de sus cargas.",
    )
    last_seen_certification_alert = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha/hora en la que el usuario revisó las alertas de certificación mensual.",
    )

    def __str__(self) -> str:
        return f"Perfil de {self.user.username}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        AccountProfile.objects.create(user=instance, must_change_password=True)
