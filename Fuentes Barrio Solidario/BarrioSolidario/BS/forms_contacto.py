import html
import re
import unicodedata

from django import forms

from .models import CasoContacto

ETIQUETA_HTML = re.compile(r"<\s*(?:/?[a-z][^>]*|!--[^>]*--|\?[^>]*|![^>]*)>", re.IGNORECASE | re.DOTALL)
ESQUEMA_ACTIVO = re.compile(r"(?:javascript|vbscript|data)\s*:", re.IGNORECASE)


def validar_texto_plano(valor):
    valor = unicodedata.normalize("NFC", valor.strip())
    decodificado = html.unescape(valor)
    if ETIQUETA_HTML.search(decodificado) or ESQUEMA_ACTIVO.search(decodificado):
        raise forms.ValidationError("No se permite código HTML ni enlaces ejecutables.")
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in valor):
        raise forms.ValidationError("El texto contiene caracteres no permitidos.")
    return valor


class CasoContactoForm(forms.ModelForm):
    # Campo trampa: los navegadores normales no lo rellenan.
    sitio_web = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = CasoContacto
        fields = ("nombre", "email", "telefono", "institucion", "mensaje")

    def clean_sitio_web(self):
        if self.cleaned_data["sitio_web"]:
            raise forms.ValidationError("No se pudo procesar el formulario.")
        return ""

    def clean_nombre(self):
        nombre = " ".join(validar_texto_plano(self.cleaned_data["nombre"]).split())
        if len(nombre) < 3 or not all(c.isalpha() or c in " -'’" for c in nombre):
            raise forms.ValidationError("Escribe un nombre válido (solo letras y espacios).")
        return nombre

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_telefono(self):
        telefono = validar_texto_plano(self.cleaned_data["telefono"])
        if telefono and (not all(c.isdigit() or c in " +()-" for c in telefono)
                         or not 7 <= sum(c.isdigit() for c in telefono) <= 15):
            raise forms.ValidationError("Escribe un teléfono válido de 7 a 15 dígitos.")
        return telefono

    def clean_institucion(self):
        return validar_texto_plano(self.cleaned_data["institucion"])

    def clean_mensaje(self):
        mensaje = validar_texto_plano(self.cleaned_data["mensaje"])
        if len(mensaje) < 10:
            raise forms.ValidationError("Describe tu consulta en al menos 10 caracteres.")
        return mensaje


class RevisionCasoForm(forms.ModelForm):
    class Meta:
        model = CasoContacto
        fields = ("estado", "nota_revision")
        widgets = {"nota_revision": forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
                   "estado": forms.Select(attrs={"class": "form-select"})}

    def clean_nota_revision(self):
        return validar_texto_plano(self.cleaned_data["nota_revision"])
