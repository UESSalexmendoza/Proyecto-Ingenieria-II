"""Campos y reglas del formulario del solicitante."""
import re
from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import SolicitudAsistencia, ValorCatalogo

CATALOGO_TIPOS = "TIPOS_AYUDA"
CATALOGO_PRIORIDADES = "PRIORIDADES"


def opciones(codigo):
    return ValorCatalogo.objects.filter(catalogo__codigo=codigo, catalogo__activo=True,
        activo=True, disponible_nuevas=True).select_related("catalogo").order_by("orden", "pk")


class SolicitudAsistenciaForm(forms.Form):
    destinatario = forms.ChoiceField(
        choices=SolicitudAsistencia.Destinatario.choices,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )
    tipo_ayuda = forms.ModelChoiceField(queryset=ValorCatalogo.objects.none(), empty_label="Selecciona el tipo de ayuda")
    prioridad = forms.ModelChoiceField(queryset=ValorCatalogo.objects.none(), empty_label="Selecciona la prioridad")
    fecha_requerida = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    descripcion = forms.CharField(min_length=15, max_length=500, widget=forms.Textarea(attrs={"rows": 4, "maxlength": 500}))
    sector_referencia = forms.CharField(min_length=5, max_length=160)
    latitud = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitud = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)
    consiente_ubicacion = forms.BooleanField(required=False)
    persona_contacto = forms.CharField(min_length=2, max_length=120)
    telefono_contacto = forms.CharField(min_length=8, max_length=15)
    correo_contacto = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    disponibilidad = forms.MultipleChoiceField(choices=(("MANANA", "Mañana"), ("TARDE", "Tarde"), ("NOCHE", "Noche")), widget=forms.CheckboxSelectMultiple)
    observaciones = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2, "maxlength": 500}))
    confirmacion = forms.BooleanField(required=False)
    acepta_tratamiento = forms.BooleanField(required=False)

    def __init__(self, *args, usuario=None, requiere_confirmacion=True, **kwargs):
        self.usuario = usuario
        self.requiere_confirmacion = requiere_confirmacion
        super().__init__(*args, **kwargs)
        self.fields["tipo_ayuda"].queryset = opciones(CATALOGO_TIPOS)
        self.fields["prioridad"].queryset = opciones(CATALOGO_PRIORIDADES)
        for nombre, campo in self.fields.items():
            if nombre in ("disponibilidad", "destinatario", "confirmacion", "acepta_tratamiento", "consiente_ubicacion"):
                continue
            campo.widget.attrs.setdefault("class", "form-select" if isinstance(campo.widget, forms.Select) else "form-control")

    def clean_destinatario(self):
        valor = self.cleaned_data["destinatario"]
        if valor == SolicitudAsistencia.Destinatario.ADULTO_CUIDADO:
            from .models import UsuarioRol
            if not self.usuario or not UsuarioRol.objects.filter(usuario=self.usuario, rol__codigo="FAMILIAR_CUIDADOR",
                rol__activo=True, activo=True, estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).exists():
                raise ValidationError("Esta opción requiere el rol de familiar/cuidador aprobado.")
        return valor

    def clean_fecha_requerida(self):
        fecha = self.cleaned_data["fecha_requerida"]
        hoy = timezone.localdate()
        if fecha < hoy or fecha > hoy + timedelta(days=365):
            raise ValidationError("Selecciona una fecha desde hoy hasta un año en adelante.")
        return fecha

    def clean_persona_contacto(self):
        nombre = " ".join(self.cleaned_data["persona_contacto"].split())
        if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:[ '\-][A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*", nombre):
            raise ValidationError("Escribe un nombre de contacto válido, sin números ni código HTML.")
        return nombre

    def clean_telefono_contacto(self):
        telefono = self.cleaned_data["telefono_contacto"].strip()
        if not re.fullmatch(r"[0-9]{8,15}", telefono):
            raise ValidationError("Ingresa únicamente entre 8 y 15 dígitos.")
        return telefono

    def clean_disponibilidad(self):
        dias = self.cleaned_data["disponibilidad"]
        if not dias:
            raise ValidationError("Selecciona al menos un horario.")
        return dias

    def clean(self):
        d = super().clean()
        for campo in ("descripcion", "sector_referencia", "observaciones"):
            valor = d.get(campo, "")
            if "<" in valor or ">" in valor:
                self.add_error(campo, "No se permite código HTML.")
            elif valor:
                d[campo] = " ".join(valor.split())
        if (d.get("latitud") is None) != (d.get("longitud") is None):
            self.add_error("latitud", "Selecciona una ubicación válida en el mapa.")
        if not d.get("consiente_ubicacion"):
            self.add_error("consiente_ubicacion", "Autoriza el uso de esta ubicación para coordinar la asistencia.")
        if self.requiere_confirmacion:
            if not d.get("confirmacion"):
                self.add_error("confirmacion", "Confirma que los datos son correctos.")
            if not d.get("acepta_tratamiento"):
                self.add_error("acepta_tratamiento", "Debes aceptar el tratamiento de datos de esta solicitud.")
        return d


class SolicitudEdicionForm(SolicitudAsistenciaForm):
    """Edición acotada de la petición; preserva contacto y punto geográfico originales."""

    def __init__(self, *args, **kwargs):
        kwargs["requiere_confirmacion"] = False
        super().__init__(*args, **kwargs)
        for nombre in ("latitud", "longitud", "persona_contacto", "telefono_contacto",
                       "correo_contacto", "consiente_ubicacion", "confirmacion", "acepta_tratamiento"):
            self.fields.pop(nombre)

    def clean(self):
        d = forms.Form.clean(self)
        for campo in ("descripcion", "sector_referencia", "observaciones"):
            valor = d.get(campo, "")
            if "<" in valor or ">" in valor:
                self.add_error(campo, "No se permite código HTML.")
            elif valor:
                d[campo] = " ".join(valor.split())
        return d


class CancelacionSolicitudForm(forms.Form):
    motivo = forms.ChoiceField(choices=(("", "Selecciona un motivo"),
        ("YA_NO_REQUIERE", "Ya no necesito la ayuda"),
        ("RESUELTA", "La necesidad fue resuelta"),
        ("ERROR", "Registré datos incorrectos"),
        ("OTRO", "Otro motivo")), widget=forms.Select(attrs={"class": "form-select"}))
    comentario = forms.CharField(min_length=10, max_length=220,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 220, "class": "form-control"}))
    confirma = forms.BooleanField(widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        error_messages={"required": "Confirma que deseas cancelar esta solicitud."})

    def clean_comentario(self):
        valor = " ".join(self.cleaned_data["comentario"].split())
        if "<" in valor or ">" in valor:
            raise ValidationError("No se permite código HTML.")
        if len(valor) < 10:
            raise ValidationError("Explica el motivo en al menos 10 caracteres.")
        return valor
