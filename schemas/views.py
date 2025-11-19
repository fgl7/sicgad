from django.db.models import Max
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import admin_required

from .models import ColumnDef, DatasetType
from .forms import DatasetTypeForm, ColumnDefForm, CertificationSchemaForm


def schema_list(request):
    datasets = DatasetType.objects.select_related("plant").order_by("plant__code", "name", "-version")
    return render(request, "schemas/schema_list.html", {"datasets": datasets})


def schema_detail(request, pk):
    dataset = get_object_or_404(DatasetType.objects.select_related("plant"), pk=pk)
    columns = dataset.columns.order_by("display_order", "name")
    return render(
        request,
        "schemas/schema_detail.html",
        {"dataset": dataset, "columns": columns},
    )


def schema_edit(request, pk=None):
    if pk:
        dataset = get_object_or_404(DatasetType, pk=pk)
    else:
        dataset = None

    DatasetColumnFormSet = inlineformset_factory(
        DatasetType,
        ColumnDef,
        form=ColumnDefForm,
        extra=1,
        can_delete=True,
    )

    if request.method == "POST":
        form = DatasetTypeForm(request.POST, instance=dataset)
        formset = DatasetColumnFormSet(request.POST, instance=dataset)
        if form.is_valid() and formset.is_valid():
            dataset = form.save()
            formset.instance = dataset
            formset.save()
            return redirect(reverse("schemas:schema_detail", args=[dataset.pk]))
    else:
        form = DatasetTypeForm(instance=dataset)
        formset = DatasetColumnFormSet(instance=dataset)

    return render(
        request,
        "schemas/schema_edit.html",
        {
            "form": form,
            "formset": formset,
            "dataset": dataset,
        },
    )


@admin_required
def certification_schema_create(request):
    if request.method == "POST":
        form = CertificationSchemaForm(request.POST)
        if form.is_valid():
            source = form.cleaned_data["source_dataset"]
            name = form.cleaned_data["name"]
            columns = form.cleaned_data["columns"]

            current_max = (
                DatasetType.objects.filter(plant=source.plant, name=name)
                .aggregate(max_version=Max("version"))
            )
            next_version = (current_max["max_version"] or 0) + 1

            dataset = DatasetType.objects.create(
                plant=source.plant,
                name=name,
                version=next_version,
                validation_frequency=DatasetType.MONTHLY,
                is_certification=True,
                is_active=True,
            )

            for col in columns:
                ColumnDef.objects.create(
                    dataset_type=dataset,
                    name=col.name,
                    label=col.label,
                    data_type=col.data_type,
                    required=col.required,
                    min_value=col.min_value,
                    max_value=col.max_value,
                    regex=col.regex,
                    choices_raw=col.choices_raw,
                    unit=col.unit,
                    axis_role=col.axis_role,
                    default_agg=col.default_agg,
                    is_primary_kpi=col.is_primary_kpi,
                    display_order=col.display_order,
                    is_active=col.is_active,
                )

            return redirect(reverse("schemas:schema_detail", args=[dataset.pk]))
    else:
        form = CertificationSchemaForm()

    return render(
        request,
        "schemas/certification_schema_create.html",
        {
            "form": form,
        },
    )
