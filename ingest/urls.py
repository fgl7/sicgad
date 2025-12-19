from django.urls import path

from . import views

app_name = "ingest"

urlpatterns = [
    path("upload/", views.upload, name="upload"),
    path("upload/historical/", views.upload_historical, name="upload_historical"),
    path("upload/manual/", views.upload_manual, name="upload_manual"),
    path("dataset-has-data/", views.dataset_has_data, name="dataset_has_data"),
    path(
        "historical/<int:batch_id>/submit/",
        views.submit_historical_batch,
        name="submit_historical_batch",
    ),
    path("template/", views.download_template, name="download_template"),
    path("history/", views.upload_history, name="upload_history"),
    path("instance/<int:pk>/", views.instance_detail, name="instance_detail"),
    path(
        "instance/<int:pk>/certification-review/",
        views.certification_review,
        name="certification_review",
    ),
    path("instance/<int:pk>/submit/", views.submit_instance, name="submit_instance"),
    path("instance/<int:pk>/edit/", views.edit_instance, name="edit_instance"),
    path("instance/<int:pk>/delete/", views.delete_instance, name="delete_instance"),
]
