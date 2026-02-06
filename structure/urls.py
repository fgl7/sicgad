from django.urls import path

from . import views

app_name = "structure"

urlpatterns = [
    path("levels/", views.manage_levels, name="manage_levels"),
]
