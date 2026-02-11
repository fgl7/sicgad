from django import forms
from django.contrib.auth import get_user_model

from .models import Institution, Membership
from structure.models import Category, Entity, Subsector


User = get_user_model()


class SubsectorChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.sector.name} / {obj.name}"


class CategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.subsector.name} / {obj.name}"


class EntityChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.category.subsector.name} / {obj.category.name} / {obj.name}"


class AdminUserCreateForm(forms.ModelForm):
    SCOPE_ENTITY = "ENTITY"
    SCOPE_CATEGORY_GLOBAL = "CATEGORY_GLOBAL"
    SCOPE_MODE_CHOICES = (
        (SCOPE_ENTITY, "Entidad especifica"),
        (SCOPE_CATEGORY_GLOBAL, "Global en categoria"),
    )

    password1 = forms.CharField(
        label="Contrasena temporal",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirmar contrasena",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    role = forms.ChoiceField(
        label="Rol principal",
        choices=Membership.ROLE_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    subsector = SubsectorChoiceField(
        label="Subsector",
        queryset=Subsector.objects.filter(is_active=True).select_related("sector").order_by("sector__name", "name"),
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
        empty_label="Seleccione subsector",
    )
    category = CategoryChoiceField(
        label="Categoria",
        queryset=Category.objects.filter(is_active=True).select_related("subsector", "subsector__sector").order_by("subsector__sector__name", "subsector__name", "name"),
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
        empty_label="Seleccione categoria",
    )
    scope_mode = forms.ChoiceField(
        label="Alcance",
        choices=SCOPE_MODE_CHOICES,
        required=False,
        initial=SCOPE_ENTITY,
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    entity = EntityChoiceField(
        label="Entidad",
        queryset=Entity.objects.filter(is_active=True).select_related("category", "category__subsector").order_by("category__subsector__name", "category__name", "name"),
        required=False,
        empty_label="Seleccione entidad",
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    validation_level = forms.IntegerField(
        label="Nivel de validacion",
        required=False,
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    can_validate_daily = forms.BooleanField(
        label="Puede validar flujo diario",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "rounded border-slate-700",
            }
        ),
    )
    can_validate_monthly = forms.BooleanField(
        label="Puede validar flujo mensual/certificacion",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "rounded border-slate-700",
            }
        ),
    )
    can_validate_weekly = forms.BooleanField(
        label="Puede validar flujo semanal",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "rounded border-slate-700",
            }
        ),
    )
    can_validate_projections = forms.BooleanField(
        label="Puede validar proyecciones",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "rounded border-slate-700",
            }
        ),
    )
    institution = forms.ModelChoiceField(
        label="Institucion",
        queryset=Institution.objects.filter(is_active=True).order_by("code"),
        required=False,
        empty_label="(sin institucion)",
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        is_editing = bool(getattr(self.instance, "pk", None))
        self.fields["password1"].required = not is_editing
        self.fields["password2"].required = not is_editing

        initial_entity = self.initial.get("entity")
        if initial_entity and hasattr(initial_entity, "category"):
            self.initial.setdefault("category", initial_entity.category)
            self.initial.setdefault("subsector", initial_entity.category.subsector)
        self.initial.setdefault("scope_mode", self.SCOPE_ENTITY)

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        role = cleaned.get("role")
        subsector = cleaned.get("subsector")
        category = cleaned.get("category")
        scope_mode = cleaned.get("scope_mode") or self.SCOPE_ENTITY
        entity = cleaned.get("entity")
        validation_level = cleaned.get("validation_level")
        is_editing = bool(getattr(self.instance, "pk", None))

        if is_editing and not p1 and not p2:
            pass
        else:
            if not p1:
                self.add_error("password1", "Debe definir una contrasena.")
            if not p2:
                self.add_error("password2", "Debe confirmar la contrasena.")
            if p1 and p2 and p1 != p2:
                self.add_error("password2", "Las contrasenas no coinciden.")

        if entity and not category:
            category = entity.category
            cleaned["category"] = category
        if category and not subsector:
            subsector = category.subsector
            cleaned["subsector"] = subsector

        if category and subsector and category.subsector_id != subsector.id:
            self.add_error("category", "La categoria no pertenece al subsector seleccionado.")

        if scope_mode == self.SCOPE_ENTITY:
            if not entity:
                self.add_error("entity", "Debe seleccionar una entidad.")
            elif category and entity.category_id != category.id:
                self.add_error("entity", "La entidad no pertenece a la categoria seleccionada.")

        if scope_mode == self.SCOPE_CATEGORY_GLOBAL:
            if role == "LOADER":
                self.add_error("scope_mode", "El rol Cargador debe estar asociado a una entidad especifica.")
            if not category:
                self.add_error("category", "Debe seleccionar una categoria para el alcance global.")
            elif not Entity.objects.filter(category=category, is_active=True).exists():
                self.add_error("category", "La categoria no tiene entidades activas asociadas.")

        if role == "LOADER" and scope_mode != self.SCOPE_ENTITY:
            self.add_error("scope_mode", "El rol Cargador debe estar asociado a una entidad especifica.")

        if role == "VALIDATOR" and not validation_level:
            self.add_error("validation_level", "Debe definir un nivel de validacion para un Validador.")

        if role == "VALIDATOR" and not cleaned.get("institution"):
            self.add_error("institution", "Debe definir una institucion para un Validador.")

        if role == "VALIDATOR":
            can_validate_any = any(
                cleaned.get(flag)
                for flag in (
                    "can_validate_daily",
                    "can_validate_weekly",
                    "can_validate_monthly",
                    "can_validate_projections",
                )
            )
            if not can_validate_any:
                self.add_error(
                    None,
                    "Debe habilitar al menos un flujo de validacion (diario, semanal, mensual o proyecciones).",
                )

        cleaned["scope_mode"] = scope_mode
        return cleaned

    def _target_entities_and_label(self):
        scope_mode = self.cleaned_data.get("scope_mode") or self.SCOPE_ENTITY
        selected_category = self.cleaned_data.get("category")
        selected_entity = self.cleaned_data.get("entity")

        if scope_mode == self.SCOPE_CATEGORY_GLOBAL and selected_category:
            target_entities = Entity.objects.filter(category=selected_category, is_active=True).order_by("name")
            scope_label = f"Global en categoria {selected_category.name}"
            return target_entities, scope_label

        target_entities = Entity.objects.filter(pk=selected_entity.pk) if selected_entity else Entity.objects.none()
        scope_label = f"Entidad {selected_entity}" if selected_entity else "Sin alcance"
        return target_entities, scope_label

    def create_memberships_for_user(self, user, replace=False):
        if replace:
            Membership.objects.filter(user=user).delete()

        created_memberships = []
        target_entities, scope_label = self._target_entities_and_label()

        for entity in target_entities:
            created_memberships.append(
                Membership.objects.create(
                    user=user,
                    entity=entity,
                    role=self.cleaned_data["role"],
                    validation_level=self.cleaned_data.get("validation_level"),
                    can_validate_daily=self.cleaned_data.get("can_validate_daily", False),
                    can_validate_monthly=self.cleaned_data.get("can_validate_monthly", False),
                    can_validate_weekly=self.cleaned_data.get("can_validate_weekly", False),
                    can_validate_projections=self.cleaned_data.get("can_validate_projections", False),
                    institution=self.cleaned_data.get("institution"),
                    is_active=True,
                )
            )

        self.created_memberships = created_memberships
        self.created_scope_label = scope_label
        return created_memberships

    def save(self, commit=True):
        user = super().save(commit=False)
        password = (self.cleaned_data.get("password1") or "").strip()
        if password:
            user.set_password(password)
        user.is_active = True

        if commit:
            user.save()
            self.create_memberships_for_user(user, replace=False)

        return user


class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ["code", "name", "description", "is_active"]
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
                    "rows": 3,
                }
            ),
        }

