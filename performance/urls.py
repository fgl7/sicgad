from django.urls import path

from . import views

app_name = "performance"

urlpatterns = [
    path("pcs/formula-1/", views.pcs_formula_1, name="pcs_formula_1"),
]

