from django import forms
from django.forms import formset_factory

from schemas.models import DatasetType, ColumnDef
from plants.models import Plant
from .models import DatasetInstance


class DatasetInstanceUploadForm(forms.ModelForm):
    dataset_type = forms.ModelChoiceField(
        queryset=DatasetType.objects.select_related("plant")
        .filter(is_active=True, status=DatasetType.STATUS_APPROVED),
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
        label="Tipo de dataset",
    )

    def __init__(self, *args, loader_plant: Plant | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if loader_plant:
            # Restringir la planta al valor asignado al cargador
            self.fields["plant"].queryset = Plant.objects.filter(pk=loader_plant.pk)
            self.fields["plant"].initial = loader_plant
            # Restringir los datasets a esa planta
            self.fields["dataset_type"].queryset = (
                DatasetType.objects.select_related("plant")
                .filter(
                    plant=loader_plant,
                    is_active=True,
                    status=DatasetType.STATUS_APPROVED,
                )
            )

    class Meta:
        model = DatasetInstance
        fields = ["dataset_type", "plant", "period", "raw_file"]
        widgets = {
            "plant": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
                }
            ),
            "period": forms.DateInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
                    "type": "date",
                }
            ),
            "raw_file": forms.ClearableFileInput(
                attrs={
                    "class": "w-full text-sm text-slate-200",
                }
            ),
        }


class DatasetInstanceEditForm(forms.ModelForm):
    class Meta:
        model = DatasetInstance
        fields = ["raw_file"]
        widgets = {
            # Usamos FileInput simple para evitar el checkbox "Clear"
            # y el texto "Currently", ya que el flujo siempre es
            # reemplazar el archivo anterior por uno corregido.
            "raw_file": forms.FileInput(
                attrs={
                    "class": "w-full text-sm text-slate-200",
                }
            ),
        }


class ManualDatasetForm(forms.ModelForm):
    dataset_type = forms.ModelChoiceField(
        queryset=DatasetType.objects.select_related("plant")
        .filter(is_active=True, status=DatasetType.STATUS_APPROVED),
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
        label="Tipo de dataset",
    )

    class Meta:
        model = DatasetInstance
        fields = ["dataset_type", "plant", "period"]
        widgets = {
            "plant": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
                }
            ),
            "period": forms.DateInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
                    "type": "date",
                }
            ),
        }

    def __init__(self, *args, loader_plant: Plant | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if loader_plant:
            self.fields["plant"].queryset = Plant.objects.filter(pk=loader_plant.pk)
            self.fields["plant"].initial = loader_plant
            self.fields["dataset_type"].queryset = (
                DatasetType.objects.select_related("plant")
                .filter(
                    plant=loader_plant,
                    is_active=True,
                    status=DatasetType.STATUS_APPROVED,
                )
            )


def build_manual_row_form(dataset: DatasetType):
    columns = list(
        dataset.columns.filter(is_active=True).order_by("display_order", "name")
    )
    fields = {}
    for column in columns:
        label = column.label or column.name
        field_name = column.name
        required = column.required
        common_attrs = {
            "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs"
        }
        if column.data_type in ("INTEGER", "FLOAT"):
            fields[field_name] = forms.FloatField(
                required=required,
                label=label,
                widget=forms.NumberInput(attrs=common_attrs),
            )
        elif column.data_type == "DATE":
            fields[field_name] = forms.DateField(
                required=required,
                label=label,
                widget=forms.DateInput(attrs={**common_attrs, "type": "date"}),
            )
        elif column.data_type == "BOOLEAN":
            fields[field_name] = forms.BooleanField(
                required=False,
                label=label,
                widget=forms.CheckboxInput(
                    attrs={"class": "rounded border-slate-700 size-4"}
                ),
            )
        else:
            fields[field_name] = forms.CharField(
                required=required,
                label=label,
                widget=forms.TextInput(attrs=common_attrs),
            )

    ManualRowForm = type("ManualRowForm", (forms.Form,), fields)
    ManualRowForm._columns = columns
    return ManualRowForm, columns
