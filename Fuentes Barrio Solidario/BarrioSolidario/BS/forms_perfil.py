"""Validaciones de edición del perfil."""
import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .forms_cuentas import RegistroForm

class PerfilCuentaForm(forms.Form):
    nombres = forms.CharField(min_length=2, max_length=60)
    apellidos = forms.CharField(min_length=2, max_length=60)
    telefono = forms.CharField(min_length=8, max_length=15)
    fecha_nacimiento = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    sector_aproximado = forms.CharField(required=False, max_length=80)
    contacto_alternativo = forms.CharField(required=False, max_length=15)
    canal_preferido = forms.ChoiceField(choices=[("PLATAFORMA", "Mensaje de la plataforma"), ("CORREO", "Correo electrónico")])
    recibir_notificaciones = forms.BooleanField(required=False)
    alto_contraste = forms.BooleanField(required=False)
    informacion_adicional = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    idioma = forms.ChoiceField(choices=[("es", "Español")])
    zona_horaria = forms.ChoiceField(choices=[("America/Guayaquil", "Ecuador")])
    disponibilidad = forms.CharField(required=False, max_length=120)
    permitir_ubicacion_aproximada = forms.BooleanField(required=False)
    compartir_ubicacion_atencion = forms.BooleanField(required=False)
    recibir_recordatorios = forms.BooleanField(required=False)
    recibir_mensajes = forms.BooleanField(required=False)
    recibir_resumen_semanal = forms.BooleanField(required=False)
    distancia_maxima_km = forms.TypedChoiceField(coerce=int, choices=[(5, "5 km"), (10, "10 km"), (20, "20 km")])
    notificaciones_desde = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    notificaciones_hasta = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    modo_silencioso = forms.BooleanField(required=False)
    tamano_texto = forms.ChoiceField(choices=[("pequeno", "Pequeño"), ("mediano", "Mediano"), ("grande", "Grande")])
    subrayar_enlaces = forms.BooleanField(required=False)
    reducir_animaciones = forms.BooleanField(required=False)
    lectura_simplificada = forms.BooleanField(required=False)
    lectura_idioma = forms.ChoiceField(choices=[("es", "Español")])
    ocultar_datos_personales = forms.BooleanField(required=False)
    permitir_contacto_coordinacion = forms.BooleanField(required=False)
    permitir_contacto_usuarios = forms.BooleanField(required=False)
    ocultar_informacion_adicional = forms.BooleanField(required=False)
    avatar = forms.ImageField(required=False)

    def __init__(self, *args, usuario, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "form-check-input"
            else:
                campo.widget.attrs["class"] = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
        self.fields["telefono"].widget.attrs.update({"inputmode": "numeric", "maxlength": 15})
        self.fields["contacto_alternativo"].widget.attrs.update({"inputmode": "numeric", "maxlength": 15})
        self.fields["avatar"].widget.attrs.update({"accept": "image/png,image/jpeg"})
        if not self.is_bound:
            self.initial.update({"nombres": usuario.first_name, "apellidos": usuario.last_name,
                                 "telefono": perfil.telefono if perfil else ""})
            if perfil:
                self.initial.update({campo: getattr(perfil, campo) for campo in (
                    "fecha_nacimiento", "sector_aproximado", "contacto_alternativo",
                    "canal_preferido", "recibir_notificaciones", "alto_contraste", "informacion_adicional",
                    "idioma", "zona_horaria", "disponibilidad", "permitir_ubicacion_aproximada",
                    "compartir_ubicacion_atencion", "recibir_recordatorios", "recibir_mensajes",
                    "recibir_resumen_semanal", "distancia_maxima_km", "notificaciones_desde",
                    "notificaciones_hasta", "modo_silencioso", "tamano_texto", "subrayar_enlaces",
                    "reducir_animaciones", "lectura_simplificada", "lectura_idioma",
                    "ocultar_datos_personales", "permitir_contacto_coordinacion", "permitir_contacto_usuarios",
                    "ocultar_informacion_adicional",
                )})

    def clean_nombres(self):
        return RegistroForm._validar_nombre(self.cleaned_data["nombres"])

    def clean_apellidos(self):
        return RegistroForm._validar_nombre(self.cleaned_data["apellidos"])

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"]
        if not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa únicamente números: entre 8 y 15 dígitos.")
        return telefono

    def clean_contacto_alternativo(self):
        telefono = self.cleaned_data["contacto_alternativo"].strip()
        if telefono and not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa entre 8 y 15 dígitos o deja el campo vacío.")
        return telefono

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data["fecha_nacimiento"]
        if fecha and fecha > timezone.localdate():
            raise ValidationError("La fecha de nacimiento no puede ser futura.")
        return fecha

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("notificaciones_desde"), datos.get("notificaciones_hasta")
        if desde and hasta and desde >= hasta:
            self.add_error("notificaciones_hasta", "La hora final debe ser posterior a la inicial.")
        return datos

    def clean_avatar(self):
        imagen = self.cleaned_data.get("avatar")
        if imagen and (imagen.size > 2 * 1024 * 1024 or getattr(imagen, "content_type", "") not in {"image/png", "image/jpeg"}):
            raise ValidationError("La foto debe ser PNG o JPG y pesar como máximo 2 MB.")
        return imagen


