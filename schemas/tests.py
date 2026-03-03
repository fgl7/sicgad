from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Membership
from projects.models import Project
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


@override_settings(
    ROOT_URLCONF="config.urls",
    AUTO_INGEST_CLEANUP_ENABLED=False,
)
class SchemaSeededCreateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.loader_user = User.objects.create_user(
            username="schema_loader",
            password="test-pass-123",
        )
        self.loader_user.profile.must_change_password = False
        self.loader_user.profile.save(update_fields=["must_change_password"])

        sector = Sector.objects.create(name="Sector Seed")
        subsector = Subsector.objects.create(sector=sector, name="Subsector Seed")
        self.category = Category.objects.create(subsector=subsector, name="Categoria Seed")
        self.entity = Entity.objects.create(
            category=self.category,
            code="SEED-1",
            name="Entidad Seed",
        )

        Membership.objects.create(
            user=self.loader_user,
            entity=self.entity,
            role="LOADER",
        )

        self.project = Project.objects.create(
            name="Convenio EDL",
            category=self.category,
            workflow_status=Project.STATUS_APPROVED,
            is_active=True,
            created_by=self.loader_user,
        )
        self.project.entities.add(self.entity)

    def test_schema_create_prefills_from_seeded_project_context(self):
        self.client.force_login(self.loader_user)

        response = self.client.get(
            reverse("schemas:schema_create"),
            {
                "project_id": self.project.id,
                "project": self.project.name,
                "entity": self.entity.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["seed_project_label"], self.project.name)
        self.assertEqual(response.context["seed_project_id"], self.project.id)
        self.assertEqual(
            response.context["form"].fields["name"].initial,
            f"{self.project.name} - resumen",
        )
        self.assertEqual(
            response.context["form"].fields["entity"].initial,
            self.entity,
        )
        self.assertContains(response, "Este esquema se esta creando para")
        self.assertContains(response, "Requiere aprobacion admin")
