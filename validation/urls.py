from django.urls import path

from . import views

app_name = "validation"

urlpatterns = [
    path("inbox/", views.inbox, name="inbox"),
    path("admin/", views.admin_overview, name="admin_overview"),
    path(
        "historical/<int:batch_id>/approve/",
        views.approve_historical_batch,
        name="approve_historical_batch",
    ),
    path(
        "historical/<int:batch_id>/approve/progress/",
        views.approve_historical_batch_progress,
        name="approve_historical_batch_progress",
    ),
    path("<int:pk>/", views.detail, name="detail"),
]
