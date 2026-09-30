"""Gestión de usuarios y alta administrativa con activación por correo."""
import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST, require_GET

from .forms_usuarios import (AltaUsuarioForm, EditarUsuarioForm, AsignarRolForm,
                             EstadoUsuarioForm, ActivacionAdministrativaForm)
from .models import ActuacionUsuario, EventoAcceso, PerfilUsuario, Rol, UsuarioRol
from .views_cuentas import _adjuntar_logo_uees

logger = logging.getLogger(__name__)


def _solo_admin(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied("La gestión de usuarios requiere una cuenta administradora.")


def _tiene_acceso_social(usuario):
    from allauth.socialaccount.models import SocialAccount
    return SocialAccount.objects.filter(user=usuario).exists()


def _correo_alta(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    ruta = reverse("activar_alta_administrativa", kwargs={"uidb64": uid, "token": token})
    origen = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    enlace = f"{origen}{ruta}" if origen else request.build_absolute_uri(ruta)
    contexto = {"nombre": usuario.first_name, "correo": usuario.email, "enlace": enlace}
    correo = EmailMultiAlternatives(
        subject="Activa tu cuenta en Barrio Solidario",
        body=render_to_string("usuarios/correo_alta.txt", contexto),
        from_email=settings.DEFAULT_FROM_EMAIL, to=[usuario.email],
    )
    correo.attach_alternative(render_to_string("usuarios/correo_alta.html", contexto), "text/html")
    _adjuntar_logo_uees(correo)
    if correo.send(fail_silently=False) != 1:
        raise SMTPException("El servidor no confirmó el envío del correo de activación")


@login_required(login_url="acceso")
def usuarios_panel(request):
    _solo_admin(request)
    User = get_user_model()
    qs = User.objects.select_related("perfil_barrio").prefetch_related("roles_barrio__rol").order_by("-date_joined")
    busqueda = request.GET.get("q", "").strip()[:100]
    rol = request.GET.get("rol", "").strip()[:32]
    estado = request.GET.get("estado", "").strip()[:12]
    aprobacion = request.GET.get("aprobacion", "").strip()[:12]
    if busqueda:
        filtro = (Q(username__icontains=busqueda) | Q(email__icontains=busqueda) |
                  Q(first_name__icontains=busqueda) | Q(last_name__icontains=busqueda))
        if busqueda.upper().startswith("USR-") and busqueda[4:].isdigit():
            filtro |= Q(pk=int(busqueda[4:]))
        qs = qs.filter(filtro)
    if rol:
        qs = qs.filter(roles_barrio__rol__codigo=rol)
    if estado in PerfilUsuario.Estado.values:
        qs = qs.filter(perfil_barrio__estado=estado)
    if aprobacion in UsuarioRol.Aprobacion.values:
        qs = qs.filter(roles_barrio__estado_aprobacion=aprobacion)
    from django.core.paginator import Paginator
    pagina = Paginator(qs.distinct(), 10).get_page(request.GET.get("page"))
    return render(request, "usuarios/lista.html", {
        "pagina": pagina, "q": busqueda, "rol_actual": rol, "estado_actual": estado,
        "aprobacion_actual": aprobacion, "roles_filtro": Rol.objects.order_by("nombre"),
        "estados": PerfilUsuario.Estado.choices, "aprobaciones": UsuarioRol.Aprobacion.choices,
        "total": User.objects.count(),
        "pendientes": UsuarioRol.objects.filter(activo=True, estado_aprobacion=UsuarioRol.Aprobacion.PENDIENTE).values("usuario_id").distinct().count(),
        "activos": PerfilUsuario.objects.filter(estado=PerfilUsuario.Estado.ACTIVA, usuario__is_active=True).count(),
        "suspendidos": PerfilUsuario.objects.filter(estado__in=[PerfilUsuario.Estado.SUSPENDIDA, PerfilUsuario.Estado.INACTIVA]).count(),
    })


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def crear_usuario(request):
    _solo_admin(request)
    form = AltaUsuarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        User = get_user_model()
        try:
            with transaction.atomic():
                usuario = User(username=datos["email"], email=datos["email"],
                               first_name=datos["nombres"], last_name=datos["apellidos"], is_active=False)
                usuario.set_unusable_password()
                usuario.save()
                PerfilUsuario.objects.create(usuario=usuario, correo=datos["email"], telefono=datos["telefono"],
                                             estado=PerfilUsuario.Estado.PENDIENTE, acepto_politicas_en=None)
                UsuarioRol.objects.create(usuario=usuario, rol=datos["rol"])
                ActuacionUsuario.objects.create(usuario=usuario, actor=request.user, accion="ALTA",
                                               detalle=f"Invitación enviada. Rol solicitado: {datos['rol'].nombre}. {datos['observacion']}")
                _correo_alta(request, usuario)
                EventoAcceso.objects.create(usuario=usuario, tipo=EventoAcceso.Tipo.REGISTRO)
        except IntegrityError:
            form.add_error("email", "El correo ya se encuentra registrado.")
        except (OSError, SMTPException):
            logger.exception("Falló el correo del alta administrativa")
            form.add_error(None, "No se pudo enviar el correo de activación. No se creó la cuenta. Comprueba la configuración SMTP.")
        else:
            messages.success(request, f"Cuenta creada. Enviamos a {usuario.email} el enlace para activar y definir su contraseña.")
            return redirect("usuario_detalle", pk=usuario.pk)
    return render(request, "usuarios/nuevo.html", {"form": form})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def usuario_detalle(request, pk):
    _solo_admin(request)
    User = get_user_model()
    usuario = get_object_or_404(User.objects.select_related("perfil_barrio"), pk=pk)
    perfil = PerfilUsuario.objects.filter(usuario=usuario).first()
    if perfil is None:
        messages.warning(request, "Esta cuenta no tiene perfil de Barrio Solidario; sus datos deben completarse antes de gestionarla.")
    inicial = {"nombres": usuario.first_name, "apellidos": usuario.last_name,
               "telefono": perfil.telefono if perfil else "", "sector_aproximado": perfil.sector_aproximado if perfil else ""}
    editar = EditarUsuarioForm(initial=inicial)
    asignar = AsignarRolForm(initial={"estado_aprobacion": UsuarioRol.Aprobacion.PENDIENTE, "activo": True})
    estado_form = EstadoUsuarioForm(initial={"estado": perfil.estado if perfil else ""})
    accion = request.POST.get("accion", "") if request.method == "POST" else ""
    if request.method == "POST":
        if usuario.is_superuser:
            raise PermissionDenied("Las cuentas superusuarias se gestionan desde Django Admin.")
        if not perfil:
            raise PermissionDenied("No se puede modificar una cuenta sin perfil asociado.")
        if accion == "datos":
            editar = EditarUsuarioForm(request.POST)
            if editar.is_valid():
                datos = editar.cleaned_data
                with transaction.atomic():
                    usuario.first_name, usuario.last_name = datos["nombres"], datos["apellidos"]
                    usuario.save(update_fields=["first_name", "last_name"])
                    perfil.telefono, perfil.sector_aproximado = datos["telefono"], datos["sector_aproximado"]
                    perfil.save(update_fields=["telefono", "sector_aproximado", "actualizado_en"])
                    ActuacionUsuario.objects.create(usuario=usuario, actor=request.user, accion="DATOS", detalle="Actualizó nombres, apellidos, teléfono o sector aproximado.")
                messages.success(request, "Los datos del usuario se actualizaron.")
                return redirect("usuario_detalle", pk=pk)
        elif accion == "rol":
            asignar = AsignarRolForm(request.POST)
            if asignar.is_valid():
                datos = asignar.cleaned_data
                with transaction.atomic():
                    actual, creado = UsuarioRol.objects.select_for_update().get_or_create(
                        usuario=usuario, rol=datos["rol"], defaults={"activo": datos["activo"]})
                    anterior = actual.get_estado_aprobacion_display() if not creado else "Sin asignar"
                    actual.estado_aprobacion = datos["estado_aprobacion"]
                    actual.activo = datos["activo"]
                    actual.observacion_revision = datos["observacion"]
                    actual.fecha_revision = timezone.now() if actual.estado_aprobacion != UsuarioRol.Aprobacion.PENDIENTE else None
                    actual.revisado_por = request.user if actual.fecha_revision else None
                    actual.save()
                    ActuacionUsuario.objects.create(usuario=usuario, actor=request.user, accion="ROL",
                        detalle=f"{actual.rol.nombre}: {anterior} → {actual.get_estado_aprobacion_display()}; asignación {'activa' if actual.activo else 'inactiva'}. {datos['observacion']}")
                messages.success(request, "La asignación y aprobación del rol se guardaron.")
                return redirect("usuario_detalle", pk=pk)
        elif accion == "estado":
            estado_form = EstadoUsuarioForm(request.POST)
            if estado_form.is_valid():
                datos = estado_form.cleaned_data
                nuevo = datos["estado"]
                if nuevo == PerfilUsuario.Estado.ACTIVA and (not usuario.has_usable_password() and not _tiene_acceso_social(usuario) or perfil.acepto_politicas_en is None):
                    estado_form.add_error("estado", "La cuenta debe activarse desde el correo y aceptar las políticas antes de habilitarse.")
                elif (perfil.estado == PerfilUsuario.Estado.PENDIENTE and nuevo != PerfilUsuario.Estado.PENDIENTE) or (perfil.estado != PerfilUsuario.Estado.PENDIENTE and nuevo == PerfilUsuario.Estado.PENDIENTE):
                    estado_form.add_error("estado", "El estado pendiente corresponde únicamente al proceso de activación por correo.")
                else:
                    anterior = perfil.get_estado_display()
                    with transaction.atomic():
                        perfil.estado = nuevo
                        perfil.save(update_fields=["estado", "actualizado_en"])
                        usuario.is_active = nuevo == PerfilUsuario.Estado.ACTIVA
                        usuario.save(update_fields=["is_active"])
                        ActuacionUsuario.objects.create(usuario=usuario, actor=request.user, accion="ESTADO",
                            detalle=f"{anterior} → {perfil.get_estado_display()}. {datos['motivo']}")
                    messages.success(request, "El estado de la cuenta se actualizó.")
                    return redirect("usuario_detalle", pk=pk)
        else:
            raise Http404("Acción no disponible")
    return render(request, "usuarios/detalle.html", {
        "cuenta": usuario, "perfil": perfil, "editar": editar, "asignar": asignar,
        "estado_form": estado_form,
        "asignaciones": UsuarioRol.objects.filter(usuario=usuario).select_related("rol").order_by("rol__nombre"),
        "historial": ActuacionUsuario.objects.filter(usuario=usuario).select_related("actor")[:20],
        "accion_actual": accion,
    })


@login_required(login_url="acceso")
@csrf_protect
@require_POST
def reenviar_invitacion(request, pk):
    _solo_admin(request)
    usuario = get_object_or_404(get_user_model(), pk=pk)
    perfil = PerfilUsuario.objects.filter(usuario=usuario).first()
    if usuario.is_active or not perfil or perfil.estado != PerfilUsuario.Estado.PENDIENTE or usuario.has_usable_password() or usuario.is_superuser:
        messages.error(request, "Solo puedes reenviar invitaciones de altas administrativas pendientes.")
        return redirect("usuario_detalle", pk=pk)
    clave = f"bs:reenviar-invitacion:{usuario.pk}"
    if not cache.add(clave, 1, timeout=60):
        messages.warning(request, "Espera un minuto antes de volver a enviar esta invitación.")
        return redirect("usuario_detalle", pk=pk)
    try:
        _correo_alta(request, usuario)
    except (OSError, SMTPException):
        cache.delete(clave)
        logger.exception("No se pudo reenviar invitación")
        messages.error(request, "No se pudo enviar el correo. La cuenta continúa pendiente.")
    else:
        ActuacionUsuario.objects.create(usuario=usuario, actor=request.user, accion="REENVIO", detalle="Reenvió enlace de activación.")
        messages.success(request, "Se envió un nuevo enlace de activación.")
    return redirect("usuario_detalle", pk=pk)


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def activar_alta_administrativa(request, uidb64, token):
    try:
        pk = force_str(urlsafe_base64_decode(uidb64))
        usuario = get_user_model().objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        usuario = None
    if usuario is None or usuario.is_active or not default_token_generator.check_token(usuario, token) or not PerfilUsuario.objects.filter(usuario=usuario, estado=PerfilUsuario.Estado.PENDIENTE, acepto_politicas_en__isnull=True).exists():
        return render(request, "cuentas/activacion_invalida.html", status=400)
    form = ActivacionAdministrativaForm(request.POST or None, usuario=usuario)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
            perfil = PerfilUsuario.objects.select_for_update().get(usuario=usuario)
            if usuario.is_active or perfil.estado != PerfilUsuario.Estado.PENDIENTE or not default_token_generator.check_token(usuario, token):
                return render(request, "cuentas/activacion_invalida.html", status=400)
            usuario.set_password(form.cleaned_data["password1"])
            usuario.is_active = True
            usuario.save(update_fields=["password", "is_active"])
            perfil.estado = PerfilUsuario.Estado.ACTIVA
            perfil.acepto_politicas_en = timezone.now()
            perfil.save(update_fields=["estado", "acepto_politicas_en", "actualizado_en"])
            ActuacionUsuario.objects.create(usuario=usuario, accion="ACTIVACION",
                                            detalle="El titular aceptó las políticas y definió su contraseña.")
        messages.success(request, "Tu cuenta está activa. Ya puedes iniciar sesión.")
        return redirect("acceso")
    return render(request, "usuarios/activar_alta.html", {"form": form})


@login_required(login_url="acceso")
@require_GET
def avatar_usuario(request, pk):
    _solo_admin(request)
    perfil = get_object_or_404(PerfilUsuario, usuario_id=pk)
    if not perfil.avatar:
        raise Http404("Sin fotografía")
    try:
        return FileResponse(perfil.avatar.open("rb"), content_type="image/jpeg")
    except OSError:
        raise Http404("Fotografía no disponible")
