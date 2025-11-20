from django.urls import path

from . import views

app_name = "schemas"

urlpatterns = [
    path("", views.schema_list, name="schema_list"),
    path("new/", views.schema_edit, name="schema_create"),
    path("<slug:slug>/submit/", views.schema_submit_for_approval, name="schema_submit"),
    path("<slug:slug>/approve/", views.schema_approve, name="schema_approve"),
    path("<slug:slug>/reject/", views.schema_reject, name="schema_reject"),
    path("certification/new/", views.certification_schema_create, name="certification_schema_create"),
    path("<slug:slug>/", views.schema_detail, name="schema_detail"),
    path("<slug:slug>/edit/", views.schema_edit, name="schema_edit"),
]
