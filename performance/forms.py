from __future__ import annotations

from dataclasses import dataclass

from django import forms

from performance.models import PerformanceVariableMapping
from schemas.models import ColumnDef


@dataclass(frozen=True)
class ColumnOption:
    id: int
    label: str


class VariableMappingForm(forms.Form):
    """
    Formulario simple por variable-stage para mapear a una ColumnDef (con dataset implícito).
    """

    column_id = forms.ChoiceField(choices=(), required=False)
    aggregation = forms.ChoiceField(choices=PerformanceVariableMapping.AGG_CHOICES, required=True)
    offset_months = forms.IntegerField(min_value=0, max_value=60, required=True)

    def __init__(self, *args, column_options: list[ColumnOption], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["column_id"].choices = [("", "— Seleccionar —")] + [
            (str(o.id), o.label) for o in column_options
        ]
        base_class = "w-full px-3 py-2 rounded-md bg-slate-900 border border-slate-800 text-slate-100 text-sm"
        self.fields["column_id"].widget.attrs.update({"class": base_class})
        self.fields["aggregation"].widget.attrs.update({"class": base_class})
        self.fields["offset_months"].widget.attrs.update({"class": base_class, "inputmode": "numeric"})

    def clean_column_id(self):
        raw = self.cleaned_data.get("column_id") or ""
        raw = str(raw).strip()
        if raw == "":
            return None
        try:
            return int(raw)
        except ValueError as exc:
            raise forms.ValidationError("Valor inválido") from exc

    def clean_offset_months(self):
        val = self.cleaned_data.get("offset_months")
        if val is None:
            return 0
        return int(val)

    def resolve_column(self) -> ColumnDef | None:
        col_id = self.cleaned_data.get("column_id")
        if not col_id:
            return None
        return ColumnDef.objects.filter(id=col_id).select_related("dataset_type", "dataset_type__entity").first()
