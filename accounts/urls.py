from django.urls import path

from .views import (
    ForcePasswordChangeView,
    admin_user_create,
    admin_user_delete,
    admin_user_edit,
    admin_user_list,
    institution_create,
    institution_delete,
    institution_edit,
    institution_list,
)

app_name = "accounts"

urlpatterns = [
    path(
        "password-change/",
        ForcePasswordChangeView.as_view(),
        name="force_password_change",
    ),
    path("users/", admin_user_list, name="admin_user_list"),
    path("users/new/", admin_user_create, name="admin_user_create"),
    path("users/<int:user_id>/edit/", admin_user_edit, name="admin_user_edit"),
    path("users/<int:user_id>/delete/", admin_user_delete, name="admin_user_delete"),
    path("institutions/", institution_list, name="institution_list"),
    path("institutions/new/", institution_create, name="institution_create"),
    path("institutions/<int:institution_id>/edit/", institution_edit, name="institution_edit"),
    path("institutions/<int:institution_id>/delete/", institution_delete, name="institution_delete"),
]
