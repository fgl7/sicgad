from django import forms

from structure.models import Category, Entity
from schemas.models import DatasetType
from .models import Project, ProjectReportConfig


class ProjectForm(forms.ModelForm):
    change_justification = forms.CharField(
        label="Justificacion del cambio",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                "rows": 2,
                "placeholder": "Describe la razon del cambio en datos estaticos.",
            }
        ),
    )

    STATIC_FIELDS = {
        "name",
        "code",
        "description",
        "executor",
        "location",
        "start_date",
        "end_date",
        "budget_mmbs",
        "entities",
        "category",
        "is_active",
    }

    class Meta:
        model = Project
        fields = [
            "name",
            "code",
            "category",
            "description",
            "executor",
            "location",
            "start_date",
            "end_date",
            "budget_mmbs",
            "entities",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "code": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                    "rows": 2,
                }
            ),
            "executor": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "start_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "budget_mmbs": forms.NumberInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "entities": forms.SelectMultiple(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                    "size": 3,
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-slate-700",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        allow_activation = kwargs.pop("allow_activation", True)
        allowed_entity_ids = kwargs.pop("allowed_entity_ids", None)
        super().__init__(*args, **kwargs)
        entity_qs = Entity.objects.filter(is_active=True).order_by("code", "name")
        if allowed_entity_ids is not None:
            entity_qs = entity_qs.filter(id__in=allowed_entity_ids)
        self.fields["category"].required = True
        self.fields["entities"].required = True
        self.fields["entities"].error_messages["required"] = (
            "Debe seleccionar al menos una entidad operativa."
        )
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by(
            "subsector__sector__name",
            "subsector__name",
            "name",
        )
        category_id = None
        if self.data.get("category"):
            category_id = self.data.get("category")
        elif self.initial.get("category"):
            category_id = self.initial.get("category")
        elif getattr(self.instance, "category_id", None):
            category_id = self.instance.category_id
        if category_id:
            entity_qs = entity_qs.filter(category_id=category_id)
        self.fields["entities"].queryset = entity_qs
        self.user = user
        if not getattr(self.instance, "pk", None):
            self.fields.pop("change_justification", None)
        if not allow_activation:
            self.fields.pop("is_active", None)

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        entities = cleaned.get("entities")
        if getattr(self.instance, "pk", None):
            changed = [field for field in self.changed_data if field in self.STATIC_FIELDS]
            if changed:
                justification = (cleaned.get("change_justification") or "").strip()
                if not justification:
                    self.add_error(
                        "change_justification",
                        "Debe indicar una justificacion para cambios en datos estaticos.",
                    )
        if category and entities:
            invalid_entities = [
                entity
                for entity in entities
                if entity.category_id != category.id
            ]
            if invalid_entities:
                self.add_error(
                    "entities",
                    "Todas las entidades seleccionadas deben pertenecer a la categoria del proyecto.",
                )
        return cleaned


class ProjectReportConfigForm(forms.ModelForm):
    class Meta:
        model = ProjectReportConfig
        fields = [
            "project",
            "name",
            "report_variant",
            "report_dataset",
            "curve_program_dataset",
            "curve_executed_dataset",
            "is_active",
            "notes",
        ]
        widgets = {
            "project": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "report_variant": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                    "placeholder": "auto | project | agreement | otra-variante",
                    "spellcheck": "false",
                }
            ),
            "report_dataset": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "curve_program_dataset": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "curve_executed_dataset": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                    "rows": 3,
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-slate-700",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            is_active=True,
            workflow_status=Project.STATUS_APPROVED,
        ).order_by("name")
        self.fields["report_variant"].help_text = (
            "Use 'auto' para deteccion automatica, o defina un slug como "
            "'project', 'agreement' u otra variante futura."
        )

        project_id = None
        if self.data.get("project"):
            project_id = self.data.get("project")
        elif self.initial.get("project"):
            project_id = self.initial.get("project")
        elif getattr(self.instance, "project_id", None):
            project_id = self.instance.project_id

        dataset_qs = DatasetType.objects.filter(
            status=DatasetType.STATUS_APPROVED,
            is_active=True,
        ).select_related("entity").order_by("entity__name", "name", "-version")

        if project_id:
            project = Project.objects.filter(pk=project_id).select_related("category").first()
            if project and project.category_id:
                project_entity_ids = list(project.entities.values_list("id", flat=True))
                if project_entity_ids:
                    dataset_qs = dataset_qs.filter(
                        entity__category_id=project.category_id,
                        entity_id__in=project_entity_ids,
                    )
                else:
                    dataset_qs = dataset_qs.none()
            else:
                dataset_qs = dataset_qs.none()
        else:
            dataset_qs = dataset_qs.none()

        self.fields["report_dataset"].queryset = dataset_qs
        self.fields["curve_program_dataset"].queryset = dataset_qs
        self.fields["curve_executed_dataset"].queryset = dataset_qs.filter(
            validation_frequency__in=[DatasetType.WEEKLY, DatasetType.MONTHLY]
        )

    def clean_report_variant(self):
        value = (self.cleaned_data.get("report_variant") or "").strip()
        if not value:
            return ProjectReportConfig.VARIANT_AUTO
        self.instance.report_variant = value
        return self.instance.normalized_report_variant()
