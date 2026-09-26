import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import PerfilUsuario

ROLES_PUBLICOS = (
    ("ADULTO_MAYOR", "Adulto mayor"),
    ("FAMILIAR_CUIDADOR", "Familiar / cuidador"),
    ("VOLUNTARIO", "Voluntario"),
)


class RegistroForm(forms.Form):
    tipoUsuario = forms.ChoiceField(choices=(("", "Selecciona una opción"), *ROLES_PUBLICOS))
    nombres = forms.CharField(min_length=2, max_length=60, strip=True)
    apellidos = forms.CharField(min_length=2, max_length=60, strip=True)
    email = forms.EmailField(max_length=150)
    telefono = forms.CharField(min_length=8, max_length=15, strip=True)
    aceptaPoliticas = forms.BooleanField(required=True)

    @staticmethod
    def _validar_nombre(valor):
        nombre = " ".join(valor.split())
        if not all(c.isalpha() or c in " -'’" for c in nombre) or not any(c.isalpha() for c in nombre):
            raise ValidationError("Usa letras, espacios, guiones o apóstrofos.")
        return nombre

    def clean_nombres(self):
        return self._validar_nombre(self.cleaned_data["nombres"])

    def clean_apellidos(self):
        return self._validar_nombre(self.cleaned_data["apellidos"])

    def clean_email(self):
        correo = self.cleaned_data["email"].strip().casefold()
        User = get_user_model()
        if (User.objects.filter(email__iexact=correo).exists()
                or User.objects.filter(username__iexact=correo).exists()
                or PerfilUsuario.objects.filter(correo__iexact=correo).exists()):
            raise ValidationError("Ya existe una cuenta con este correo.")
        return correo

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"].strip()
        if not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa únicamente números: entre 8 y 15 dígitos.")
        return telefono


class ActivarCuentaForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput, min_length=12, max_length=15)
    password2 = forms.CharField(widget=forms.PasswordInput, min_length=12, max_length=15)

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean(self):
        datos = super().clean()
        clave1, clave2 = datos.get("password1"), datos.get("password2")
        if clave1 and clave2 and clave1 != clave2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if clave1 and self.usuario:
            grupos = sum(bool(re.search(patron, clave1)) for patron in (
                r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9\s]",
            ))
            if grupos < 3:
                self.add_error(
                    "password1",
                    "Usa al menos 3 de estos grupos: minúsculas, mayúsculas, números y símbolos.",
                )
            try:
                validate_password(clave1, user=self.usuario)
            except ValidationError as error:
                self.add_error("password1", error)
        return datos


class ReenviarActivacionForm(forms.Form):
    email = forms.EmailField(max_length=150)


class SolicitarRecuperacionForm(forms.Form):
    email = forms.EmailField(max_length=150)


class PerfilCuentaForm(forms.Form):
    nombres = forms.CharField(min_length=2, max_length=60)
    apellidos = forms.CharField(min_length=2, max_length=60)
    telefono = forms.CharField(min_length=8, max_length=15)

    def __init__(self, *args, usuario, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update({"nombres": usuario.first_name, "apellidos": usuario.last_name,
                                 "telefono": perfil.telefono if perfil else ""})

    def clean_nombres(self):
        return RegistroForm._validar_nombre(self.cleaned_data["nombres"])

    def clean_apellidos(self):
        return RegistroForm._validar_nombre(self.cleaned_data["apellidos"])

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"]
        if not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa únicamente números: entre 8 y 15 dígitos.")
        return telefono


class CambiarClaveCuentaForm(PasswordChangeForm):
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={"maxlength": 15}), min_length=12, max_length=15)
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={"maxlength": 15}), min_length=12, max_length=15)

    def clean_new_password1(self):
        clave = self.cleaned_data["new_password1"]
        grupos = sum(bool(re.search(p, clave)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9\s]"))
        if grupos < 3:
            raise ValidationError("Usa al menos 3 grupos: minúsculas, mayúsculas, números y símbolos.")
        return clave
