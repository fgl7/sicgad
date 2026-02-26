from django.urls import path

from . import views

app_name = "performance"

urlpatterns = [
    path("kcl/formula-9/", views.kcl_formula_9, name="kcl_formula_9"),
    path("formulas/", views.formula_builder, name="formulas"),
    path("formulas/<int:formula_id>/approve/progress/", views.formula_approve_progress, name="formula_approve_progress"),
]
