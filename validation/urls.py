from django.urls import path

from . import views

app_name = "validation"

urlpatterns = [
    path("inbox/", views.inbox, name="inbox"),
    path("<int:pk>/", views.detail, name="detail"),
]

