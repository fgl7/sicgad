from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Membership
from config.urls import urlpatterns as config_urlpatterns
from ingest.models import DatasetInstance
from projects.forms import ProjectForm
from projects.models import Project, ProjectReportConfig
from schemas.models import DatasetType
from structure.models import Category, Entity, Sector, Subsector


urlpatterns = [*config_urlpatterns]


@override_settings(
    ROOT_URLCONF="projects.tests",
    AUTO_INGEST_CLEANUP_ENABLED=False,
)
class ProjectsModuleTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.viewer_loader_mixed = User.objects.create_user(
            username="mixed_user",
            password="test-pass-123",
        )
        self.loader_same_scope = User.objects.create_user(
            username="loader_user",
            password="test-pass-123",
        )
        self.viewer_same_scope = User.objects.create_user(
            username="viewer_user",
            password="test-pass-123",
        )
        self.admin_user = User.objects.create_user(
            username="admin_user",
            password="test-pass-123",
        )
        for user in (
            self.viewer_loader_mixed,
            self.loader_same_scope,
            self.viewer_same_scope,
            self.admin_user,
        ):
            user.profile.must_change_password = False
            user.profile.save(update_fields=["must_change_password"])

        sector = Sector.objects.create(name="Recursos")
        subsector = Subsector.objects.create(sector=sector, name="Litio")
        self.category_projects = Category.objects.create(
            subsector=subsector,
            name="Industrializacion",
        )
        self.category_other = Category.objects.create(
            subsector=subsector,
            name="Exploracion",
        )

        self.entity_a = Entity.objects.create(
            category=self.category_projects,
            code="ENT-A",
            name="Entidad A",
        )
        self.entity_b = Entity.objects.create(
            category=self.category_projects,
            code="ENT-B",
            name="Entidad B",
        )
        self.entity_other_category = Entity.objects.create(
            category=self.category_other,
            code="ENT-C",
            name="Entidad C",
        )

        self.summary_dataset_a = self._create_dataset(
            self.entity_a,
            "Resumen Proyecto",
            DatasetType.MONTHLY,
        )
        self.program_dataset_a = self._create_dataset(
            self.entity_a,
            "Curva Programada",
            DatasetType.MONTHLY,
        )
        self.executed_dataset_a = self._create_dataset(
            self.entity_a,
            "Curva Ejecutada",
            DatasetType.WEEKLY,
        )
        self.summary_dataset_b = self._create_dataset(
            self.entity_b,
            "Resumen Proyecto B",
            DatasetType.MONTHLY,
        )

        self.project = Project.objects.create(
            name="Proyecto Salar",
            category=self.category_projects,
            workflow_status=Project.STATUS_APPROVED,
            is_active=True,
        )
        self.project.entities.add(self.entity_a)

        self.config = ProjectReportConfig.objects.create(
            project=self.project,
            name="Reporte Semanal",
            report_dataset=self.summary_dataset_a,
            curve_program_dataset=self.program_dataset_a,
            curve_executed_dataset=self.executed_dataset_a,
            is_active=True,
        )

        DatasetInstance.objects.create(
            dataset_type=self.summary_dataset_a,
            entity=self.entity_a,
            period=date(2026, 1, 31),
            state=DatasetInstance.STATE_DRAFT,
        )
        DatasetInstance.objects.create(
            dataset_type=self.program_dataset_a,
            entity=self.entity_a,
            period=date(2026, 1, 31),
            state=DatasetInstance.STATE_DRAFT,
        )
        DatasetInstance.objects.create(
            dataset_type=self.executed_dataset_a,
            entity=self.entity_a,
            period=date(2026, 1, 12),
            state=DatasetInstance.STATE_DRAFT,
        )

    def _create_dataset(self, entity, name, frequency):
        return DatasetType.objects.create(
            entity=entity,
            name=name,
            validation_frequency=frequency,
            status=DatasetType.STATUS_APPROVED,
            is_active=True,
        )

    def test_project_form_rejects_entities_outside_selected_category(self):
        form = ProjectForm(
            data={
                "name": "Proyecto Invalido",
                "category": self.category_projects.id,
                "entities": [self.entity_other_category.id],
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("entities", form.errors)

    def test_loader_can_create_project_and_it_starts_pending(self):
        Membership.objects.create(
            user=self.loader_same_scope,
            entity=self.entity_a,
            role="LOADER",
        )

        self.client.force_login(self.loader_same_scope)
        response = self.client.post(
            reverse("projects:project_create"),
            data={
                "name": "Proyecto Nuevo",
                "category": self.category_projects.id,
                "entities": [self.entity_a.id],
                "executor": "YLB",
            },
        )

        self.assertEqual(response.status_code, 302)
        created = Project.objects.get(name="Proyecto Nuevo")
        self.assertEqual(created.created_by_id, self.loader_same_scope.id)
        self.assertEqual(created.workflow_status, Project.STATUS_PENDING)
        self.assertFalse(created.is_active)

    def test_admin_cannot_create_project_catalog_entries(self):
        Membership.objects.create(
            user=self.admin_user,
            role="ADMIN",
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("projects:project_create"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("projects:project_list"))

    def test_admin_can_approve_project(self):
        Membership.objects.create(
            user=self.admin_user,
            role="ADMIN",
        )
        pending_project = Project.objects.create(
            name="Proyecto Pendiente",
            category=self.category_projects,
            workflow_status=Project.STATUS_PENDING,
            created_by=self.loader_same_scope,
            is_active=False,
        )
        pending_project.entities.add(self.entity_a)

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("projects:project_review", args=[pending_project.id, "approve"])
        )

        self.assertEqual(response.status_code, 302)
        pending_project.refresh_from_db()
        self.assertEqual(pending_project.workflow_status, Project.STATUS_APPROVED)
        self.assertEqual(pending_project.approved_by_id, self.admin_user.id)
        self.assertTrue(pending_project.is_active)

    def test_admin_created_loader_can_create_project_and_submit_seeded_schema(self):
        Membership.objects.create(
            user=self.admin_user,
            role="ADMIN",
        )

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("accounts:admin_user_create"),
            data={
                "username": "project_loader_new",
                "password1": "test-pass-123",
                "password2": "test-pass-123",
                "role": "LOADER",
                "scope_mode": "ENTITY",
                "category": [self.category_projects.id],
                "entity": [self.entity_a.id],
            },
        )

        self.assertEqual(response.status_code, 302)

        created_loader = get_user_model().objects.get(username="project_loader_new")
        loader_memberships = Membership.objects.filter(
            user=created_loader,
            role="LOADER",
            is_active=True,
        )
        self.assertEqual(loader_memberships.count(), 1)
        self.assertEqual(loader_memberships.first().entity_id, self.entity_a.id)

        created_loader.profile.must_change_password = False
        created_loader.profile.save(update_fields=["must_change_password"])

        self.client.force_login(created_loader)
        response = self.client.post(
            reverse("projects:project_create"),
            data={
                "name": "Convenio Operativo",
                "category": self.category_projects.id,
                "entities": [self.entity_a.id],
                "executor": "YLB",
            },
        )

        self.assertEqual(response.status_code, 302)

        created_project = Project.objects.get(name="Convenio Operativo")
        self.assertEqual(created_project.created_by_id, created_loader.id)
        self.assertEqual(created_project.workflow_status, Project.STATUS_PENDING)
        self.assertFalse(created_project.is_active)

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("projects:project_review", args=[created_project.id, "approve"])
        )

        self.assertEqual(response.status_code, 302)
        created_project.refresh_from_db()
        self.assertEqual(created_project.workflow_status, Project.STATUS_APPROVED)
        self.assertTrue(created_project.is_active)

        self.client.force_login(created_loader)
        response = self.client.get(
            reverse("schemas:schema_create"),
            {
                "project_id": created_project.id,
                "project": created_project.name,
                "entity": self.entity_a.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].fields["name"].initial,
            f"{created_project.name} - resumen",
        )
        self.assertEqual(
            response.context["form"].fields["entity"].initial,
            self.entity_a,
        )

        response = self.client.post(
            reverse("schemas:schema_create"),
            data={
                "seed_project_id": created_project.id,
                "seed_project_label": created_project.name,
                "seed_entity_id": self.entity_a.id,
                "entity": self.entity_a.id,
                "name": f"{created_project.name} - resumen",
                "version": "1",
                "validation_frequency": DatasetType.MONTHLY,
                "columns-TOTAL_FORMS": "1",
                "columns-INITIAL_FORMS": "0",
                "columns-MIN_NUM_FORMS": "0",
                "columns-MAX_NUM_FORMS": "1000",
                "columns-0-name": "fecha_corte",
                "columns-0-label": "Fecha corte",
                "columns-0-data_type": "DATE",
                "columns-0-required": "on",
                "columns-0-min_value": "",
                "columns-0-max_value": "",
                "columns-0-regex": "",
                "columns-0-choices_raw": "",
                "columns-0-unit": "",
                "columns-0-axis_role": "X",
                "columns-0-default_agg": "NONE",
                "columns-0-display_order": "0",
                "columns-0-is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)

        created_schema = DatasetType.objects.get(
            entity=self.entity_a,
            name=f"{created_project.name} - resumen",
            version=1,
        )
        self.assertEqual(created_schema.status, DatasetType.STATUS_DRAFT)
        self.assertFalse(created_schema.is_active)
        self.assertEqual(created_schema.project_id, created_project.id)

        response = self.client.post(
            reverse("schemas:schema_submit", args=[created_schema.slug])
        )

        self.assertEqual(response.status_code, 302)
        created_schema.refresh_from_db()
        self.assertEqual(created_schema.status, DatasetType.STATUS_PENDING)
        self.assertFalse(created_schema.is_active)

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("schemas:schema_approve", args=[created_schema.slug])
        )

        self.assertEqual(response.status_code, 302)
        created_schema.refresh_from_db()
        self.assertEqual(created_schema.status, DatasetType.STATUS_APPROVED)
        self.assertTrue(created_schema.is_active)

        auto_config = ProjectReportConfig.objects.get(project=created_project)
        self.assertEqual(auto_config.report_dataset_id, created_schema.id)
        self.assertEqual(auto_config.curve_program_dataset_id, created_schema.id)
        self.assertEqual(auto_config.curve_executed_dataset_id, created_schema.id)
        self.assertTrue(auto_config.is_active)

    def test_report_config_validation_rejects_datasets_outside_project_entities(self):
        config = ProjectReportConfig(
            project=self.project,
            name="Configuracion Invalida",
            report_dataset=self.summary_dataset_b,
            curve_program_dataset=self.program_dataset_a,
            curve_executed_dataset=self.executed_dataset_a,
            is_active=True,
        )

        with self.assertRaises(ValidationError) as raised:
            config.full_clean()

        self.assertIn("report_dataset", raised.exception.message_dict)

    def test_mixed_roles_do_not_unlock_drafts_for_other_entity(self):
        Membership.objects.create(
            user=self.viewer_loader_mixed,
            entity=self.entity_a,
            role="VIEWER",
        )
        Membership.objects.create(
            user=self.viewer_loader_mixed,
            entity=self.entity_b,
            role="LOADER",
        )

        self.client.force_login(self.viewer_loader_mixed)
        response = self.client.get(
            reverse("projects:report_detail", args=[self.config.id]),
            {"source": "draft"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["source"], "published")
        self.assertFalse(response.context["can_see_drafts"])

    def test_loader_with_matching_entity_can_view_drafts(self):
        Membership.objects.create(
            user=self.loader_same_scope,
            entity=self.entity_a,
            role="LOADER",
        )

        self.client.force_login(self.loader_same_scope)
        response = self.client.get(
            reverse("projects:report_detail", args=[self.config.id]),
            {"source": "draft"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["source"], "draft")
        self.assertTrue(response.context["can_see_drafts"])

    def test_explicit_agreement_variant_is_used(self):
        agreement_config = ProjectReportConfig.objects.create(
            project=self.project,
            name="Reporte Ejecutivo",
            report_variant="agreement",
            report_dataset=self.summary_dataset_a,
            curve_program_dataset=self.program_dataset_a,
            curve_executed_dataset=self.executed_dataset_a,
            is_active=True,
        )
        Membership.objects.create(
            user=self.viewer_same_scope,
            entity=self.entity_a,
            role="VIEWER",
        )

        self.client.force_login(self.viewer_same_scope)
        response = self.client.get(
            reverse("projects:report_detail", args=[agreement_config.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(agreement_config.normalized_report_variant(), "agreement")
        self.assertEqual(response.context["report_variant"], "agreement")

    def test_unknown_variant_falls_back_to_base_layout(self):
        custom_config = ProjectReportConfig.objects.create(
            project=self.project,
            name="Reporte Futuro",
            report_variant="Panel Ejecutivo Especial",
            report_dataset=self.summary_dataset_a,
            curve_program_dataset=self.program_dataset_a,
            curve_executed_dataset=self.executed_dataset_a,
            is_active=True,
        )
        Membership.objects.create(
            user=self.viewer_same_scope,
            entity=self.entity_a,
            role="VIEWER",
        )

        self.client.force_login(self.viewer_same_scope)
        response = self.client.get(
            reverse("projects:report_detail", args=[custom_config.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["configured_report_variant"], "panel-ejecutivo-especial")
        self.assertEqual(response.context["detected_report_variant"], "panel-ejecutivo-especial")
        self.assertEqual(response.context["report_variant"], "project")

    def test_report_detail_ignores_legacy_instances_outside_project_scope(self):
        legacy_config = ProjectReportConfig.objects.create(
            project=self.project,
            name="Reporte Legacy",
            report_dataset=self.summary_dataset_b,
            curve_program_dataset=self.program_dataset_a,
            curve_executed_dataset=self.executed_dataset_a,
            is_active=True,
        )
        DatasetInstance.objects.create(
            dataset_type=self.summary_dataset_b,
            entity=self.entity_b,
            period=date(2026, 2, 28),
            state=DatasetInstance.STATE_DRAFT,
        )
        Membership.objects.create(
            user=self.viewer_same_scope,
            entity=self.entity_a,
            role="VIEWER",
        )

        self.client.force_login(self.viewer_same_scope)
        response = self.client.get(
            reverse("projects:report_detail", args=[legacy_config.id]),
            {"source": "draft"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["summary_instance"])
