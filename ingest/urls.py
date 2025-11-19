from django.urls import path

from . import views

app_name = "ingest"

urlpatterns = [
    path("upload/", views.upload, name="upload"),
    path("history/", views.upload_history, name="upload_history"),
]

