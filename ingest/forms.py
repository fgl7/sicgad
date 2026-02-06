from django import forms
from django.db.models import Exists, OuterRef, Q
from django.forms import formset_factory

from schemas.models import DatasetType, ColumnDef
from structure.models import Entity
from .models import DatasetInstance
from .utils import month_number_from_label


def _exclude_one_time_with_instance(qs):
    inst_qs = DatasetInstance.objects.filter(dataset_type=OuterRef("pk")).filter(
        entity_id=OuterRef("entity_id"),
        entity_id__isnull=False,
    )
    return qs.annotate(has_instance=Exists(inst_qs)).exclude(is_one_time=True, has_instance=True)


def _has_one_time_instance(dataset: DatasetType | None) -> bool:
    if not dataset or not dataset.is_one_time:
        return False
    qs = DatasetInstance.objects.filter(dataset_type=dataset)
    if dataset.entity_id:
        qs = qs.filter(entity_id=dataset.entity_id)
    return qs.exists()


class DatasetInstanceUploadForm(forms.ModelForm):
    dataset_type = forms.ModelChoiceField(
        queryset=DatasetType.objects.select_related("entity")
        .filter(is_active=True, status=DatasetType.STATUS_APPROVED),
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
        label="Tipo de dataset",
    )

    def __init__(
        self,
        *args,
        loader_entities: list[int] | None = None,
        loader_plants: list[int] | None = None,
        loader_projects: list[int] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        entity_ids = loader_entities if loader_entities is not None else []
        if loader_entities is not None:
            self.fields["entity"].queryset = Entity.objects.filter(
                id__in=entity_ids,
                is_active=True,
            )
            qs = DatasetType.objects.select_related("entity").filter(
                is_active=True,
                status=DatasetType.STATUS_APPROVED,
                entity_id__in=entity_ids,
            )
            self.fields["dataset_type"].queryset = qs

        self.fields["dataset_type"].queryset = _exclude_one_time_with_instance(
            self.fields["dataset_type"].queryset
        )

    class Meta:
        model = DatasetInstance
        fields = ["dataset_type", "entity", "period", "raw_file"]
        widgets = {
            "entity": forms.Select(
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

    def clean(self):
        cleaned = super().clean()
        dataset = cleaned.get("dataset_type")
        if not dataset:
            return cleaned

        cleaned["entity"] = dataset.entity

        if _has_one_time_instance(dataset):
            self.add_error(
                "dataset_type",
                "Este esquema es de carga unica y ya tiene una carga registrada.",
            )
        return cleaned


class HistoricalDatasetUploadForm(forms.Form):
    dataset_type = forms.ModelChoiceField(
        queryset=DatasetType.objects.select_related("entity").filter(
            is_active=True,
            is_certification=False,
            validation_frequency=DatasetType.DAILY,
            status=DatasetType.STATUS_APPROVED,
        ),
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
        label="Tipo de dataset",
    )
    entity = forms.ModelChoiceField(
        queryset=Entity.objects.filter(is_active=True),
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
        label="Entidad",
    )
    date_column_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
                "placeholder": "Ej: fecha, date, periodo (opcional)",
            }
        ),
        label="Columna fecha (encabezado, opcional)",
        help_text="Si lo dejas vacío, se usa la primera columna DATE del esquema (por name o label).",
    )
    raw_file = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={
                "class": "w-full text-sm text-slate-200",
            }
        ),
        label="Archivo",
    )

    def __init__(
        self,
        *args,
        loader_entities: list[int] | None = None,
        loader_plants: list[int] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if loader_entities is not None:
            self.fields["entity"].queryset = Entity.objects.filter(id__in=loader_entities, is_active=True)
            self.fields["dataset_type"].queryset = (
                DatasetType.objects.select_related("entity")
                .filter(
                    entity_id__in=loader_entities,
                    is_active=True,
                    is_certification=False,
                    validation_frequency=DatasetType.DAILY,
                    status=DatasetType.STATUS_APPROVED,
                )
            )


class DatasetInstanceEditForm(forms.ModelForm):
    justification = forms.CharField(
        label="Justificacion del cambio",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                "rows": 3,
                "placeholder": "Describe la razon de la actualizacion.",
            }
        ),
    )

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

    def clean(self):
        cleaned = super().clean()
        dataset = getattr(self.instance, "dataset_type", None)
        if dataset and dataset.is_one_time:
            justification = (cleaned.get("justification") or "").strip()
            if not justification:
                self.add_error(
                    "justification",
                    "Debe indicar una justificacion para actualizar este esquema de carga unica.",
                )
        return cleaned


class ManualDatasetForm(forms.ModelForm):
    dataset_type = forms.ModelChoiceField(
        queryset=DatasetType.objects.select_related("entity")
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
        fields = ["dataset_type", "entity", "period"]
        widgets = {
            "entity": forms.Select(
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

    def __init__(
        self,
        *args,
        loader_entities: list[int] | None = None,
        loader_plants: list[int] | None = None,
        loader_projects: list[int] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if loader_entities is not None:
            entity_ids = loader_entities or []
            self.fields["entity"].queryset = Entity.objects.filter(id__in=entity_ids, is_active=True)
            qs = DatasetType.objects.select_related("entity").filter(
                is_active=True,
                status=DatasetType.STATUS_APPROVED,
                entity_id__in=entity_ids,
            )
            self.fields["dataset_type"].queryset = qs

        self.fields["dataset_type"].queryset = _exclude_one_time_with_instance(
            self.fields["dataset_type"].queryset
        )

    def clean(self):
        cleaned = super().clean()
        dataset = cleaned.get("dataset_type")
        if not dataset:
            return cleaned

        cleaned["entity"] = dataset.entity

        if _has_one_time_instance(dataset):
            self.add_error(
                "dataset_type",
                "Este esquema es de carga unica y ya tiene una carga registrada.",
            )
        return cleaned


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
        month_number = month_number_from_label(column.name) or month_number_from_label(
            column.label
        )
        if month_number:
            common_attrs["data-month-number"] = str(month_number)
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
                widget=forms.DateInput(
                    attrs={
                        **common_attrs,
                        "type": "date",
                        "data-manual-date-field": "true",
                    }
                ),
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


class CertificationJustificationForm(forms.Form):
    justification = forms.CharField(
        label="Justificación",
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                "rows": 4,
                "placeholder": "Describe por qué se ajustan los valores consolidados.",
            }
        ),
    )
