from django import forms

from structure.models import Category
from .models import Plant


class PlantForm(forms.ModelForm):
    class Meta:
        model = Plant
        fields = ["code", "name", "category", "description", "is_active"]
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "name": forms.TextInput(
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
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-slate-700",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = True
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by(
            "subsector__sector__name",
            "subsector__name",
            "name",
        )

