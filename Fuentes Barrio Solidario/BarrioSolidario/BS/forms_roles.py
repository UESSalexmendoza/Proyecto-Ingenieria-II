"""Campos editables del catálogo de roles; permisos filtrados en la vista."""
import re
from django import forms
from django.core.exceptions import ValidationError
from .models import Rol


class RolForm(forms.Form):
    codigo = forms.CharField(max_length=32, help_text="Identificador estable, por ejemplo COORDINADOR_BARRIO")
    nombre = forms.CharField(min_length=3, max_length=80)
    descripcion = forms.CharField(max_length=255, widget=forms.Textarea(attrs={"rows": 3}))
    activo = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, instancia=None, **kwargs):
        self.instancia = instancia
        super().__init__(*args, **kwargs)
        if instancia is not None:
            self.fields["codigo"].disabled = True
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,31}", codigo):
            raise ValidationError("Usa 3 a 32 caracteres: letras mayúsculas, números y guion bajo.")
        if Rol.objects.filter(codigo__iexact=codigo).exclude(pk=getattr(self.instancia, "pk", None)).exists():
            raise ValidationError("Este código de rol ya existe.")
        return codigo

    def clean_nombre(self):
        nombre = " ".join(self.cleaned_data["nombre"].split())
        if "<" in nombre or ">" in nombre:
            raise ValidationError("No se permite código HTML.")
        return nombre

    def clean_descripcion(self):
        descripcion = " ".join(self.cleaned_data["descripcion"].split())
        if "<" in descripcion or ">" in descripcion:
            raise ValidationError("No se permite código HTML.")
        return descripcion


class PermisosRolForm(forms.Form):
    permisos = forms.MultipleChoiceField(required=False, choices=())
    motivo = forms.CharField(min_length=10, max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    confirmacion = forms.BooleanField(required=True, error_messages={"required": "Confirma que revisaste el alcance de los permisos."})

    def __init__(self, *args, disponibles=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permisos"].choices = [(str(p.pk), p.name) for p in disponibles]

    def clean_motivo(self):
        motivo = " ".join(self.cleaned_data["motivo"].split())
        if "<" in motivo or ">" in motivo:
            raise ValidationError("No se permite código HTML.")
        return motivo
