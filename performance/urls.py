from django.urls import path

from . import views

app_name = "performance"

urlpatterns = [
    path("kcl/formula-9/", views.kcl_formula_9, name="kcl_formula_9"),
]
