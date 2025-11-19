from django import forms

from .models import ColumnDef, DatasetType


class DatasetTypeForm(forms.ModelForm):
    class Meta:
        model = DatasetType
        fields = ["plant", "name", "version", "validation_frequency", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm"}),
            "version": forms.NumberInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm"}),
            "validation_frequency": forms.Select(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm"}),
            "plant": forms.Select(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm"}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-slate-700"}),
        }


class ColumnDefForm(forms.ModelForm):
    class Meta:
        model = ColumnDef
        exclude = ["dataset_type", "created_at", "updated_at"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "label": forms.TextInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "data_type": forms.Select(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "required": forms.CheckboxInput(attrs={"class": "rounded border-slate-700"}),
            "min_value": forms.NumberInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "max_value": forms.NumberInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "regex": forms.TextInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "choices_raw": forms.Textarea(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs", "rows": 2}),
            "unit": forms.TextInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "axis_role": forms.Select(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "default_agg": forms.Select(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "is_primary_kpi": forms.CheckboxInput(attrs={"class": "rounded border-slate-700"}),
            "display_order": forms.NumberInput(attrs={"class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-slate-700"}),
        }


class CertificationSchemaForm(forms.Form):
    source_dataset = forms.ModelChoiceField(
        queryset=DatasetType.objects.none(),
        label="Dataset base (diario)",
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
    )
    name = forms.CharField(
        label="Nombre del esquema de certificaci��n",
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
    )
    columns = forms.ModelMultipleChoiceField(
        queryset=ColumnDef.objects.none(),
        label="Campos a incluir en la certificaci��n",
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "space-y-1 text-xs",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["source_dataset"].queryset = (
            DatasetType.objects.filter(
                validation_frequency=DatasetType.DAILY,
                is_active=True,
                is_certification=False,
            )
            .select_related("plant")
            .order_by("plant__code", "name", "-version")
        )

        source = None
        if "source_dataset" in self.data:
            try:
                source_id = int(self.data.get("source_dataset"))
                source = DatasetType.objects.get(pk=source_id)
            except (TypeError, ValueError, DatasetType.DoesNotExist):
                source = None
        else:
            initial_source = self.initial.get("source_dataset")
            if isinstance(initial_source, DatasetType):
                source = initial_source

        if source is not None:
            self.fields["columns"].queryset = ColumnDef.objects.filter(
                dataset_type=source,
                is_active=True,
            ).order_by("display_order", "name")

            if not self.initial.get("name") and not self.data.get("name"):
                self.fields["name"].initial = f"{source.name} - Certificaci��n mensual"
        else:
            self.fields["columns"].queryset = ColumnDef.objects.none()
