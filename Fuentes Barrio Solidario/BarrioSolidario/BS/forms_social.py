import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .forms_cuentas import ROLES_PUBLICOS, RegistroForm
from .models import PerfilUsuario


class CompletarRegistroSocialForm(forms.Form):
    tipoUsuario = forms.ChoiceField(choices=(("", "Selecciona una opción"), *ROLES_PUBLICOS))
    nombres = forms.CharField(min_length=2, max_length=60, strip=True)
    apellidos = forms.CharField(min_length=2, max_length=60, strip=True)
    telefono = forms.CharField(min_length=8, max_length=15, strip=True)
    aceptaPoliticas = forms.BooleanField(required=True)

    def clean_nombres(self):
        return RegistroForm._validar_nombre(self.cleaned_data["nombres"])

    def clean_apellidos(self):
        return RegistroForm._validar_nombre(self.cleaned_data["apellidos"])

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"]
        if not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa únicamente números: entre 8 y 15 dígitos.")
        return telefono
