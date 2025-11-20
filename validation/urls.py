from django.urls import path

from . import views

app_name = "validation"

urlpatterns = [
    path("inbox/", views.inbox, name="inbox"),
    path("admin/", views.admin_overview, name="admin_overview"),
    path("<int:pk>/", views.detail, name="detail"),
]
