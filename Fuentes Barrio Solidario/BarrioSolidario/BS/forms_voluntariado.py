"""Validaciones del flujo de postulación."""
from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone


class PostulacionForm(forms.Form):
    puede_atender = forms.ChoiceField(choices=(("SI", "Sí"), ("NO", "No")), widget=forms.RadioSelect)
    fecha_disponible = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    hora_desde = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}))
    hora_hasta = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}))
    tiene_transporte = forms.ChoiceField(choices=(("SI", "Sí"), ("NO", "No")), widget=forms.RadioSelect)
    mensaje = forms.CharField(min_length=10, max_length=400, widget=forms.Textarea(attrs={"rows": 4, "maxlength": 400, "class": "form-control"}))
    confirmo = forms.BooleanField(required=False)
    acepto_revision = forms.BooleanField(required=False)

    def __init__(self, *args, solicitud=None, enviar=True, **kwargs):
        self.solicitud = solicitud
        self.enviar = enviar
        super().__init__(*args, **kwargs)

    def clean_mensaje(self):
        texto = " ".join(self.cleaned_data["mensaje"].split())
        if "<" in texto or ">" in texto:
            raise ValidationError("No se permite código HTML en el mensaje.")
        if len(texto) < 10:
            raise ValidationError("Escribe al menos 10 caracteres.")
        return texto

    def clean(self):
        data = super().clean()
        inicio, fin = data.get("hora_desde"), data.get("hora_hasta")
        if inicio and fin and inicio >= fin:
            self.add_error("hora_hasta", "El horario de fin debe ser posterior al de inicio.")
        fecha = data.get("fecha_disponible")
        if fecha and (fecha < timezone.localdate() or fecha > timezone.localdate() + timedelta(days=365)):
            self.add_error("fecha_disponible", "Elige una fecha desde hoy hasta un año en adelante.")
        if self.enviar:
            if data.get("puede_atender") != "SI":
                self.add_error("puede_atender", "Para enviar la postulación debes confirmar que puedes atender la solicitud.")
            if not data.get("confirmo"):
                self.add_error("confirmo", "Confirma que tus datos son correctos.")
            if not data.get("acepto_revision"):
                self.add_error("acepto_revision", "Autoriza la revisión de tu postulación.")
        return data
