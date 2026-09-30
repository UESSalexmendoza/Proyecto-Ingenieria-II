"""Formularios para revisión y asignación de coordinación."""
from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import SolicitudAsistencia


class DecisionSolicitudForm(forms.Form):
    estado = forms.ChoiceField(choices=(
        ("", "Selecciona un resultado"),
        (SolicitudAsistencia.Estado.APROBADA, "Aprobar para asignación"),
        (SolicitudAsistencia.Estado.OBSERVADA, "Solicitar corrección"),
        (SolicitudAsistencia.Estado.RECHAZADA, "Rechazar solicitud"),
    ), widget=forms.RadioSelect)
    nota = forms.CharField(min_length=10, max_length=300,
                           widget=forms.Textarea(attrs={"class": "form-control", "rows": 4, "maxlength": 300}))
    confirma = forms.BooleanField(error_messages={"required": "Confirma que revisaste los datos de la solicitud."})

    def clean_nota(self):
        valor = " ".join(self.cleaned_data["nota"].split())
        if "<" in valor or ">" in valor:
            raise ValidationError("No se permite código HTML.")
        if len(valor) < 10:
            raise ValidationError("Escribe al menos 10 caracteres.")
        return valor


class AsignacionForm(forms.Form):
    postulacion = forms.ChoiceField(choices=())
    fecha_atencion = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    hora_inicio = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}))
    hora_fin = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}))
    instrucciones_voluntario = forms.CharField(min_length=10, max_length=400,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control", "maxlength": 400}))
    instrucciones_solicitante = forms.CharField(min_length=10, max_length=400,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control", "maxlength": 400}))
    nota_interna = forms.CharField(max_length=400, required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "maxlength": 400}))
    confirma = forms.BooleanField(error_messages={"required": "Confirma la asignación."})

    def __init__(self, *args, postulaciones=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.postulaciones = {str(p.pk): p for p in postulaciones}
        self.fields["postulacion"].choices = [("", "Selecciona voluntario aprobado")] + [
            (str(p.pk), f"{p.voluntario.get_full_name() or p.voluntario.username} · {p.fecha_disponible:%d/%m/%Y}")
            for p in postulaciones]
        self.fields["postulacion"].widget.attrs["class"] = "form-select"

    def clean_fecha_atencion(self):
        fecha = self.cleaned_data["fecha_atencion"]
        if fecha < timezone.localdate() or fecha > timezone.localdate() + timedelta(days=365):
            raise ValidationError("Selecciona una fecha desde hoy hasta un año en adelante.")
        return fecha

    def clean(self):
        d = super().clean()
        post = self.postulaciones.get(d.get("postulacion"))
        if post and d.get("fecha_atencion") and post.fecha_disponible != d["fecha_atencion"]:
            self.add_error("fecha_atencion", "La fecha debe coincidir con la disponibilidad ofrecida por el voluntario.")
        if post and d.get("hora_inicio") and d.get("hora_fin"):
            if d["hora_inicio"] >= d["hora_fin"]:
                self.add_error("hora_fin", "La hora final debe ser posterior a la inicial.")
            elif d["hora_inicio"] < post.hora_desde or d["hora_fin"] > post.hora_hasta:
                self.add_error("hora_inicio", "El horario debe estar dentro de la disponibilidad ofrecida.")
        for campo in ("instrucciones_voluntario", "instrucciones_solicitante", "nota_interna"):
            valor = d.get(campo, "")
            if "<" in valor or ">" in valor:
                self.add_error(campo, "No se permite código HTML.")
            elif valor:
                d[campo] = " ".join(valor.split())
        return d
