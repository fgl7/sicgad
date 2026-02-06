from __future__ import annotations

from django.db import models
from django.utils.text import slugify


class Sector(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Subsector(models.Model):
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name="subsectors")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sector__name", "name"]
        unique_together = ("sector", "name")

    def __str__(self) -> str:
        return f"{self.sector.name} - {self.name}"


class Category(models.Model):
    subsector = models.ForeignKey(Subsector, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subsector__sector__name", "subsector__name", "name"]
        unique_together = ("subsector", "name")

    def __str__(self) -> str:
        return f"{self.subsector.sector.name} / {self.subsector.name} / {self.name}"


class EntityType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Entity(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="entities")
    entity_type = models.ForeignKey(EntityType, on_delete=models.PROTECT, related_name="entities")
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("category", "entity_type", "name")

    def __str__(self) -> str:
        return f"{self.entity_type.name}: {self.name}"
