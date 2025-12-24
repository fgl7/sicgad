from django import forms
from django.contrib.auth import get_user_model

from plants.models import Plant
from .models import Institution, Membership


User = get_user_model()


class AdminUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Contrasena temporal",
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-xs",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirmar contrasena",
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
    plant = forms.ModelChoiceField(
        label="Planta",
        queryset=Plant.objects.all(),
        required=False,
        empty_label="GLOBAL (todas las plantas)",
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

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        role = cleaned.get("role")
        plant = cleaned.get("plant")
        validation_level = cleaned.get("validation_level")

        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contrasenas no coinciden.")

        # La planta es obligatoria para cargadores; otros roles pueden ser globales.
        if role == "LOADER" and plant is None:
            self.add_error("plant", "La planta es obligatoria para este rol.")

        if role == "VALIDATOR" and not validation_level:
            self.add_error("validation_level", "Debe definir un nivel de validacion para un Validador.")

        if role == "VALIDATOR" and not cleaned.get("institution"):
            self.add_error("institution", "Debe definir una institucion para un Validador.")

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data["password1"]
        user.set_password(password)
        user.is_active = True
        if commit:
            user.save()
            Membership.objects.create(
                user=user,
                plant=self.cleaned_data.get("plant"),
                role=self.cleaned_data["role"],
                validation_level=self.cleaned_data.get("validation_level"),
                can_validate_daily=self.cleaned_data.get("can_validate_daily", False),
                can_validate_monthly=self.cleaned_data.get("can_validate_monthly", False),
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
