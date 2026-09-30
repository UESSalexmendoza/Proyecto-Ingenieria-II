"""Validación de catálogos y sus valores, también al publicar borradores."""
import re
from django import forms
from django.core.exceptions import ValidationError
from .models import CatalogoSistema


def texto(valor):
    limpio = " ".join(valor.split())
    if "<" in limpio or ">" in limpio:
        raise ValidationError("No se permite código HTML.")
    return limpio


def codigo(valor):
    valor = valor.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_-]{2,31}", valor):
        raise ValidationError("Usa 3 a 32 caracteres: letras, números, guion o guion bajo.")
    return valor


class CatalogoForm(forms.Form):
    codigo = forms.CharField(max_length=32)
    nombre = forms.CharField(min_length=3, max_length=100)
    descripcion = forms.CharField(min_length=5, max_length=300, widget=forms.Textarea(attrs={"rows": 2}))
    activo = forms.BooleanField(required=False)
    visible_formularios = forms.BooleanField(required=False)

    def __init__(self, *args, instancia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instancia = instancia
        if instancia is not None:
            self.fields["codigo"].disabled = True

    def clean_codigo(self):
        valor = codigo(self.cleaned_data["codigo"])
        if CatalogoSistema.objects.filter(codigo__iexact=valor).exclude(pk=getattr(self.instancia, "pk", None)).exists():
            raise ValidationError("Este código ya existe.")
        return valor

    def clean_nombre(self):
        return texto(self.cleaned_data["nombre"])

    def clean_descripcion(self):
        return texto(self.cleaned_data["descripcion"])

    def clean(self):
        datos = super().clean()
        if datos.get("visible_formularios") and not datos.get("activo"):
            self.add_error("visible_formularios", "Un catálogo inactivo no puede mostrarse en formularios.")
        return datos


class ValorForm(forms.Form):
    codigo = forms.CharField(max_length=32)
    nombre = forms.CharField(min_length=2, max_length=100)
    descripcion = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    orden = forms.IntegerField(min_value=0, max_value=32767)
    activo = forms.BooleanField(required=False)
    disponible_nuevas = forms.BooleanField(required=False)
    requiere_ubicacion = forms.BooleanField(required=False)
    requiere_validacion = forms.BooleanField(required=False)

    def clean_codigo(self):
        return codigo(self.cleaned_data["codigo"])

    def clean_nombre(self):
        return texto(self.cleaned_data["nombre"])

    def clean_descripcion(self):
        return texto(self.cleaned_data["descripcion"])

    def clean(self):
        datos = super().clean()
        if not datos.get("activo") and datos.get("disponible_nuevas"):
            self.add_error("disponible_nuevas", "Un valor inactivo no puede estar disponible para nuevas solicitudes.")
        return datos


class PublicacionForm(forms.Form):
    motivo = forms.CharField(min_length=10, max_length=500)
    confirmacion = forms.BooleanField(required=True, error_messages={"required": "Confirma que revisaste los cambios y dependencias."})

    def clean_motivo(self):
        return texto(self.cleaned_data["motivo"])
