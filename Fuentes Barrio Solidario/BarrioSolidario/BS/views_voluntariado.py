"""Panel, catálogo cercano y postulación de voluntarios aprobados."""
import hmac
import logging
from smtplib import SMTPException
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.core.mail import EmailMultiAlternatives
from django.http import Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from .distancias import distancia_km
from .forms_voluntariado import PostulacionForm
from .models import PerfilUsuario, PostulacionVoluntario, SolicitudAsistencia, UsuarioRol
from .views_cuentas import _adjuntar_logo_uees

logger = logging.getLogger(__name__)


def notificar_resultado_postulacion(pk, request):
    try:
        postulacion = PostulacionVoluntario.objects.select_related("voluntario", "solicitud").get(pk=pk)
        if not postulacion.voluntario.email:
            return
        origen = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
        ruta = reverse("voluntario_postulaciones")
        enlace = f"{origen}{ruta}" if origen else request.build_absolute_uri(ruta)
        contexto = {"postulacion": postulacion, "enlace": enlace,
                    "nombre": postulacion.voluntario.first_name, "nota": postulacion.nota_revision}
        mensaje = EmailMultiAlternatives(
            subject=f"Resultado de postulación {postulacion.solicitud.codigo} | Barrio Solidario",
            body=render_to_string("voluntariado/correo_resultado.txt", contexto),
            from_email=settings.DEFAULT_FROM_EMAIL, to=[postulacion.voluntario.email])
        mensaje.attach_alternative(render_to_string("voluntariado/correo_resultado.html", contexto), "text/html")
        _adjuntar_logo_uees(mensaje)
        if mensaje.send(fail_silently=False) != 1:
            raise SMTPException("El servidor no confirmó el envío")
    except Exception:
        logger.exception("No se pudo notificar la postulación %s", pk)


def rol_voluntario(usuario):
    return usuario.is_authenticated and usuario.is_active and UsuarioRol.objects.filter(
        usuario=usuario, rol__codigo="VOLUNTARIO", rol__activo=True, activo=True,
        estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).exists()


def _perfil(request):
    if not rol_voluntario(request.user):
        raise PermissionDenied("Se requiere un rol de voluntario aprobado.")
    return PerfilUsuario.objects.filter(usuario=request.user, estado=PerfilUsuario.Estado.ACTIVA).first()


def _cercanas(request, perfil):
    if not perfil or not perfil.permitir_ubicacion_aproximada or perfil.latitud_ubicacion is None or perfil.longitud_ubicacion is None:
        return []
    qs = SolicitudAsistencia.objects.filter(estado=SolicitudAsistencia.Estado.APROBADA,
        fecha_requerida__gte=timezone.localdate(),
        latitud__isnull=False, longitud__isnull=False, consentimiento_ubicacion_en__isnull=False,
        solicitante__is_active=True).exclude(solicitante=request.user).select_related("tipo_ayuda", "prioridad")
    candidatos = []
    for solicitud in qs:
        km = distancia_km(perfil.latitud_ubicacion, perfil.longitud_ubicacion,
                          solicitud.latitud, solicitud.longitud)
        if km <= perfil.distancia_maxima_km:
            candidatos.append((solicitud, round(km, 1)))
    return sorted(candidatos, key=lambda item: item[1])[:100]


def _encontrar(request, codigo, perfil):
    if len(codigo) != 32 or any(c not in "0123456789abcdef" for c in codigo):
        return None
    return next(((s, km) for s, km in _cercanas(request, perfil)
                 if hmac.compare_digest(s.codigo_acceso, codigo)), None)


def _mapa_aproximado(candidatos):
    # Dos decimales (~1 km) para evitar publicar las coordenadas exactas del solicitante.
    return [{"lat": round(float(s.latitud), 2), "lon": round(float(s.longitud), 2),
             "codigo": s.codigo, "tipo": s.tipo_ayuda.nombre,
             "url": s.codigo_acceso, "km": km} for s, km in candidatos]


@login_required(login_url="acceso")
def panel_voluntario(request):
    perfil = _perfil(request)
    cercanas = _cercanas(request, perfil)
    propias = PostulacionVoluntario.objects.filter(voluntario=request.user).select_related("solicitud", "solicitud__tipo_ayuda")
    return render(request, "voluntariado/panel.html", {
        "perfil": perfil, "cercanas": cercanas[:12], "total_cercanas": len(cercanas),
        "puntos": _mapa_aproximado(cercanas),
        "postulaciones_pendientes": propias.filter(estado=PostulacionVoluntario.Estado.ENVIADA).count(),
        "postulaciones_aprobadas": propias.filter(estado=PostulacionVoluntario.Estado.APROBADA).count(),
        "postulaciones": propias[:5],
    })


@login_required(login_url="acceso")
def detalle_voluntario(request, codigo):
    perfil = _perfil(request)
    encontrada = _encontrar(request, codigo, perfil)
    if not encontrada:
        raise Http404("Solicitud no disponible en tu zona de cobertura.")
    solicitud, km = encontrada
    propia = PostulacionVoluntario.objects.filter(solicitud=solicitud, voluntario=request.user).first()
    otras = [(s, d) for s, d in _cercanas(request, perfil) if s.pk != solicitud.pk][:3]
    return render(request, "voluntariado/detalle.html", {"solicitud": solicitud, "distancia": km,
        "propia": propia, "otras": otras, "perfil": perfil,
        "punto": _mapa_aproximado([(solicitud, km)])[0]})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def postulacion(request, codigo):
    perfil = _perfil(request)
    encontrada = _encontrar(request, codigo, perfil)
    if not encontrada:
        raise Http404("Solicitud no disponible en tu zona de cobertura.")
    solicitud, km = encontrada
    propia = PostulacionVoluntario.objects.filter(solicitud=solicitud, voluntario=request.user).first()
    if propia and propia.estado not in (PostulacionVoluntario.Estado.BORRADOR,):
        messages.info(request, "Ya enviaste una postulación para esta solicitud.")
        return redirect("voluntario_detalle", codigo=codigo)
    inicial = {}
    if propia:
        inicial = {"puede_atender": "SI", "fecha_disponible": propia.fecha_disponible,
            "hora_desde": propia.hora_desde, "hora_hasta": propia.hora_hasta,
            "tiene_transporte": "SI" if propia.tiene_transporte else "NO", "mensaje": propia.mensaje}
    accion = request.POST.get("accion") if request.method == "POST" else None
    if request.method == "POST" and accion not in ("borrador", "enviar"):
        raise Http404("Acción no disponible")
    form = PostulacionForm(request.POST or None, initial=inicial, solicitud=solicitud, enviar=accion == "enviar")
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                actual, _ = PostulacionVoluntario.objects.select_for_update().get_or_create(
                    solicitud=solicitud, voluntario=request.user)
                # Revalidar después del bloqueo para impedir dos envíos concurrentes.
                if actual.estado != PostulacionVoluntario.Estado.BORRADOR or not _encontrar(request, codigo, perfil):
                    messages.warning(request, "Esta postulación ya fue enviada o la solicitud dejó de estar disponible.")
                    return redirect("voluntario_panel")
                actual.fecha_disponible = data["fecha_disponible"]
                actual.hora_desde = data["hora_desde"]
                actual.hora_hasta = data["hora_hasta"]
                actual.tiene_transporte = data["tiene_transporte"] == "SI"
                actual.mensaje = data["mensaje"]
                if accion == "enviar":
                    actual.estado = PostulacionVoluntario.Estado.ENVIADA
                    actual.confirmado_en = timezone.now()
                    actual.acepto_revision_en = timezone.now()
                    actual.enviada_en = timezone.now()
                actual.save()
        except IntegrityError:
            messages.warning(request, "La postulación ya fue registrada. Consulta su estado.")
            return redirect("voluntario_panel")
        messages.success(request, "Postulación enviada para revisión." if accion == "enviar" else "Borrador de postulación guardado.")
        return redirect("voluntario_postulaciones")
    return render(request, "voluntariado/postulacion.html", {"solicitud": solicitud, "distancia": km,
        "punto": _mapa_aproximado([(solicitud, km)])[0], "perfil": perfil, "form": form})


@login_required(login_url="acceso")
def mis_postulaciones(request):
    _perfil(request)
    postulaciones = PostulacionVoluntario.objects.filter(voluntario=request.user).select_related(
        "solicitud", "solicitud__tipo_ayuda")
    return render(request, "voluntariado/mis_postulaciones.html", {"postulaciones": postulaciones})
