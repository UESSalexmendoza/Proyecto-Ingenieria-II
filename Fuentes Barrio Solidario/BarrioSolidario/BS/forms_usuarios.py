"""Validaciones del alta y revisión de cuentas desde el panel."""
import re
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .forms_cuentas import RegistroForm, ActivarCuentaForm
from .models import PerfilUsuario, Rol, UsuarioRol


class AltaUsuarioForm(forms.Form):
    nombres = forms.CharField(min_length=2, max_length=60)
    apellidos = forms.CharField(min_length=2, max_length=60)
    email = forms.EmailField(max_length=150)
    telefono = forms.CharField(min_length=8, max_length=15)
    rol = forms.ModelChoiceField(queryset=Rol.objects.none(), empty_label="Selecciona un rol")
    observacion = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rol"].queryset = Rol.objects.filter(activo=True).order_by("nombre")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control" if not isinstance(field.widget, forms.Select) else "form-select")

    def clean_nombres(self):
        return RegistroForm._validar_nombre(self.cleaned_data["nombres"])

    def clean_apellidos(self):
        return RegistroForm._validar_nombre(self.cleaned_data["apellidos"])

    def clean_email(self):
        email = self.cleaned_data["email"].strip().casefold()
        User = get_user_model()
        if (User.objects.filter(email__iexact=email).exists() or
            User.objects.filter(username__iexact=email).exists() or
            PerfilUsuario.objects.filter(correo__iexact=email).exists()):
            raise ValidationError("Este correo ya está registrado.")
        return email

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"].strip()
        if not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa únicamente números: entre 8 y 15 dígitos.")
        return telefono

    def clean_observacion(self):
        texto = " ".join(self.cleaned_data["observacion"].split())
        if "<" in texto or ">" in texto:
            raise ValidationError("No se permite código HTML.")
        return texto


class EditarUsuarioForm(forms.Form):
    nombres = forms.CharField(min_length=2, max_length=60)
    apellidos = forms.CharField(min_length=2, max_length=60)
    telefono = forms.CharField(min_length=8, max_length=15)
    sector_aproximado = forms.CharField(max_length=80, required=False)

    def clean_nombres(self):
        return RegistroForm._validar_nombre(self.cleaned_data["nombres"])

    def clean_apellidos(self):
        return RegistroForm._validar_nombre(self.cleaned_data["apellidos"])

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"].strip()
        if not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa únicamente números: entre 8 y 15 dígitos.")
        return telefono

    def clean_sector_aproximado(self):
        sector = " ".join(self.cleaned_data["sector_aproximado"].split())
        if "<" in sector or ">" in sector:
            raise ValidationError("No se permite código HTML.")
        return sector


class AsignarRolForm(forms.Form):
    rol = forms.ModelChoiceField(queryset=Rol.objects.none())
    estado_aprobacion = forms.ChoiceField(choices=UsuarioRol.Aprobacion.choices)
    activo = forms.BooleanField(required=False)
    observacion = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rol"].queryset = Rol.objects.filter(activo=True).order_by("nombre")

    def clean_observacion(self):
        texto = " ".join(self.cleaned_data["observacion"].split())
        if "<" in texto or ">" in texto:
            raise ValidationError("No se permite código HTML.")
        return texto


class EstadoUsuarioForm(forms.Form):
    estado = forms.ChoiceField(choices=PerfilUsuario.Estado.choices)
    motivo = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean_motivo(self):
        motivo = " ".join(self.cleaned_data["motivo"].split())
        if "<" in motivo or ">" in motivo:
            raise ValidationError("No se permite código HTML.")
        return motivo

    def clean(self):
        datos = super().clean()
        if datos.get("estado") in (PerfilUsuario.Estado.SUSPENDIDA, PerfilUsuario.Estado.INACTIVA) and not datos.get("motivo"):
            self.add_error("motivo", "Indica el motivo del cambio.")
        return datos


class ActivacionAdministrativaForm(ActivarCuentaForm):
    acepta_politicas = forms.BooleanField(required=True, error_messages={"required": "Debes aceptar los términos y las políticas para activar la cuenta."})
