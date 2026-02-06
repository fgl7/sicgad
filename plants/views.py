from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_role_required

from .forms import PlantForm
from .models import Plant


@admin_role_required
def plant_list(request):
    plants = Plant.objects.all().order_by("code")
    return render(request, "plants/plant_list.html", {"plants": plants})


@admin_role_required
def plant_create(request):
    if request.method == "POST":
        form = PlantForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("plants:plant_list")
    else:
        form = PlantForm()
    return render(request, "plants/plant_form.html", {"form": form, "plant": None})


@admin_role_required
def plant_edit(request, pk):
    plant = get_object_or_404(Plant, pk=pk)
    if request.method == "POST":
        form = PlantForm(request.POST, instance=plant)
        if form.is_valid():
            form.save()
            return redirect("plants:plant_list")
    else:
        form = PlantForm(instance=plant)
    return render(request, "plants/plant_form.html", {"form": form, "plant": plant})


@admin_role_required
def plant_delete(request, pk):
    plant = get_object_or_404(Plant, pk=pk)
    if request.method == "POST":
        plant.delete()
        return redirect("plants:plant_list")

    return render(
        request,
        "plants/plant_confirm_delete.html",
        {
            "plant": plant,
        },
    )
