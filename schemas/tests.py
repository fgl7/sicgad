from django.core.exceptions import ValidationError
from django.test import TestCase

from plants.models import Plant
from projects.models import Project

from .models import DatasetType


class DatasetTypeCleanTests(TestCase):
    def test_requires_plant_or_project(self):
        dataset = DatasetType(
            name="Daily Production",
            version=1,
            validation_frequency=DatasetType.DAILY,
        )
        with self.assertRaises(ValidationError):
            dataset.full_clean()

    def test_rejects_both_plant_and_project(self):
        plant = Plant.objects.create(code="PLANT", name="Plant")
        project = Project.objects.create(name="Project")
        dataset = DatasetType(
            name="Daily Production",
            version=1,
            validation_frequency=DatasetType.DAILY,
            plant=plant,
            project=project,
        )
        with self.assertRaises(ValidationError):
            dataset.full_clean()

    def test_slug_generated_for_plant(self):
        plant = Plant.objects.create(code="PCS", name="Plant")
        dataset = DatasetType.objects.create(
            name="Daily Production",
            version=1,
            validation_frequency=DatasetType.DAILY,
            plant=plant,
            status=DatasetType.STATUS_APPROVED,
            is_active=True,
        )
        self.assertTrue(dataset.slug)
        self.assertIn("pcs-daily-production-v1", dataset.slug)
