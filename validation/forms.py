from django import forms

from .models import ValidationAction


class ValidationDecisionForm(forms.ModelForm):
    class Meta:
        model = ValidationAction
        fields = ["decision", "comment"]
        widgets = {
            "decision": forms.Select(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                    "rows": 3,
                }
            ),
        }

