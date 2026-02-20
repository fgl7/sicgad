from django import forms
from django.contrib.auth import get_user_model

from .models import AccountProfile, Institution, Membership
from structure.models import Category, Entity, Sector, Subsector


User = get_user_model()


class SubsectorChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.sector.name} / {obj.name}"


class CategoryMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.subsector.name} / {obj.name}"


class EntityMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.category.subsector.name} / {obj.category.name} / {obj.name}"


class CategorySelectMultipleWidget(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option.setdefault("attrs", {})
            option["attrs"]["data-subsector-id"] = str(instance.subsector_id)
        return option


class EntitySelectMultipleWidget(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option.setdefault("attrs", {})
            option["attrs"]["data-category-id"] = str(instance.category_id)
            option["attrs"]["data-subsector-id"] = str(instance.category.subsector_id)
        return option


class AdminUserCreateForm(forms.ModelForm):
    SCOPE_ENTITY = "ENTITY"
    SCOPE_CATEGORY_GLOBAL = "CATEGORY_GLOBAL"
    SCOPE_MODE_CHOICES = (
        (SCOPE_ENTITY, "Entidad especifica"),
        (SCOPE_CATEGORY_GLOBAL, "Global en categoria"),
    )
    AUTH_SCOPE_SECTOR = "SECTOR"
    AUTH_SCOPE_ALL = "ALL_SECTORS"
    AUTH_SCOPE_CHOICES = (
        (AUTH_SCOPE_SECTOR, "Un solo sector"),
        (AUTH_SCOPE_ALL, "Todos los sectores"),
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
    category = CategoryMultipleChoiceField(
        label="Categorias",
        queryset=Category.objects.filter(is_active=True).select_related("subsector", "subsector__sector").order_by("subsector__sector__name", "subsector__name", "name"),
        required=False,
        widget=CategorySelectMultipleWidget(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs min-h-[8rem]",
            }
        ),
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
    entity = EntityMultipleChoiceField(
        label="Entidades",
        queryset=Entity.objects.filter(is_active=True).select_related("category", "category__subsector").order_by("category__subsector__name", "category__name", "name"),
        required=False,
        widget=EntitySelectMultipleWidget(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs min-h-[9rem]",
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
    viewer_profile_type = forms.ChoiceField(
        label="Plantilla de visualizador",
        choices=AccountProfile.VIEWER_PROFILE_CHOICES,
        required=False,
        initial=AccountProfile.VIEWER_STANDARD,
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    authority_scope_mode = forms.ChoiceField(
        label="Alcance autoridad MHE",
        choices=AUTH_SCOPE_CHOICES,
        required=False,
        initial=AUTH_SCOPE_SECTOR,
        widget=forms.Select(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    authority_sector = forms.ModelChoiceField(
        label="Sector",
        queryset=Sector.objects.filter(is_active=True).order_by("name"),
        required=False,
        empty_label="Seleccione sector",
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
        if is_editing and getattr(self.instance, "pk", None):
            profile = getattr(self.instance, "profile", None)
            if profile:
                self.initial.setdefault("viewer_profile_type", profile.viewer_profile_type)
        self.initial.setdefault("authority_scope_mode", self.AUTH_SCOPE_SECTOR)

        initial_entities = self.initial.get("entity")
        initial_categories = self.initial.get("category")
        if initial_entities and not initial_categories:
            first_entity = None
            if hasattr(initial_entities, "all"):
                first_entity = initial_entities.first()
            elif isinstance(initial_entities, (list, tuple)):
                first_raw = initial_entities[0] if initial_entities else None
                if hasattr(first_raw, "category"):
                    first_entity = first_raw
                elif first_raw:
                    first_entity = Entity.objects.filter(pk=first_raw).first()
            elif hasattr(initial_entities, "category"):
                first_entity = initial_entities
            if first_entity and hasattr(first_entity, "category"):
                self.initial.setdefault("category", [first_entity.category_id])
                self.initial.setdefault("subsector", first_entity.category.subsector)
        elif initial_categories and not self.initial.get("subsector"):
            category_ids = []
            if hasattr(initial_categories, "all"):
                category_ids = list(initial_categories.values_list("id", flat=True))
            elif isinstance(initial_categories, (list, tuple)):
                category_ids = [item.id if hasattr(item, "id") else item for item in initial_categories]
            elif hasattr(initial_categories, "id"):
                category_ids = [initial_categories.id]
            subsector_ids = set(
                Category.objects.filter(id__in=category_ids).values_list("subsector_id", flat=True)
            )
            if len(subsector_ids) == 1:
                subsector_id = next(iter(subsector_ids))
                self.initial["subsector"] = Subsector.objects.filter(pk=subsector_id).first()
        self.initial.setdefault("scope_mode", self.SCOPE_ENTITY)

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        role = cleaned.get("role")
        subsector = cleaned.get("subsector")
        selected_categories = list(cleaned.get("category") or [])
        scope_mode = cleaned.get("scope_mode") or self.SCOPE_ENTITY
        selected_entities = list(cleaned.get("entity") or [])
        validation_level = cleaned.get("validation_level")
        viewer_profile_type = cleaned.get("viewer_profile_type") or AccountProfile.VIEWER_STANDARD
        authority_scope_mode = cleaned.get("authority_scope_mode") or self.AUTH_SCOPE_SECTOR
        authority_sector = cleaned.get("authority_sector")
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

        if selected_entities and not selected_categories:
            selected_categories = list(
                Category.objects.filter(id__in={entity.category_id for entity in selected_entities})
            )
            cleaned["category"] = selected_categories
        if selected_categories and not subsector:
            subsector_ids = {category.subsector_id for category in selected_categories}
            if len(subsector_ids) == 1:
                subsector = selected_categories[0].subsector
                cleaned["subsector"] = subsector

        # El cargador siempre trabaja por entidad especifica. Si la categoria
        # solo tiene una entidad activa, normalizamos automaticamente.
        if (
            role == "LOADER"
            and scope_mode == self.SCOPE_CATEGORY_GLOBAL
            and not selected_entities
            and len(selected_categories) == 1
        ):
            active_entities = Entity.objects.filter(category=selected_categories[0], is_active=True).order_by("name")
            if active_entities.count() == 1:
                selected_entities = [active_entities.first()]
                cleaned["entity"] = selected_entities
                scope_mode = self.SCOPE_ENTITY
                cleaned["scope_mode"] = scope_mode

        if selected_categories and subsector:
            mismatch = [category for category in selected_categories if category.subsector_id != subsector.id]
            if mismatch:
                self.add_error("category", "Todas las categorias deben pertenecer al subsector seleccionado.")

        is_authority_viewer = (
            role == "VIEWER"
            and viewer_profile_type == AccountProfile.VIEWER_AUTHORITY_MHE
        )

        if is_authority_viewer:
            if authority_scope_mode == self.AUTH_SCOPE_SECTOR:
                if not authority_sector:
                    self.add_error("authority_sector", "Debe seleccionar un sector.")
                elif not Entity.objects.filter(
                    category__subsector__sector=authority_sector,
                    is_active=True,
                ).exists():
                    self.add_error("authority_sector", "El sector no tiene entidades activas asociadas.")
        else:
            if scope_mode == self.SCOPE_ENTITY:
                if not selected_categories:
                    self.add_error("category", "Debe seleccionar al menos una categoria.")
                if not selected_entities:
                    self.add_error("entity", "Debe seleccionar al menos una entidad.")
                elif selected_categories:
                    category_ids = {category.id for category in selected_categories}
                    out_of_category = [
                        entity for entity in selected_entities if entity.category_id not in category_ids
                    ]
                    if out_of_category:
                        self.add_error("entity", "Todas las entidades deben pertenecer a las categorias seleccionadas.")

            if scope_mode == self.SCOPE_CATEGORY_GLOBAL:
                if role == "LOADER":
                    self.add_error("scope_mode", "El rol Cargador debe estar asociado a una entidad especifica.")
                if not selected_categories:
                    self.add_error("category", "Debe seleccionar una o mas categorias para el alcance global.")
                else:
                    missing = [
                        category.name
                        for category in selected_categories
                        if not Entity.objects.filter(category=category, is_active=True).exists()
                    ]
                    if missing:
                        self.add_error(
                            "category",
                            "Las siguientes categorias no tienen entidades activas: " + ", ".join(missing),
                        )

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
        elif role not in {"LOADER"}:
            cleaned["validation_level"] = None
            cleaned["can_validate_daily"] = False
            cleaned["can_validate_weekly"] = False
            cleaned["can_validate_monthly"] = False
            cleaned["can_validate_projections"] = False
        else:
            cleaned["validation_level"] = None

        if role != "VIEWER":
            viewer_profile_type = AccountProfile.VIEWER_STANDARD
            cleaned["authority_scope_mode"] = self.AUTH_SCOPE_SECTOR
            cleaned["authority_sector"] = None
        cleaned["viewer_profile_type"] = viewer_profile_type

        cleaned["scope_mode"] = scope_mode
        return cleaned

    def _target_entities_and_label(self):
        role = self.cleaned_data.get("role")
        viewer_profile_type = self.cleaned_data.get("viewer_profile_type")
        if role == "VIEWER" and viewer_profile_type == AccountProfile.VIEWER_AUTHORITY_MHE:
            auth_scope = self.cleaned_data.get("authority_scope_mode") or self.AUTH_SCOPE_SECTOR
            auth_sector = self.cleaned_data.get("authority_sector")
            if auth_scope == self.AUTH_SCOPE_ALL:
                return Entity.objects.none(), "Todos los sectores (global)"
            target_entities = Entity.objects.filter(
                category__subsector__sector=auth_sector,
                is_active=True,
            ).order_by("name")
            scope_label = f"Sector {auth_sector.name}" if auth_sector else "Sector no definido"
            return target_entities, scope_label

        scope_mode = self.cleaned_data.get("scope_mode") or self.SCOPE_ENTITY
        selected_categories = list(self.cleaned_data.get("category") or [])
        selected_entities = list(self.cleaned_data.get("entity") or [])

        if scope_mode == self.SCOPE_CATEGORY_GLOBAL and selected_categories:
            target_entities = Entity.objects.filter(category__in=selected_categories, is_active=True).order_by("name")
            if len(selected_categories) == 1:
                scope_label = f"Global en categoria {selected_categories[0].name}"
            else:
                scope_label = f"Global en {len(selected_categories)} categorias"
            return target_entities, scope_label

        selected_ids = [entity.id for entity in selected_entities]
        target_entities = (
            Entity.objects.filter(pk__in=selected_ids, is_active=True).order_by("name")
            if selected_ids
            else Entity.objects.none()
        )
        if len(selected_entities) == 1:
            scope_label = f"Entidad {selected_entities[0]}"
        elif len(selected_entities) > 1:
            scope_label = f"{len(selected_entities)} entidades especÃ­ficas"
        else:
            scope_label = "Sin alcance"
        return target_entities, scope_label

    def create_memberships_for_user(self, user, replace=False):
        if replace:
            Membership.objects.filter(user=user).delete()

        created_memberships = []
        target_entities, scope_label = self._target_entities_and_label()

        role = self.cleaned_data["role"]
        viewer_profile_type = self.cleaned_data.get("viewer_profile_type")
        is_authority_all_sectors = (
            role == "VIEWER"
            and viewer_profile_type == AccountProfile.VIEWER_AUTHORITY_MHE
            and (self.cleaned_data.get("authority_scope_mode") == self.AUTH_SCOPE_ALL)
        )

        if is_authority_all_sectors:
            created_memberships.append(
                Membership.objects.create(
                    user=user,
                    entity=None,
                    role=role,
                    validation_level=None,
                    can_validate_daily=False,
                    can_validate_monthly=False,
                    can_validate_weekly=False,
                    can_validate_projections=False,
                    institution=self.cleaned_data.get("institution"),
                    is_active=True,
                )
            )
        else:
            for entity in target_entities:
                created_memberships.append(
                    Membership.objects.create(
                        user=user,
                        entity=entity,
                        role=role,
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
            self.save_profile_for_user(user)

        return user

    def save_profile_for_user(self, user):
        profile, _ = AccountProfile.objects.get_or_create(user=user)
        profile.viewer_profile_type = (
            self.cleaned_data.get("viewer_profile_type") or AccountProfile.VIEWER_STANDARD
        )
        profile.save(update_fields=["viewer_profile_type"])


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

