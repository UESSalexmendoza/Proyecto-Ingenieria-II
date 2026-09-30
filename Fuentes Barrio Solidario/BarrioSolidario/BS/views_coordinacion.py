"""Bandeja de coordinación, revisión de postulaciones y asignación segura."""
import logging
from smtplib import SMTPException
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from .distancias import distancia_km
from .forms_coordinacion import AsignacionForm, DecisionSolicitudForm
from .models import (ActuacionSolicitud, AsignacionAsistencia, PerfilUsuario,
                     PostulacionVoluntario, SolicitudAsistencia, UsuarioRol)
from .views_cuentas import _adjuntar_logo_uees
from .views_solicitudes import _es_revisor, revisar_solicitud
from .views_voluntariado import notificar_resultado_postulacion

logger = logging.getLogger(__name__)


def _permiso(request):
    if not _es_revisor(request.user):
        raise PermissionDenied("Se requiere un rol de coordinación aprobado.")


def _aviso_asignacion(asignacion_id, request):
    a = AsignacionAsistencia.objects.select_related("solicitud__solicitante", "postulacion__voluntario").get(pk=asignacion_id)
    for usuario, destino in ((a.postulacion.voluntario, "voluntario"),
                             (a.solicitud.solicitante, "solicitante")):
        if not usuario.email:
            continue
        ruta = reverse("voluntario_postulaciones" if destino == "voluntario" else "solicitud_detalle",
                       kwargs={} if destino == "voluntario" else {"codigo": a.solicitud.codigo_acceso})
        origen = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
        contexto = {"asignacion": a, "destino": destino, "nombre": usuario.first_name,
                    "enlace": f"{origen}{ruta}" if origen else request.build_absolute_uri(ruta)}
        try:
            correo = EmailMultiAlternatives(
                subject=f"Coordinación de asistencia {a.solicitud.codigo} | Barrio Solidario",
                body=render_to_string("coordinacion/correo_asignacion.txt", contexto),
                from_email=settings.DEFAULT_FROM_EMAIL, to=[usuario.email])
            correo.attach_alternative(render_to_string("coordinacion/correo_asignacion.html", contexto), "text/html")
            _adjuntar_logo_uees(correo)
            if correo.send(fail_silently=False) != 1:
                raise SMTPException("El servidor no confirmó el envío")
        except Exception:
            logger.exception("Falló aviso de asignación %s a %s", asignacion_id, destino)


def _aviso_cierre(solicitud_id, nota, request):
    solicitud = SolicitudAsistencia.objects.select_related("solicitante").get(pk=solicitud_id)
    if not solicitud.solicitante.email:
        return
    ruta = reverse("solicitud_detalle", kwargs={"codigo": solicitud.codigo_acceso})
    origen = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    contexto = {"solicitud": solicitud, "nota": nota, "nombre": solicitud.solicitante.first_name,
                "enlace": f"{origen}{ruta}" if origen else request.build_absolute_uri(ruta)}
    try:
        correo = EmailMultiAlternatives(
            subject=f"Actualización de solicitud {solicitud.codigo} | Barrio Solidario",
            body=render_to_string("solicitudes/correo_estado.txt", contexto),
            from_email=settings.DEFAULT_FROM_EMAIL, to=[solicitud.solicitante.email])
        correo.attach_alternative(render_to_string("solicitudes/correo_estado.html", contexto), "text/html")
        _adjuntar_logo_uees(correo)
        if correo.send(fail_silently=False) != 1:
            raise SMTPException("El servidor no confirmó el envío")
    except Exception:
        logger.exception("Falló aviso de cierre de solicitud %s", solicitud_id)


@login_required(login_url="acceso")
def panel_coordinacion(request):
    _permiso(request)
    solicitudes = SolicitudAsistencia.objects.select_related("tipo_ayuda", "prioridad").annotate(
        total_postulaciones=Count("postulaciones", filter=Q(postulaciones__estado=PostulacionVoluntario.Estado.ENVIADA)))
    asignaciones = AsignacionAsistencia.objects.select_related("solicitud", "postulacion__voluntario")
    puntos = [{"lat": round(float(s.latitud), 2), "lon": round(float(s.longitud), 2),
               "codigo": s.codigo, "tipo": s.tipo_ayuda.nombre,
               "url": reverse("solicitud_revision", kwargs={"pk": s.pk})}
              for s in solicitudes.filter(estado__in=[SolicitudAsistencia.Estado.EN_REVISION,
                  SolicitudAsistencia.Estado.APROBADA], latitud__isnull=False,
                  longitud__isnull=False).order_by("-creado_en")[:80]]
    return render(request, "coordinacion/panel.html", {
        "puntos": puntos,
        "nuevas": solicitudes.filter(estado=SolicitudAsistencia.Estado.EN_REVISION).count(),
        "por_asignar": solicitudes.filter(estado=SolicitudAsistencia.Estado.APROBADA, asignacion__isnull=True).count(),
        "en_atencion": asignaciones.filter(estado=AsignacionAsistencia.Estado.EN_ATENCION).count(),
        "cierres": asignaciones.filter(estado=AsignacionAsistencia.Estado.CIERRE_PENDIENTE).count(),
        "pendientes": solicitudes.filter(estado=SolicitudAsistencia.Estado.APROBADA,
                                        asignacion__isnull=True).order_by("creado_en")[:5],
        "revisar": solicitudes.filter(estado=SolicitudAsistencia.Estado.EN_REVISION).order_by("creado_en")[:4],
        "asignaciones": asignaciones[:5],
    })


@login_required(login_url="acceso")
def bandeja_coordinacion(request):
    _permiso(request)
    qs = SolicitudAsistencia.objects.select_related("tipo_ayuda", "prioridad").annotate(
        total_postulaciones=Count("postulaciones", filter=Q(postulaciones__estado=PostulacionVoluntario.Estado.ENVIADA)))
    estado = request.GET.get("estado", "")[:20]
    if estado in SolicitudAsistencia.Estado.values:
        qs = qs.filter(estado=estado)
    busqueda = request.GET.get("q", "").strip()[:80]
    if busqueda:
        filtro = Q(tipo_ayuda__nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda)
        if busqueda.startswith("SOL-") and busqueda[9:].isdigit():
            filtro |= Q(pk=int(busqueda[9:]))
        qs = qs.filter(filtro)
    pagina = Paginator(qs, 10).get_page(request.GET.get("page"))
    return render(request, "coordinacion/bandeja.html", {
        "pagina": pagina, "estado": estado, "busqueda": busqueda,
        "nuevas": SolicitudAsistencia.objects.filter(estado=SolicitudAsistencia.Estado.EN_REVISION).count(),
        "por_asignar": SolicitudAsistencia.objects.filter(estado=SolicitudAsistencia.Estado.APROBADA,
                                                         asignacion__isnull=True).count(),
        "observadas": SolicitudAsistencia.objects.filter(estado=SolicitudAsistencia.Estado.OBSERVADA).count(),
    })


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def decision_coordinacion(request, pk):
    _permiso(request)
    solicitud = get_object_or_404(SolicitudAsistencia.objects.select_related("tipo_ayuda", "prioridad"), pk=pk)
    form = DecisionSolicitudForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        # La vista de revisión existente registra la decisión y notifica al solicitante.
        return revisar_solicitud(request, pk)
    return render(request, "coordinacion/decision.html", {"solicitud": solicitud, "form": form})


@login_required(login_url="acceso")
def postulaciones_coordinacion(request, pk):
    _permiso(request)
    solicitud = get_object_or_404(SolicitudAsistencia.objects.select_related("tipo_ayuda", "prioridad"), pk=pk)
    posts = PostulacionVoluntario.objects.filter(solicitud=solicitud).exclude(
        estado=PostulacionVoluntario.Estado.BORRADOR).select_related("voluntario", "voluntario__perfil_barrio")
    filas = []
    for post in posts:
        perfil = getattr(post.voluntario, "perfil_barrio", None)
        km = None
        if perfil and perfil.latitud_ubicacion is not None and perfil.longitud_ubicacion is not None and solicitud.latitud is not None:
            km = round(distancia_km(perfil.latitud_ubicacion, perfil.longitud_ubicacion,
                                    solicitud.latitud, solicitud.longitud), 1)
        filas.append((post, km))
    return render(request, "coordinacion/postulaciones.html", {"solicitud": solicitud,
        "postulaciones": filas, "asignacion": AsignacionAsistencia.objects.filter(solicitud=solicitud).first()})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def revisar_postulacion(request, pk):
    _permiso(request)
    post = get_object_or_404(PostulacionVoluntario.objects.select_related(
        "solicitud__tipo_ayuda", "voluntario", "voluntario__perfil_barrio"), pk=pk)
    if request.method == "POST":
        estado = request.POST.get("estado")
        nota = " ".join(request.POST.get("nota", "").split())
        if estado not in (post.Estado.APROBADA, post.Estado.RECHAZADA) or len(nota) < 10 or len(nota) > 300 or "<" in nota or ">" in nota or request.POST.get("confirma") != "on":
            messages.error(request, "Elige aprobar o rechazar, escribe una nota válida de 10 a 300 caracteres y confirma la revisión.")
        else:
            with transaction.atomic():
                actual = PostulacionVoluntario.objects.select_for_update().select_related("voluntario").get(pk=post.pk)
                if actual.estado != actual.Estado.ENVIADA or actual.solicitud.estado != SolicitudAsistencia.Estado.APROBADA:
                    messages.warning(request, "La postulación o la solicitud cambió de estado.")
                    return redirect("coord_postulacion", pk=pk)
                if (not actual.voluntario.is_active or not UsuarioRol.objects.filter(
                    usuario=actual.voluntario, rol__codigo="VOLUNTARIO", rol__activo=True, activo=True,
                    estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).exists() or not PerfilUsuario.objects.filter(
                    usuario=actual.voluntario, estado=PerfilUsuario.Estado.ACTIVA).exists()):
                    messages.error(request, "El perfil de voluntariado debe continuar activo y aprobado.")
                    return redirect("coord_postulacion", pk=pk)
                actual.estado, actual.nota_revision = estado, nota
                actual.revisado_por, actual.revisado_en = request.user, timezone.now()
                actual.save(update_fields=["estado", "nota_revision", "revisado_por", "revisado_en", "actualizado_en"])
                ActuacionSolicitud.objects.create(solicitud=actual.solicitud, actor=request.user,
                    accion="POSTULACION", descripcion=f"Postulación revisada: {actual.get_estado_display()}." )
                transaction.on_commit(lambda: notificar_resultado_postulacion(actual.pk, request))
            messages.success(request, "Revisión guardada. Se intentará notificar al voluntario por correo.")
            return redirect("coord_postulaciones", pk=post.solicitud_id)
    return render(request, "coordinacion/postulacion_detalle.html", {"post": post})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def asignar_voluntario(request, pk):
    _permiso(request)
    solicitud = get_object_or_404(SolicitudAsistencia.objects.select_related("tipo_ayuda", "prioridad"), pk=pk)
    posts = list(PostulacionVoluntario.objects.filter(solicitud=solicitud,
        estado=PostulacionVoluntario.Estado.APROBADA, voluntario__is_active=True,
        voluntario__perfil_barrio__estado=PerfilUsuario.Estado.ACTIVA,
        voluntario__roles_barrio__rol__codigo="VOLUNTARIO", voluntario__roles_barrio__rol__activo=True,
        voluntario__roles_barrio__activo=True,
        voluntario__roles_barrio__estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).select_related("voluntario").distinct())
    form = AsignacionForm(request.POST or None, postulaciones=posts)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                s = SolicitudAsistencia.objects.select_for_update().get(pk=pk)
                if s.estado != SolicitudAsistencia.Estado.APROBADA or AsignacionAsistencia.objects.filter(solicitud=s).exists():
                    messages.warning(request, "La solicitud ya no está disponible para asignación.")
                    return redirect("coord_bandeja")
                p = PostulacionVoluntario.objects.select_for_update().get(pk=int(form.cleaned_data["postulacion"]))
                if p.solicitud_id != s.pk or p.estado != p.Estado.APROBADA:
                    messages.error(request, "La postulación ya no está disponible.")
                    return redirect("coord_postulaciones", pk=pk)
                if not p.voluntario.is_active or not PerfilUsuario.objects.filter(
                    usuario=p.voluntario, estado=PerfilUsuario.Estado.ACTIVA).exists() or not UsuarioRol.objects.filter(usuario=p.voluntario, rol__codigo="VOLUNTARIO",
                    rol__activo=True, activo=True, estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).exists():
                    messages.error(request, "El rol del voluntario dejó de estar aprobado.")
                    return redirect("coord_postulaciones", pk=pk)
                d = form.cleaned_data
                asignacion = AsignacionAsistencia.objects.create(solicitud=s, postulacion=p,
                    coordinador=request.user, fecha_atencion=d["fecha_atencion"],
                    hora_inicio=d["hora_inicio"], hora_fin=d["hora_fin"],
                    instrucciones_voluntario=d["instrucciones_voluntario"],
                    instrucciones_solicitante=d["instrucciones_solicitante"], nota_interna=d["nota_interna"])
                ActuacionSolicitud.objects.create(solicitud=s, actor=request.user,
                    accion="ASIGNACION", descripcion="Coordinación asignó un voluntario y programó la atención.")
                otros = list(PostulacionVoluntario.objects.select_for_update().filter(solicitud=s,
                    estado__in=[PostulacionVoluntario.Estado.ENVIADA, PostulacionVoluntario.Estado.APROBADA])
                    .exclude(pk=p.pk))
                for otro in otros:
                    otro.estado = PostulacionVoluntario.Estado.NO_SELECCIONADA
                    otro.nota_revision = "La solicitud fue asignada a otra persona. Gracias por tu disposición."
                    otro.revisado_por = request.user
                    otro.revisado_en = timezone.now()
                    otro.save(update_fields=["estado", "nota_revision", "revisado_por", "revisado_en", "actualizado_en"])
                    transaction.on_commit(lambda oid=otro.pk: notificar_resultado_postulacion(oid, request))
                transaction.on_commit(lambda: _aviso_asignacion(asignacion.pk, request))
        except IntegrityError:
            messages.error(request, "Otra persona registró la asignación. Actualiza la bandeja.")
            return redirect("coord_bandeja")
        messages.success(request, "Voluntario asignado. Se enviarán los avisos de coordinación.")
        return redirect("coord_asignacion_detalle", pk=asignacion.pk)
    return render(request, "coordinacion/asignar.html", {"solicitud": solicitud, "postulaciones": posts,
        "form": form, "asignacion": AsignacionAsistencia.objects.filter(solicitud=solicitud).first()})


@login_required(login_url="acceso")
def asignaciones_coordinacion(request):
    _permiso(request)
    pagina = Paginator(AsignacionAsistencia.objects.select_related(
        "solicitud__tipo_ayuda", "postulacion__voluntario"), 10).get_page(request.GET.get("page"))
    return render(request, "coordinacion/asignaciones.html", {"pagina": pagina})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def asignacion_detalle(request, pk):
    _permiso(request)
    asignacion = get_object_or_404(AsignacionAsistencia.objects.select_related(
        "solicitud__tipo_ayuda", "postulacion__voluntario"), pk=pk)
    siguientes = {AsignacionAsistencia.Estado.ASIGNADA: AsignacionAsistencia.Estado.EN_ATENCION,
        AsignacionAsistencia.Estado.EN_ATENCION: AsignacionAsistencia.Estado.CIERRE_PENDIENTE,
        AsignacionAsistencia.Estado.CIERRE_PENDIENTE: AsignacionAsistencia.Estado.COMPLETADA}
    if request.method == "POST":
        nota = " ".join(request.POST.get("nota", "").split())
        if len(nota) < 10 or len(nota) > 300 or "<" in nota or ">" in nota:
            messages.error(request, "Indica una nota de 10 a 300 caracteres sin HTML.")
        else:
            with transaction.atomic():
                a = AsignacionAsistencia.objects.select_for_update().select_related("solicitud").get(pk=pk)
                nuevo = siguientes.get(a.estado)
                if not nuevo or request.POST.get("nuevo_estado") != nuevo:
                    messages.error(request, "La transición de estado no está disponible.")
                    return redirect("coord_asignacion_detalle", pk=pk)
                a.estado = nuevo
                if nuevo == a.Estado.COMPLETADA:
                    a.cierre_en = timezone.now()
                    a.solicitud.estado = SolicitudAsistencia.Estado.COMPLETADA
                    a.solicitud.save(update_fields=["estado", "actualizado_en"])
                    transaction.on_commit(lambda: _aviso_cierre(a.solicitud_id, nota, request))
                a.save()
                ActuacionSolicitud.objects.create(solicitud=a.solicitud, actor=request.user,
                    accion="ATENCION", descripcion=f"{a.get_estado_display()}: {nota}"[:350])
            messages.success(request, "Estado de atención actualizado.")
            return redirect("coord_asignacion_detalle", pk=pk)
    return render(request, "coordinacion/asignacion_detalle.html", {
        "asignacion": asignacion, "siguiente": siguientes.get(asignacion.estado)})
