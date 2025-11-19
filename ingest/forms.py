from django import forms

from .models import DatasetInstance
from schemas.models import DatasetType


class DatasetInstanceUploadForm(forms.ModelForm):
    dataset_type = forms.ModelChoiceField(
        queryset=DatasetType.objects.select_related("plant").all(),
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

