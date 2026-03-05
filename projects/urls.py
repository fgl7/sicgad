from django.urls import path

from . import views


app_name = "projects"


urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("create/", views.project_create, name="project_create"),
    path("<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("<int:pk>/submit/", views.project_submit, name="project_submit"),
    path("<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("<int:pk>/<str:decision>/", views.project_review, name="project_review"),
    path("reports/", views.report_list, name="report_list"),
    path("reports/<int:config_id>/", views.report_detail, name="report_detail"),
    path("reports/configs/", views.report_config_list, name="report_config_list"),
    path("reports/configs/new/", views.report_config_create, name="report_config_create"),
    path(
        "reports/configs/<int:config_id>/edit/",
        views.report_config_edit,
        name="report_config_edit",
    ),
    path(
        "reports/configs/<int:config_id>/delete/",
        views.report_config_delete,
        name="report_config_delete",
    ),
]
