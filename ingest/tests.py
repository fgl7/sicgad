from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Membership
from schemas.models import DatasetType
from structure.models import Category, Entity, Sector, Subsector

from .forms import DatasetInstanceUploadForm, HistoricalDatasetUploadForm


@override_settings(
    ROOT_URLCONF="config.urls",
    AUTO_INGEST_CLEANUP_ENABLED=False,
)
class IngestSecurityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="loader_ingest", password="test-pass-123")
        self.user.profile.must_change_password = False
        self.user.profile.save(update_fields=["must_change_password"])

        sector = Sector.objects.create(name="Sector Ingest")
        subsector = Subsector.objects.create(sector=sector, name="Subsector Ingest")
        category = Category.objects.create(subsector=subsector, name="Categoria Ingest")
        self.entity = Entity.objects.create(category=category, code="ING", name="Entidad Ingest")
        self.other_entity = Entity.objects.create(category=category, code="ING2", name="Entidad Ingest 2")

        Membership.objects.create(user=self.user, entity=self.entity, role="LOADER")

        self.dataset = DatasetType.objects.create(
            name="Dataset Ingest",
            version=1,
            validation_frequency=DatasetType.DAILY,
            entity=self.entity,
            status=DatasetType.STATUS_APPROVED,
            is_active=True,
        )

    def test_upload_form_rejects_disallowed_extension(self):
        form = DatasetInstanceUploadForm(
            data={
                "dataset_type": self.dataset.id,
                "entity": self.entity.id,
                "period": "2026-01-01",
            },
            files={
                "raw_file": SimpleUploadedFile("malicioso.exe", b"data", content_type="application/octet-stream"),
            },
            loader_entities=[self.entity.id],
        )

        self.assertFalse(form.is_valid())
        self.assertIn("raw_file", form.errors)

    def test_historical_form_rejects_entity_mismatch(self):
        form = HistoricalDatasetUploadForm(
            data={
                "dataset_type": self.dataset.id,
                "entity": self.other_entity.id,
                "date_column_name": "fecha",
            },
            files={
                "raw_file": SimpleUploadedFile("historico.csv", b"fecha\n2026-01-01\n", content_type="text/csv"),
            },
            loader_entities=[self.entity.id, self.other_entity.id],
        )

        self.assertFalse(form.is_valid())
        self.assertIn("entity", form.errors)

    def test_download_template_requires_login(self):
        response = self.client.get(reverse("ingest:download_template"), {"dataset_type": self.dataset.id})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
