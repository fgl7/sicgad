from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordChangeView
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from audit.utils import record_action
from structure.models import Entity

from .decorators import admin_required
from .forms import AdminUserCreateForm, InstitutionForm
from .models import AccountProfile, Institution, Membership


User = get_user_model()


class ForcePasswordChangeView(PasswordChangeView):
    template_name = "accounts/force_password_change.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        profile, _ = AccountProfile.objects.get_or_create(user=self.request.user)
        profile.must_change_password = False
        profile.save()
        return response


@admin_required
def admin_user_list(request):
    role = request.GET.get("role") or ""
    entity_id = request.GET.get("entity") or ""
    institution = request.GET.get("institution") or ""

    users_qs = User.objects.filter(is_superuser=False).exclude(pk=request.user.pk).prefetch_related(
        "memberships__entity",
        "memberships__institution",
    )

    if role:
        users_qs = users_qs.filter(memberships__role=role)
    if entity_id:
        users_qs = users_qs.filter(memberships__entity_id=entity_id)
    if institution:
        users_qs = users_qs.filter(memberships__institution_id=institution)

    users = users_qs.order_by("username").distinct()

    roles = Membership.ROLE_CHOICES
    entities = Entity.objects.filter(is_active=True).order_by("name")
    institutions = Institution.objects.all().order_by("code")

    return render(
        request,
        "accounts/admin_user_list.html",
        {
            "users": users,
            "roles": roles,
            "entities": entities,
            "institutions": institutions,
            "filter_role": role,
            "filter_entity": entity_id,
            "filter_institution": institution,
        },
    )


@admin_required
def admin_user_create(request):
    if request.method == "POST":
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            scope_label = getattr(form, "created_scope_label", "Sin alcance")


            record_action(
                "USER",
                request=request,
                module="Accounts",
                object_repr=f"Usuario {user.username} creado",
                details=f"Rol {form.cleaned_data.get('role')} - {scope_label}",
            )
            return redirect("accounts:admin_user_list")
    else:
        form = AdminUserCreateForm()

    return render(request, "accounts/admin_user_create.html", {"form": form})


@admin_required
def admin_user_edit(request, user_id):
    if user_id == request.user.id:
        return redirect("accounts:admin_user_list")

    user = get_object_or_404(User, pk=user_id, is_superuser=False)
    memberships = list(
        user.memberships.select_related("entity__category__subsector", "institution").order_by("entity__name")
    )

    initial = {}
    if memberships:
        primary = memberships[0]
        initial.update(
            {
                "role": primary.role,
                "validation_level": primary.validation_level,
                "can_validate_daily": primary.can_validate_daily,
                "can_validate_monthly": primary.can_validate_monthly,
                "can_validate_weekly": primary.can_validate_weekly,
                "can_validate_projections": primary.can_validate_projections,
                "institution": primary.institution,
            }
        )

        entities = [m.entity for m in memberships if m.entity_id]
        if entities:
            category_ids = {entity.category_id for entity in entities}
            first_entity = entities[0]
            first_category = first_entity.category
            first_subsector = first_category.subsector

            if len(category_ids) == 1:
                total_active_in_category = Entity.objects.filter(category=first_category, is_active=True).count()
                if len(entities) == total_active_in_category and total_active_in_category > 0:
                    initial.update(
                        {
                            "subsector": first_subsector,
                            "category": first_category,
                            "scope_mode": AdminUserCreateForm.SCOPE_CATEGORY_GLOBAL,
                            "entity": None,
                        }
                    )
                else:
                    initial.update(
                        {
                            "subsector": first_subsector,
                            "category": first_category,
                            "scope_mode": AdminUserCreateForm.SCOPE_ENTITY,
                            "entity": first_entity,
                        }
                    )
            else:
                initial.update(
                    {
                        "subsector": first_subsector,
                        "category": first_category,
                        "scope_mode": AdminUserCreateForm.SCOPE_ENTITY,
                        "entity": first_entity,
                    }
                )

    if request.method == "POST":
        form = AdminUserCreateForm(request.POST, instance=user)
        if form.is_valid():
            data = form.cleaned_data
            user_obj = form.save(commit=False)
            user_obj.username = data["username"]
            user_obj.first_name = data["first_name"]
            user_obj.last_name = data["last_name"]
            user_obj.email = data["email"]

            password = (data.get("password1") or "").strip()
            if password:
                user_obj.set_password(password)
                profile, _ = AccountProfile.objects.get_or_create(user=user_obj)
                profile.must_change_password = True
                profile.save(update_fields=["must_change_password"])

            user_obj.save()
            form.create_memberships_for_user(user_obj, replace=True)

            scope_label = getattr(form, "created_scope_label", "Sin alcance")
            record_action(
                "USER",
                request=request,
                module="Accounts",
                object_repr=f"Usuario {user_obj.username} editado",
                details=f"Rol {data.get('role')} - {scope_label}",
            )
            return redirect("accounts:admin_user_list")
    else:
        form = AdminUserCreateForm(instance=user, initial=initial)

    return render(
        request,
        "accounts/admin_user_edit.html",
        {
            "form": form,
            "user_obj": user,
        },
    )



@admin_required
def admin_user_delete(request, user_id):
    if user_id == request.user.id:
        return redirect("accounts:admin_user_list")

    user = get_object_or_404(User, pk=user_id, is_superuser=False)
    if request.method == "POST":
        username = user.username
        user.delete()
        record_action(
            "USER",
            request=request,
            module="Accounts",
            object_repr=f"Usuario {username} eliminado",
            details="Usuario eliminado desde el panel de administraciÃ³n",
        )
        return redirect("accounts:admin_user_list")

    return render(
        request,
        "accounts/admin_user_confirm_delete.html",
        {
            "user_obj": user,
        },
    )


@admin_required
def institution_list(request):
    institutions = Institution.objects.all().order_by("code")
    return render(
        request,
        "accounts/institution_list.html",
        {"institutions": institutions},
    )


@admin_required
def institution_create(request):
    if request.method == "POST":
        form = InstitutionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accounts:institution_list")
    else:
        form = InstitutionForm()
    return render(
        request,
        "accounts/institution_form.html",
        {"form": form, "institution": None},
    )


@admin_required
def institution_edit(request, institution_id):
    institution = get_object_or_404(Institution, pk=institution_id)
    if request.method == "POST":
        form = InstitutionForm(request.POST, instance=institution)
        if form.is_valid():
            form.save()
            return redirect("accounts:institution_list")
    else:
        form = InstitutionForm(instance=institution)
    return render(
        request,
        "accounts/institution_form.html",
        {"form": form, "institution": institution},
    )


@admin_required
def institution_delete(request, institution_id):
    institution = get_object_or_404(Institution, pk=institution_id)
    if request.method == "POST":
        try:
            institution.delete()
            return redirect("accounts:institution_list")
        except ProtectedError:
            return render(
                request,
                "accounts/institution_confirm_delete.html",
                {
                    "institution": institution,
                    "error": "No se puede eliminar: hay usuarios asociados.",
                },
            )
    return render(
        request,
        "accounts/institution_confirm_delete.html",
        {"institution": institution},
    )


