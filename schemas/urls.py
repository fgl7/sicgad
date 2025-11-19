from django.urls import path

from . import views

app_name = "schemas"

urlpatterns = [
    path("", views.schema_list, name="schema_list"),
    path("new/", views.schema_edit, name="schema_create"),
    path("certification/new/", views.certification_schema_create, name="certification_schema_create"),
    path("<int:pk>/", views.schema_detail, name="schema_detail"),
    path("<int:pk>/edit/", views.schema_edit, name="schema_edit"),
]
