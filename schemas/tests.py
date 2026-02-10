from django.core.exceptions import ValidationError
from django.test import TestCase

from structure.models import Category, Entity, Sector, Subsector

from .models import DatasetType


class DatasetTypeCleanTests(TestCase):
    def _build_entity(self, code="PCS") -> Entity:
        sector = Sector.objects.create(name=f"Sector {code}")
        subsector = Subsector.objects.create(sector=sector, name=f"Subsector {code}")
        category = Category.objects.create(subsector=subsector, name=f"Categoria {code}")
        return Entity.objects.create(category=category, code=code, name=f"Entidad {code}")

    def test_requires_entity(self):
        dataset = DatasetType(
            name="Daily Production",
            version=1,
            validation_frequency=DatasetType.DAILY,
        )
        with self.assertRaises(ValidationError):
            dataset.full_clean()

    def test_accepts_entity(self):
        entity = self._build_entity("ENT")
        dataset = DatasetType(
            name="Daily Production",
            version=1,
            validation_frequency=DatasetType.DAILY,
            entity=entity,
        )

        dataset.full_clean()

    def test_slug_generated_for_entity(self):
        entity = self._build_entity("PCS")
        dataset = DatasetType.objects.create(
            name="Daily Production",
            version=1,
            validation_frequency=DatasetType.DAILY,
            entity=entity,
            status=DatasetType.STATUS_APPROVED,
            is_active=True,
        )
        self.assertTrue(dataset.slug)
        self.assertIn("pcs-daily-production-v1", dataset.slug)
