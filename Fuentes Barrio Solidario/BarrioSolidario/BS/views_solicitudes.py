"""Panel del solicitante y registro de solicitudes con confirmación por correo."""
import logging
import hmac
from smtplib import SMTPException
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.http import Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from .forms_solicitudes import SolicitudAsistenciaForm, SolicitudEdicionForm, CancelacionSolicitudForm, opciones, CATALOGO_TIPOS, CATALOGO_PRIORIDADES
from .models import ActuacionSolicitud, PerfilUsuario, SolicitudAsistencia, UsuarioRol
from .views_cuentas import _adjuntar_logo_uees

logger = logging.getLogger(__name__)
ROLES_SOLICITANTES = ("ADULTO_MAYOR", "FAMILIAR_CUIDADOR", "SOLICITANTE")


def tiene_rol_solicitante(usuario, aprobado=False):
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    asignaciones = UsuarioRol.objects.filter(usuario=usuario, rol__codigo__in=ROLES_SOLICITANTES,
                                              rol__activo=True, activo=True)
    if aprobado:
        asignaciones = asignaciones.filter(estado_aprobacion=UsuarioRol.Aprobacion.APROBADO)
    return asignaciones.exists()


def _permiso(request, enviar=False):
    if not tiene_rol_solicitante(request.user):
        raise PermissionDenied("Esta sección corresponde a las cuentas solicitantes.")
    if enviar and (not tiene_rol_solicitante(request.user, aprobado=True) or
                  not PerfilUsuario.objects.filter(usuario=request.user, estado=PerfilUsuario.Estado.ACTIVA).exists()):
        raise PermissionDenied("Tu rol de solicitante debe estar aprobado para enviar una solicitud.")


def _buscar_solicitud_propia(request, codigo):
    """Resuelve el código dentro de las solicitudes del titular, sin distinguir si existe en otra cuenta."""
    if len(codigo) != 32 or any(c not in "0123456789abcdef" for c in codigo):
        return None
    candidatas = SolicitudAsistencia.objects.filter(solicitante=request.user).select_related("tipo_ayuda", "prioridad")
    return next((s for s in candidatas if hmac.compare_digest(s.codigo_acceso, codigo)), None)


def _no_disponible(request):
    return render(request, "solicitudes/no_disponible.html", status=404)


@login_required(login_url="acceso")
def solicitud_no_disponible(request, pk):
    return _no_disponible(request)


def _notificar(solicitud, request):
    correo = solicitud.solicitante.email.strip()
    if not correo:
        raise ValueError("La cuenta no tiene un correo de contacto configurado.")
    url = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    ruta = reverse("solicitud_detalle", kwargs={"codigo": solicitud.codigo_acceso})
    enlace = f"{url}{ruta}" if url else request.build_absolute_uri(ruta)
    contexto = {"solicitud": solicitud, "nombre": solicitud.solicitante.first_name,
                "enlace": enlace}
    mensaje = EmailMultiAlternatives(
        subject=f"Recibimos tu solicitud {solicitud.codigo} | Barrio Solidario",
        body=render_to_string("solicitudes/correo_confirmacion.txt", contexto),
        from_email=settings.DEFAULT_FROM_EMAIL, to=[correo],
    )
    mensaje.attach_alternative(render_to_string("solicitudes/correo_confirmacion.html", contexto), "text/html")
    _adjuntar_logo_uees(mensaje)
    if mensaje.send(fail_silently=False) != 1:
        raise SMTPException("El servidor no aceptó el mensaje")


def _intentar_correo(solicitud, request):
    try:
        _notificar(solicitud, request)
    except (SMTPException, OSError, ValueError):
        logger.exception("No se pudo confirmar por correo la solicitud %s", solicitud.pk)
        return False
    solicitud.confirmacion_enviada_en = timezone.now()
    solicitud.confirmacion_pendiente = False
    solicitud.save(update_fields=["confirmacion_enviada_en", "confirmacion_pendiente", "actualizado_en"])
    ActuacionSolicitud.objects.create(solicitud=solicitud, actor=None,
                                      accion="CORREO", descripcion="Confirmación enviada al titular.")
    return True


@login_required(login_url="acceso")
def panel_solicitante(request):
    _permiso(request)
    qs = SolicitudAsistencia.objects.filter(solicitante=request.user)
    recientes = qs.select_related("tipo_ayuda", "prioridad")[:5]
    actividades = ActuacionSolicitud.objects.filter(solicitud__solicitante=request.user).select_related("solicitud")[:5]
    return render(request, "solicitudes/panel.html", {
        "recientes": recientes, "actividades": actividades,
        "activas": qs.exclude(estado__in=[SolicitudAsistencia.Estado.BORRADOR,
                    SolicitudAsistencia.Estado.CANCELADA, SolicitudAsistencia.Estado.COMPLETADA]).count(),
        "revision": qs.filter(estado=SolicitudAsistencia.Estado.EN_REVISION).count(),
        "completadas": qs.filter(estado=SolicitudAsistencia.Estado.COMPLETADA).count(),
        "borradores": qs.filter(estado=SolicitudAsistencia.Estado.BORRADOR).count(),
        "rol_aprobado": tiene_rol_solicitante(request.user, aprobado=True),
    })


@login_required(login_url="acceso")
def mis_solicitudes(request):
    _permiso(request)
    base = SolicitudAsistencia.objects.filter(solicitante=request.user)
    qs = base.select_related("tipo_ayuda", "prioridad")
    estado = request.GET.get("estado", "")
    busqueda = request.GET.get("q", "").strip()[:80]
    tipo = request.GET.get("tipo", "")
    fecha = request.GET.get("fecha", "")
    if estado in SolicitudAsistencia.Estado.values:
        qs = qs.filter(estado=estado)
    if busqueda:
        filtro = Q(tipo_ayuda__nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda)
        if busqueda.startswith("SOL-") and busqueda[9:].isdigit():
            filtro |= Q(pk=int(busqueda[9:]))
        qs = qs.filter(filtro)
    if tipo.isdigit():
        qs = qs.filter(tipo_ayuda_id=int(tipo))
    from datetime import date
    try:
        if fecha:
            qs = qs.filter(fecha_requerida=date.fromisoformat(fecha))
    except ValueError:
        fecha = ""
    from django.core.paginator import Paginator
    pagina = Paginator(qs, 10).get_page(request.GET.get("page"))
    return render(request, "solicitudes/lista.html", {
        "pagina": pagina, "estado": estado, "estados": SolicitudAsistencia.Estado.choices,
        "busqueda": busqueda, "tipo": tipo, "fecha": fecha, "tipos": opciones(CATALOGO_TIPOS),
        "total": base.count(), "revision": base.filter(estado=SolicitudAsistencia.Estado.EN_REVISION).count(),
        "aprobadas": base.filter(estado=SolicitudAsistencia.Estado.APROBADA).count(),
        "completadas": base.filter(estado=SolicitudAsistencia.Estado.COMPLETADA).count(),
        "canceladas": base.filter(estado=SolicitudAsistencia.Estado.CANCELADA).count(),
    })


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def nueva_solicitud(request, codigo=None):
    _permiso(request)
    existente = _buscar_solicitud_propia(request, codigo) if codigo else None
    if codigo and (existente is None or existente.estado not in (
            SolicitudAsistencia.Estado.BORRADOR, SolicitudAsistencia.Estado.OBSERVADA,
            SolicitudAsistencia.Estado.EN_REVISION)):
        return _no_disponible(request)
    inicial = {}
    if existente:
        inicial = {campo: getattr(existente, campo) for campo in (
            "destinatario", "tipo_ayuda", "prioridad", "fecha_requerida", "descripcion",
            "sector_referencia", "latitud", "longitud", "persona_contacto", "telefono_contacto", "correo_contacto", "observaciones")}
        inicial["correo_contacto"] = existente.correo_contacto or request.user.email
        inicial["disponibilidad"] = existente.disponibilidad.split(",")
        inicial["consiente_ubicacion"] = bool(existente.consentimiento_ubicacion_en)
    elif request.method == "GET":
        inicial = {"persona_contacto": request.user.get_full_name(),
                   "telefono_contacto": getattr(getattr(request.user, "perfil_barrio", None), "telefono", ""),
                   "correo_contacto": request.user.email,
                   "destinatario": SolicitudAsistencia.Destinatario.PROPIA,
                   "consiente_ubicacion": False}
    es_borrador = request.method == "POST" and request.POST.get("accion") == "borrador"
    form = SolicitudAsistenciaForm(request.POST or None, initial=inicial, usuario=request.user,
                                  requiere_confirmacion=not es_borrador)
    if request.method == "POST":
        if request.POST.get("accion") not in ("borrador", "enviar"):
            raise Http404("Acción no disponible")
        if not es_borrador:
            _permiso(request, enviar=True)
            if not request.user.email:
                form.add_error(None, "Configura tu correo en la cuenta antes de enviar la solicitud.")
        if form.is_valid() and not form.errors:
            d = form.cleaned_data
            with transaction.atomic():
                if existente:
                    solicitud = SolicitudAsistencia.objects.select_for_update().get(pk=existente.pk,
                                   solicitante=request.user, estado__in=[SolicitudAsistencia.Estado.BORRADOR,
                                                                          SolicitudAsistencia.Estado.OBSERVADA,
                                                                          SolicitudAsistencia.Estado.EN_REVISION])
                else:
                    solicitud = SolicitudAsistencia(solicitante=request.user)
                for campo in ("tipo_ayuda", "prioridad", "destinatario", "descripcion", "fecha_requerida",
                              "sector_referencia", "latitud", "longitud", "persona_contacto", "telefono_contacto", "correo_contacto", "observaciones"):
                    setattr(solicitud, campo, d[campo])
                solicitud.disponibilidad = ",".join(d["disponibilidad"])
                if solicitud.consentimiento_ubicacion_en is None:
                    solicitud.consentimiento_ubicacion_en = timezone.now()
                if es_borrador:
                    solicitud.estado = SolicitudAsistencia.Estado.BORRADOR
                    solicitud.confirmacion_pendiente = False
                else:
                    solicitud.estado = SolicitudAsistencia.Estado.EN_REVISION
                    solicitud.enviada_en = timezone.now()
                    solicitud.acepto_tratamiento_en = timezone.now()
                    solicitud.confirmacion_pendiente = True
                    solicitud.confirmacion_enviada_en = None
                solicitud.nota_revision = ""
                solicitud.revisado_por = None
                solicitud.revisado_en = None
                solicitud.save()
                ActuacionSolicitud.objects.create(solicitud=solicitud, actor=request.user,
                    accion="BORRADOR" if es_borrador else "ENVIO",
                    descripcion="Guardó un borrador." if es_borrador else "Envió la solicitud para revisión.")
            if es_borrador:
                messages.success(request, "Borrador guardado. Puedes volver a editarlo desde Mis solicitudes.")
                return redirect("solicitud_detalle", codigo=solicitud.codigo_acceso)
            if not _intentar_correo(solicitud, request):
                messages.warning(request, "La solicitud quedó registrada, pero no pudimos enviar la confirmación por correo. Puedes reintentar el envío desde su detalle.")
            return redirect("solicitud_confirmacion", codigo=solicitud.codigo_acceso)
    return render(request, "solicitudes/formulario.html", {
        "form": form, "existente": existente, "rol_aprobado": tiene_rol_solicitante(request.user, aprobado=True),
        "tipos_disponibles": opciones(CATALOGO_TIPOS).exists(),
        "prioridades_disponibles": opciones(CATALOGO_PRIORIDADES).exists(),
    })


@login_required(login_url="acceso")
def solicitud_confirmacion(request, codigo):
    _permiso(request)
    solicitud = _buscar_solicitud_propia(request, codigo)
    if solicitud is None:
        return _no_disponible(request)
    if solicitud.estado == SolicitudAsistencia.Estado.BORRADOR:
        return redirect("solicitud_detalle", codigo=codigo)
    return render(request, "solicitudes/confirmacion.html", {"solicitud": solicitud})


@login_required(login_url="acceso")
def solicitud_detalle(request, codigo):
    _permiso(request)
    solicitud = _buscar_solicitud_propia(request, codigo)
    if solicitud is None:
        return _no_disponible(request)
    return render(request, "solicitudes/detalle.html", {
        "solicitud": solicitud, "actuaciones": solicitud.actuaciones.select_related("actor"),
    })


def _form_edicion(request, solicitud, form=None, cancelacion=None):
    if form is None:
        initial = {campo: getattr(solicitud, campo) for campo in (
            "destinatario", "tipo_ayuda", "prioridad", "fecha_requerida", "descripcion",
            "sector_referencia", "observaciones")}
        initial["disponibilidad"] = solicitud.disponibilidad.split(",")
        form = SolicitudEdicionForm(initial=initial, usuario=request.user)
    return render(request, "solicitudes/edicion.html", {
        "solicitud": solicitud, "form": form,
        "cancelacion": cancelacion or CancelacionSolicitudForm(),
    })


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def editar_solicitud(request, codigo):
    _permiso(request)
    solicitud = _buscar_solicitud_propia(request, codigo)
    if solicitud is None or solicitud.estado not in (
            SolicitudAsistencia.Estado.BORRADOR, SolicitudAsistencia.Estado.EN_REVISION, SolicitudAsistencia.Estado.OBSERVADA):
        return _no_disponible(request)
    if request.method == "GET":
        return _form_edicion(request, solicitud)
    if solicitud.estado == SolicitudAsistencia.Estado.BORRADOR:
        return redirect("solicitud_editar_borrador", codigo=codigo)
    form = SolicitudEdicionForm(request.POST, usuario=request.user)
    if not form.is_valid():
        return _form_edicion(request, solicitud, form=form)
    with transaction.atomic():
        actual = SolicitudAsistencia.objects.select_for_update().get(pk=solicitud.pk, solicitante=request.user)
        if actual.estado not in (SolicitudAsistencia.Estado.EN_REVISION, SolicitudAsistencia.Estado.OBSERVADA):
            messages.warning(request, "El estado cambió mientras editabas la solicitud. Revisa el detalle.")
            return redirect("solicitud_detalle", codigo=codigo)
        for campo in ("destinatario", "tipo_ayuda", "prioridad", "fecha_requerida",
                      "descripcion", "sector_referencia", "observaciones"):
            setattr(actual, campo, form.cleaned_data[campo])
        actual.disponibilidad = ",".join(form.cleaned_data["disponibilidad"])
        actual.estado = SolicitudAsistencia.Estado.EN_REVISION
        actual.nota_revision = ""
        actual.revisado_por = None
        actual.revisado_en = None
        actual.save()
        ActuacionSolicitud.objects.create(solicitud=actual, actor=request.user,
            accion="EDICION", descripcion="Actualizó la solicitud; queda en revisión.")
    messages.success(request, "Cambios guardados. La solicitud está en revisión.")
    return redirect("solicitud_detalle", codigo=codigo)


@login_required(login_url="acceso")
@csrf_protect
@require_POST
def cancelar_solicitud(request, codigo):
    _permiso(request)
    propia = _buscar_solicitud_propia(request, codigo)
    if propia is None or propia.estado not in (
            SolicitudAsistencia.Estado.BORRADOR, SolicitudAsistencia.Estado.EN_REVISION,
            SolicitudAsistencia.Estado.OBSERVADA):
        return _no_disponible(request)
    form = CancelacionSolicitudForm(request.POST)
    if not form.is_valid():
        if propia.estado == SolicitudAsistencia.Estado.BORRADOR:
            messages.error(request, "Indica un motivo y confirma la cancelación.")
            return redirect("solicitud_detalle", codigo=codigo)
        return _form_edicion(request, propia, cancelacion=form)
    with transaction.atomic():
        solicitud = SolicitudAsistencia.objects.select_for_update().get(pk=propia.pk, solicitante=request.user)
        if solicitud.estado not in (SolicitudAsistencia.Estado.BORRADOR,
                SolicitudAsistencia.Estado.EN_REVISION, SolicitudAsistencia.Estado.OBSERVADA):
            messages.warning(request, "El estado cambió; revisa la solicitud antes de cancelarla.")
            return redirect("solicitud_detalle", codigo=codigo)
        solicitud.estado = SolicitudAsistencia.Estado.CANCELADA
        solicitud.confirmacion_pendiente = False
        solicitud.save(update_fields=["estado", "confirmacion_pendiente", "actualizado_en"])
        ActuacionSolicitud.objects.create(solicitud=solicitud, actor=request.user,
            accion="CANCELACION", descripcion=(f"Canceló su solicitud. Motivo: {form.cleaned_data['motivo']}. "
                f"{form.cleaned_data['comentario']}")[:350])
    messages.success(request, "La solicitud quedó cancelada.")
    return redirect("solicitud_detalle", codigo=codigo)


@login_required(login_url="acceso")
@csrf_protect
@require_POST
def reenviar_confirmacion(request, codigo):
    _permiso(request)
    solicitud = _buscar_solicitud_propia(request, codigo)
    if solicitud is None or not solicitud.confirmacion_pendiente or solicitud.estado != SolicitudAsistencia.Estado.EN_REVISION:
        return _no_disponible(request)
    llave = f"bs:solicitud-correo:{solicitud.pk}"
    if not cache.add(llave, 1, timeout=60):
        messages.warning(request, "Espera un minuto antes de reintentar el correo.")
    elif _intentar_correo(solicitud, request):
        messages.success(request, "Confirmación enviada a tu correo.")
    else:
        cache.delete(llave)
        messages.error(request, "No pudimos enviar el correo. La solicitud sigue registrada.")
    return redirect("solicitud_detalle", codigo=codigo)


def _es_revisor(usuario):
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    return usuario.is_superuser or UsuarioRol.objects.filter(usuario=usuario, rol__codigo="COORDINADOR",
        rol__activo=True, activo=True, estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).exists()


@login_required(login_url="acceso")
def revisar_solicitudes(request):
    if not _es_revisor(request.user):
        raise PermissionDenied
    lista = SolicitudAsistencia.objects.select_related("tipo_ayuda", "solicitante").filter(
        estado__in=[SolicitudAsistencia.Estado.EN_REVISION, SolicitudAsistencia.Estado.OBSERVADA]).order_by("creado_en")[:100]
    return render(request, "solicitudes/revision_lista.html", {"solicitudes": lista})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def revisar_solicitud(request, pk):
    if not _es_revisor(request.user):
        raise PermissionDenied
    solicitud = get_object_or_404(SolicitudAsistencia.objects.select_related("tipo_ayuda", "prioridad", "solicitante"), pk=pk)
    if request.method == "POST":
        estado = request.POST.get("estado")
        nota = " ".join(request.POST.get("nota", "").split())
        permitidos = (SolicitudAsistencia.Estado.APROBADA, SolicitudAsistencia.Estado.OBSERVADA,
                      SolicitudAsistencia.Estado.RECHAZADA)
        if estado not in permitidos or len(nota) < 10 or len(nota) > 300 or "<" in nota or ">" in nota:
            messages.error(request, "Selecciona un resultado e indica una nota válida de 10 a 300 caracteres, sin HTML.")
        else:
            with transaction.atomic():
                solicitud = SolicitudAsistencia.objects.select_for_update().get(pk=pk)
                if solicitud.estado not in (SolicitudAsistencia.Estado.EN_REVISION, SolicitudAsistencia.Estado.OBSERVADA):
                    messages.error(request, "La solicitud ya no está disponible para revisión.")
                    return redirect("solicitud_revision", pk=pk)
                solicitud.estado = estado
                solicitud.nota_revision = nota
                solicitud.revisado_por = request.user
                solicitud.revisado_en = timezone.now()
                solicitud.save(update_fields=["estado", "nota_revision", "revisado_por", "revisado_en", "actualizado_en"])
                ActuacionSolicitud.objects.create(solicitud=solicitud, actor=request.user,
                    accion="REVISION", descripcion=f"{solicitud.get_estado_display()}: {nota}"[:350])
            try:
                ruta = reverse("solicitud_detalle", kwargs={"codigo": solicitud.codigo_acceso})
                origen = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
                enlace = f"{origen}{ruta}" if origen else request.build_absolute_uri(ruta)
                contexto = {"solicitud": solicitud, "nota": nota, "enlace": enlace,
                            "nombre": solicitud.solicitante.first_name}
                correo = EmailMultiAlternatives(
                    subject=f"Actualización de solicitud {solicitud.codigo} | Barrio Solidario",
                    body=render_to_string("solicitudes/correo_estado.txt", contexto),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[solicitud.solicitante.email])
                correo.attach_alternative(render_to_string("solicitudes/correo_estado.html", contexto), "text/html")
                _adjuntar_logo_uees(correo)
                if correo.send(fail_silently=False) != 1:
                    raise SMTPException("El servidor no confirmó el envío")
            except (SMTPException, OSError, ValueError):
                logger.exception("Falló aviso de revisión de solicitud %s", pk)
                messages.warning(request, "La revisión se guardó, pero no pudimos enviar el aviso por correo.")
            else:
                messages.success(request, "Revisión guardada y notificada al solicitante.")
            return redirect("solicitud_revision", pk=pk)
    return render(request, "solicitudes/revision_detalle.html", {"solicitud": solicitud})
