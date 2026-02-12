from django import forms

from .models import ColumnDef, DatasetType


class DatasetTypeForm(forms.ModelForm):
    def __init__(
        self,
        *args,
        allowed_entities_qs=None,
        allow_set_active: bool = True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if allowed_entities_qs is not None:
            self.fields["entity"].queryset = allowed_entities_qs
        if not allow_set_active:
            self.fields["is_active"].disabled = True

    class Meta:
        model = DatasetType
        fields = [
            "entity",
            "name",
            "version",
            "validation_frequency",
            "is_active",
            "is_one_time",
        ]
        widgets = {
            "entity": forms.Select(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-white/10 text-sm text-slate-100 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-white/10 text-sm text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "version": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-white/10 text-sm text-slate-100 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "validation_frequency": forms.Select(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-white/10 text-sm text-slate-100 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-white/20 bg-slate-900 text-sky-400 focus:ring-sky-500/40",
                }
            ),
            "is_one_time": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-white/20 bg-slate-900 text-sky-400 focus:ring-sky-500/40",
                }
            ),
        }


class ColumnDefForm(forms.ModelForm):
    class Meta:
        model = ColumnDef
        exclude = ["dataset_type", "created_at", "updated_at"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full h-10 px-2.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "label": forms.TextInput(
                attrs={
                    "class": "w-full h-10 px-2.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "data_type": forms.Select(
                attrs={
                    "class": "w-full h-11 px-2.5 py-0 rounded-xl bg-slate-900/80 border border-white/10 text-sm leading-5 text-slate-100 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "required": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-white/20 bg-slate-900 text-sky-400 focus:ring-sky-500/40",
                }
            ),
            "min_value": forms.NumberInput(
                attrs={
                    "class": "w-full h-10 px-2.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "max_value": forms.NumberInput(
                attrs={
                    "class": "w-full h-10 px-2.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "regex": forms.TextInput(
                attrs={
                    "class": "w-full h-10 px-2.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "choices_raw": forms.Textarea(
                attrs={
                    "class": "w-full h-10 px-2.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                    "rows": 2,
                }
            ),
            "unit": forms.TextInput(
                attrs={
                    "class": "w-full h-10 px-2.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "axis_role": forms.Select(
                attrs={
                    "class": "w-full h-11 px-2.5 py-0 rounded-xl bg-slate-900/80 border border-white/10 text-sm leading-5 text-slate-100 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "default_agg": forms.Select(
                attrs={
                    "class": "w-full h-11 px-2.5 py-0 rounded-xl bg-slate-900/80 border border-white/10 text-sm leading-5 text-slate-100 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "is_primary_kpi": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-white/20 bg-slate-900 text-sky-400 focus:ring-sky-500/40",
                }
            ),
            "display_order": forms.NumberInput(
                attrs={
                    "class": "w-full h-11 px-2.5 py-0 rounded-xl bg-slate-900/80 border border-white/10 text-sm leading-5 text-slate-100 focus:ring-2 focus:ring-sky-500/40 focus:border-sky-400/60",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-white/20 bg-slate-900 text-sky-400 focus:ring-sky-500/40",
                }
            ),
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
        label="Nombre del esquema de certificacion",
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-sm",
            }
        ),
    )
    columns = forms.ModelMultipleChoiceField(
        queryset=ColumnDef.objects.none(),
        label="Campos a incluir en la certificacion",
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
            .select_related("entity")
            .order_by("entity__name", "name", "-version")
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
            elif initial_source:
                try:
                    source = DatasetType.objects.get(pk=initial_source)
                except (TypeError, ValueError, DatasetType.DoesNotExist):
                    source = None

        if source is not None:
            self.fields["columns"].queryset = ColumnDef.objects.filter(
                dataset_type=source,
                is_active=True,
            ).order_by("display_order", "name")

            if not self.initial.get("name") and not self.data.get("name"):
                self.fields["name"].initial = f"{source.name} - Certificacion mensual"
        else:
            self.fields["columns"].queryset = ColumnDef.objects.none()
