from django import forms

from plants.models import Plant
from structure.models import Category
from schemas.models import DatasetType
from .models import Project, ProjectReportConfig


class ProjectForm(forms.ModelForm):
    change_justification = forms.CharField(
        label="Justificacion del cambio",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                "rows": 3,
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
        "plants",
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
            "plants",
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
                    "rows": 3,
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
            "plants": forms.SelectMultiple(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                    "size": 4,
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
        self.fields["plants"].queryset = Plant.objects.all().order_by("code")
        self.fields["category"].required = True
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by(
            "subsector__sector__name",
            "subsector__name",
            "name",
        )
        if not getattr(self.instance, "pk", None):
            self.fields.pop("change_justification", None)

    def clean(self):
        cleaned = super().clean()
        if getattr(self.instance, "pk", None):
            changed = [field for field in self.changed_data if field in self.STATIC_FIELDS]
            if changed:
                justification = (cleaned.get("change_justification") or "").strip()
                if not justification:
                    self.add_error(
                        "change_justification",
                        "Debe indicar una justificacion para cambios en datos estaticos.",
                    )
        return cleaned


class ProjectReportConfigForm(forms.ModelForm):
    class Meta:
        model = ProjectReportConfig
        fields = [
            "project",
            "name",
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
        self.fields["project"].queryset = Project.objects.filter(is_active=True).order_by("name")

        project_id = None
        if self.data.get("project"):
            project_id = self.data.get("project")
        elif self.initial.get("project"):
            project_id = self.initial.get("project")
        elif getattr(self.instance, "project_id", None):
            project_id = self.instance.project_id

        dataset_qs = DatasetType.objects.filter(
            project__isnull=False,
            status=DatasetType.STATUS_APPROVED,
        ).order_by("name", "-version")

        if project_id:
            dataset_qs = dataset_qs.filter(project_id=project_id)

        self.fields["report_dataset"].queryset = dataset_qs
        self.fields["curve_program_dataset"].queryset = dataset_qs
        self.fields["curve_executed_dataset"].queryset = dataset_qs.filter(
            validation_frequency__in=[DatasetType.WEEKLY, DatasetType.MONTHLY]
        )
