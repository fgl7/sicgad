from django import forms
from django.contrib.auth import get_user_model

from .models import Institution, Membership
from structure.models import Entity


User = get_user_model()


class AdminUserCreateForm(forms.ModelForm):
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
    entity = forms.ModelChoiceField(
        label="Entidad",
        queryset=Entity.objects.filter(is_active=True).order_by("name"),
        required=False,
        empty_label="GLOBAL (todas las entidades)",
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

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        role = cleaned.get("role")
        entity = cleaned.get("entity")
        validation_level = cleaned.get("validation_level")
        is_editing = bool(getattr(self.instance, "pk", None))

        if is_editing and not p1 and not p2:
            # Mantener password anterior.
            pass
        else:
            if not p1:
                self.add_error("password1", "Debe definir una contraseña.")
            if not p2:
                self.add_error("password2", "Debe confirmar la contraseña.")
            if p1 and p2 and p1 != p2:
                self.add_error("password2", "Las contrasenas no coinciden.")

        # La entidad es obligatoria para cargadores; otros roles pueden ser globales.
        if role == "LOADER" and not entity:
            self.add_error("entity", "Debe seleccionar una entidad para este rol.")

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
                    "Debe habilitar al menos un flujo de validación (diario, semanal, mensual o proyecciones).",
                )

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = (self.cleaned_data.get("password1") or "").strip()
        if password:
            user.set_password(password)
        user.is_active = True
        if commit:
            user.save()
            Membership.objects.create(
                user=user,
                entity=self.cleaned_data.get("entity"),
                role=self.cleaned_data["role"],
                validation_level=self.cleaned_data.get("validation_level"),
                can_validate_daily=self.cleaned_data.get("can_validate_daily", False),
                can_validate_monthly=self.cleaned_data.get("can_validate_monthly", False),
                can_validate_weekly=self.cleaned_data.get("can_validate_weekly", False),
                can_validate_projections=self.cleaned_data.get("can_validate_projections", False),
                institution=self.cleaned_data.get("institution"),
                is_active=True,
            )
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
