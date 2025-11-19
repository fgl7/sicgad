from django.urls import path

from . import views

app_name = "plants"

urlpatterns = [
    path("", views.plant_list, name="plant_list"),
    path("new/", views.plant_create, name="plant_create"),
    path("<int:pk>/edit/", views.plant_edit, name="plant_edit"),
    path("<int:pk>/delete/", views.plant_delete, name="plant_delete"),
]

