"""Cambios de estado, trazabilidad y notificaciones al remitente."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import ActuacionContacto, CasoContacto

logger = logging.getLogger(__name__)


def _enviar_estado(caso, request):
    enlace = request.build_absolute_uri(reverse("inicio"))
    contexto = {"nombre": caso.nombre, "referencia": caso.pk,
                "estado": caso.get_estado_display(), "nota": caso.nota_revision,
                "enlace": enlace}
    correo = EmailMultiAlternatives(
        subject=f"Actualización del caso #{caso.pk} | Barrio Solidario",
        body=(f"Hola {caso.nombre}:\n\nHay una actualización de tu caso #{caso.pk}. "
              f"Su estado actual es: {caso.get_estado_display()}.\n\n"
              + (f"Nota del equipo:\n{caso.nota_revision}\n\n" if caso.nota_revision else "")
              + "Equipo Barrio Solidario"),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[caso.email],
    )
    correo.attach_alternative(render_to_string("contacto/correo_estado_contacto.html", contexto), "text/html")
    from .views_cuentas import _adjuntar_logo_uees
    _adjuntar_logo_uees(correo)
    correo.send(fail_silently=False)


def guardar_revision(caso_id, *, actor, nuevo_estado, nota, request):
    """Guarda la actuación antes del SMTP y deja el fallo visible para reintentar."""
    with transaction.atomic():
        caso = CasoContacto.objects.select_for_update().get(pk=caso_id)
        cambio_estado = caso.estado != nuevo_estado
        cambio_nota = caso.nota_revision != nota
        pendiente_anterior = caso.notificacion_estado_pendiente
        if not (cambio_estado or cambio_nota or pendiente_anterior):
            return False, None
        anterior = caso.estado
        if cambio_estado or cambio_nota:
            caso.estado = nuevo_estado
            caso.nota_revision = nota
            caso.revisado_por = actor
            caso.revisado_en = timezone.now()
        if cambio_estado or cambio_nota:
            caso.notificacion_estado_pendiente = True
        caso.save(update_fields=["estado", "nota_revision", "revisado_por", "revisado_en",
                                 "notificacion_estado_pendiente"])
        enviar = caso.notificacion_estado_pendiente
        actuacion = ActuacionContacto.objects.create(
            caso=caso, actor=actor,
            tipo=ActuacionContacto.Tipo.REVISION if cambio_estado or cambio_nota else ActuacionContacto.Tipo.REINTENTO,
            estado_anterior=anterior, estado_nuevo=caso.estado,
            nota=nota if cambio_estado or cambio_nota else "",
            resultado_correo=ActuacionContacto.Correo.PENDIENTE if enviar else ActuacionContacto.Correo.NO_APLICA,
        )
    if not enviar:
        return True, None
    try:
        _enviar_estado(caso, request)
    except Exception:
        logger.exception("No se pudo notificar el estado del caso %s", caso.pk)
        actuacion.resultado_correo = ActuacionContacto.Correo.FALLIDO
        actuacion.save(update_fields=["resultado_correo"])
        return True, False
    CasoContacto.objects.filter(pk=caso.pk, estado=caso.estado).update(
        notificacion_estado_pendiente=False, estado_notificado_en=timezone.now()
    )
    actuacion.resultado_correo = ActuacionContacto.Correo.ENVIADO
    actuacion.save(update_fields=["resultado_correo"])
    return True, True
