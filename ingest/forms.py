from django import forms

from schemas.models import DatasetType
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
