from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Membership
from config.urls import urlpatterns as config_urlpatterns
from ingest.models import DatasetInstance
from projects.models import Project
from schemas.models import DatasetType
from structure.models import Category, Entity, Sector, Subsector


urlpatterns = [*config_urlpatterns]


@override_settings(ROOT_URLCONF="kpis.tests")
class KpiDatasetVisibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="viewer_kpi", password="test-pass-123")
        self.user.profile.must_change_password = False
        self.user.profile.save(update_fields=["must_change_password"])

        sector = Sector.objects.create(name="Recursos")
        subsector = Subsector.objects.create(sector=sector, name="Litio")
        category = Category.objects.create(subsector=subsector, name="Industrializacion")
        self.entity = Entity.objects.create(category=category, code="YLB", name="YLB")

        self.normal_dataset = DatasetType.objects.create(
            entity=self.entity,
            name="Produccion KCl",
            validation_frequency=DatasetType.DAILY,
            status=DatasetType.STATUS_APPROVED,
            is_active=True,
        )
        project = Project.objects.create(
            name="Proyecto Curvas",
            category=category,
            workflow_status=Project.STATUS_APPROVED,
            is_active=True,
        )
        project.entities.add(self.entity)
        self.project_dataset = DatasetType.objects.create(
            entity=self.entity,
            project=project,
            name="Curva Programada",
            validation_frequency=DatasetType.WEEKLY,
            status=DatasetType.STATUS_APPROVED,
            is_active=True,
        )

        DatasetInstance.objects.create(
            dataset_type=self.normal_dataset,
            entity=self.entity,
            period=date(2026, 1, 1),
            state=DatasetInstance.STATE_PUBLISHED,
        )
        DatasetInstance.objects.create(
            dataset_type=self.project_dataset,
            entity=self.entity,
            period=date(2026, 1, 9),
            state=DatasetInstance.STATE_PUBLISHED,
        )

        Membership.objects.create(user=self.user, entity=self.entity, role="VIEWER")

    def test_charts_excludes_project_linked_datasets(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("kpis_charts"))

        self.assertEqual(response.status_code, 200)
        datasets = list(response.context["datasets"])
        dataset_ids = [dataset.id for dataset in datasets]
        self.assertIn(self.normal_dataset.id, dataset_ids)
        self.assertNotIn(self.project_dataset.id, dataset_ids)

    def test_dataset_data_rejects_project_linked_dataset(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("kpis_dataset_data", args=[self.project_dataset.id]))

        self.assertEqual(response.status_code, 404)
