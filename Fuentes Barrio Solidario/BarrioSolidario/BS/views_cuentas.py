import logging
from email.mime.image import MIMEImage
from pathlib import Path
from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from .forms_cuentas import ActivarCuentaForm, ReenviarActivacionForm, RegistroForm, PerfilCuentaForm, CambiarClaveCuentaForm, SolicitarRecuperacionForm
from .models import EventoAcceso, PerfilUsuario, Rol, UsuarioRol, RecuperacionClave

logger = logging.getLogger(__name__)


def _adjuntar_logo_uees(mensaje):
    """Incluye el logo en el MIME del correo para resolver el recurso cid."""
    ruta = Path(__file__).resolve().parent / "static" / "img" / "logo_uees_correo.png"
    imagen = MIMEImage(ruta.read_bytes(), _subtype="png")
    imagen.add_header("Content-ID", "<logo-uees@barriosolidario>")
    imagen.add_header("Content-Disposition", "inline", filename="logo_uees_correo.png")
    mensaje.mixed_subtype = "related"
    mensaje.attach(imagen)


@require_http_methods(["GET", "POST"])
@csrf_protect
@never_cache
def acceso(request):
    if request.user.is_authenticated:
        return redirect("inicio")

    contexto = {}
    if request.method == "POST":
        identificador = request.POST.get("usuario", "").strip()[:150]
        clave = request.POST.get("password", "")
        contexto = {"usuario": identificador, "recordarme": request.POST.get("recordarme") == "1"}
        if _limitado(request, "acceso", maximo=10, minutos=15):
            contexto["error"] = "Demasiados intentos. Inténtalo más tarde."
            return render(request, "cuentas/acceso.html", contexto, status=429)
        if identificador and clave:
            User = get_user_model()
            # Las cuentas registradas usan el correo como username; admite también
            # usuarios administrativos cuyo username sea distinto del correo.
            cuenta = User.objects.filter(username__iexact=identificador).first()
            if cuenta is None:
                cuenta = User.objects.filter(email__iexact=identificador).first()
            username = cuenta.get_username() if cuenta else identificador
            usuario = authenticate(request, username=username, password=clave)
            if usuario is not None:
                perfil = PerfilUsuario.objects.filter(usuario=usuario).first()
                if perfil is None or perfil.estado == PerfilUsuario.Estado.ACTIVA:
                    login(request, usuario)
                    if not contexto["recordarme"]:
                        request.session.set_expiry(0)
                    EventoAcceso.objects.create(usuario=usuario, tipo=EventoAcceso.Tipo.ACCESO)
                    return redirect("inicio")
        contexto["error"] = "No pudimos iniciar sesión. Verifica tus credenciales y que tu cuenta esté activa."
    return render(request, "cuentas/acceso.html", contexto)


def _limitado(request, accion, maximo=5, minutos=30):
    # REMOTE_ADDR: no se confía en cabeceras X-Forwarded-For enviadas por clientes.
    ip = request.META.get("REMOTE_ADDR", "unknown")
    clave = f"bs:{accion}:{ip}"
    if cache.add(clave, 1, timeout=minutos * 60):
        return False
    try:
        return cache.incr(clave) > maximo
    except ValueError:
        cache.set(clave, 1, timeout=minutos * 60)
        return False


def _correo_activacion(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    ruta = reverse("activar_cuenta", kwargs={"uidb64": uid, "token": token})
    origen = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    enlace = f"{origen}{ruta}" if origen else request.build_absolute_uri(ruta)
    contexto = {
        "nombre": usuario.first_name,
        "correo": usuario.email,
        "enlace": enlace,
    }
    cuerpo = render_to_string("cuentas/correo_activacion.txt", contexto)
    html = render_to_string("cuentas/correo_activacion.html", contexto)
    mensaje = EmailMultiAlternatives(
        subject="Activa tu cuenta en Barrio Solidario",
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.email],
    )
    mensaje.attach_alternative(html, "text/html")
    _adjuntar_logo_uees(mensaje)
    mensaje.send(fail_silently=False)


@require_http_methods(["GET", "POST"])
@csrf_protect
def registro(request):
    form = RegistroForm(request.POST or None)
    if request.method == "POST":
        if _limitado(request, "registro"):
            return HttpResponse("Demasiados intentos. Inténtalo más tarde.", status=429)
        if form.is_valid():
            datos = form.cleaned_data
            User = get_user_model()
            try:
                with transaction.atomic():
                    rol, _ = Rol.objects.get_or_create(
                        codigo=datos["tipoUsuario"],
                        defaults={"nombre": dict(RegistroForm.base_fields["tipoUsuario"].choices)[datos["tipoUsuario"]]},
                    )
                    if not rol.activo:
                        form.add_error("tipoUsuario", "Este tipo de cuenta no está disponible.")
                    else:
                        usuario = User(
                            username=datos["email"], email=datos["email"],
                            first_name=datos["nombres"], last_name=datos["apellidos"],
                            is_active=False,
                        )
                        usuario.set_unusable_password()
                        usuario.save()
                        PerfilUsuario.objects.create(
                            usuario=usuario, correo=datos["email"],
                            telefono=datos["telefono"], estado=PerfilUsuario.Estado.PENDIENTE,
                            acepto_politicas_en=timezone.now(),
                        )
                        UsuarioRol.objects.create(usuario=usuario, rol=rol)
                        # Si falla SMTP, la transacción revierte la cuenta pendiente.
                        _correo_activacion(request, usuario)
                        EventoAcceso.objects.create(usuario=usuario, tipo=EventoAcceso.Tipo.REGISTRO)
                        return redirect("registro_enviado")
            except IntegrityError:
                form.add_error("email", "Ya existe una cuenta con este correo.")
            except (SMTPException, OSError):
                logger.exception("No se pudo enviar el correo de activación")
                form.add_error(None, "No pudimos enviar el correo. Inténtalo más tarde.")
    return render(request, "cuentas/registro.html", {"form": form})


@require_http_methods(["GET"])
def registro_enviado(request):
    return render(request, "cuentas/registro_enviado.html")


def _usuario_del_enlace(uidb64, token):
    try:
        pk = force_str(urlsafe_base64_decode(uidb64))
        usuario = get_user_model().objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        return None
    if usuario.is_active or not default_token_generator.check_token(usuario, token):
        return None
    return usuario


@require_http_methods(["GET", "POST"])
@csrf_protect
@never_cache
def activar_cuenta(request, uidb64, token):
    usuario = _usuario_del_enlace(uidb64, token)
    if usuario is None:
        return render(request, "cuentas/activacion_invalida.html", status=400)
    form = ActivarCuentaForm(request.POST or None, usuario=usuario)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
            if usuario.is_active or not default_token_generator.check_token(usuario, token):
                return render(request, "cuentas/activacion_invalida.html", status=400)
            usuario.set_password(form.cleaned_data["password1"])
            usuario.is_active = True
            usuario.save(update_fields=["password", "is_active"])
            PerfilUsuario.objects.filter(usuario=usuario).update(estado=PerfilUsuario.Estado.ACTIVA)
        return redirect("acceso")
    return render(request, "cuentas/activar_cuenta.html", {"form": form})


@require_http_methods(["GET", "POST"])
@csrf_protect
def reenviar_activacion(request):
    form = ReenviarActivacionForm(request.POST or None)
    if request.method == "POST":
        if _limitado(request, "reenviar"):
            return HttpResponse("Demasiados intentos. Inténtalo más tarde.", status=429)
        if form.is_valid():
            usuario = get_user_model().objects.filter(email__iexact=form.cleaned_data["email"], is_active=False).first()
            if usuario and PerfilUsuario.objects.filter(usuario=usuario, estado=PerfilUsuario.Estado.PENDIENTE).exists():
                try:
                    _correo_activacion(request, usuario)
                except (SMTPException, OSError):
                    logger.exception("No se pudo reenviar el correo de activación")
            return redirect("registro_enviado")
    return render(request, "cuentas/reenviar_activacion.html", {"form": form})


@login_required(login_url="acceso")
def panel_cuenta(request):
    return render(request, "cuentas/panel_cuenta.html")


@login_required(login_url="acceso")
@require_http_methods(["GET", "POST"])
@csrf_protect
def perfil_cuenta(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    form = PerfilCuentaForm(request.POST or None, usuario=request.user, perfil=perfil)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            request.user.first_name = form.cleaned_data["nombres"]
            request.user.last_name = form.cleaned_data["apellidos"]
            request.user.save(update_fields=["first_name", "last_name"])
            if perfil:
                perfil.telefono = form.cleaned_data["telefono"]
                perfil.save(update_fields=["telefono", "actualizado_en"])
        return redirect("perfil_cuenta")
    return render(request, "cuentas/perfil_cuenta.html", {"form": form})


@login_required(login_url="acceso")
@require_http_methods(["GET", "POST"])
@csrf_protect
def cambiar_clave_cuenta(request):
    form = CambiarClaveCuentaForm(request.user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        update_session_auth_hash(request, usuario)

        return render(request, "cuentas/cambiar_clave_cuenta.html", {
            "form": CambiarClaveCuentaForm(request.user),
            "clave_actualizada": True,
        })

    return render(request, "cuentas/cambiar_clave_cuenta.html", {"form": form})


@login_required(login_url="acceso")
@require_POST
@csrf_protect
def cerrar_sesion_cuenta(request):
    EventoAcceso.objects.create(usuario=request.user, tipo=EventoAcceso.Tipo.SALIDA)
    logout(request)
    return redirect("inicio")


@require_http_methods(["GET", "POST"])
@csrf_protect
@never_cache
def recuperar_clave(request):
    form = SolicitarRecuperacionForm(request.POST or None)
    if request.method == "POST":
        if _limitado(request, "recuperar"):
            return HttpResponse("Demasiados intentos. Inténtalo más tarde.", status=429)
        if form.is_valid():
            correo = form.cleaned_data["email"].strip()
            usuario = get_user_model().objects.filter(email__iexact=correo, is_active=True).first()
            if usuario:
                uid = urlsafe_base64_encode(force_bytes(usuario.pk))
                token = default_token_generator.make_token(usuario)
                ruta = reverse("restablecer_clave", kwargs={"uidb64": uid, "token": token})
                origen = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
                enlace = f"{origen}{ruta}" if origen else request.build_absolute_uri(ruta)
                contexto = {"nombre": usuario.first_name, "enlace": enlace}
                mensaje = EmailMultiAlternatives(
                    "Restablece tu contraseña | Barrio Solidario",
                    render_to_string("cuentas/correo_recuperacion.txt", contexto),
                    settings.DEFAULT_FROM_EMAIL,
                    [usuario.email],
                )
                mensaje.attach_alternative(render_to_string("cuentas/correo_recuperacion.html", contexto), "text/html")
                try:
                    _adjuntar_logo_uees(mensaje)
                    mensaje.send(fail_silently=False)
                    RecuperacionClave.objects.create(
                        usuario=usuario,
                        fecha_expiracion=timezone.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT),
                    )
                    EventoAcceso.objects.create(usuario=usuario, tipo=EventoAcceso.Tipo.RECUPERACION)
                except (SMTPException, OSError):
                    logger.exception("No se pudo enviar un correo de recuperación")
                    messages.error(request, "No pudimos enviar el correo en este momento. Inténtalo de nuevo más tarde.")
                    return render(request, "cuentas/recuperar_clave.html", {"form": form}, status=503)
            # Respuesta idéntica para correos existentes e inexistentes.
            messages.success(request, "Recibimos tu solicitud. Si existe una cuenta activa con ese correo, recibirás un enlace para restablecer tu contraseña. Revisa también el correo no deseado.")
            return redirect("inicio")
    return render(request, "cuentas/recuperar_clave.html", {"form": form})


@require_http_methods(["GET"])
@never_cache
def recuperacion_enviada(request):
    return render(request, "cuentas/recuperacion_enviada.html")


@require_http_methods(["GET", "POST"])
@csrf_protect
@never_cache
def restablecer_clave(request, uidb64, token):
    try:
        pk = force_str(urlsafe_base64_decode(uidb64))
        usuario = get_user_model().objects.get(pk=pk, is_active=True)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        usuario = None
    if usuario is None or not default_token_generator.check_token(usuario, token):
        return render(request, "cuentas/enlace_recuperacion_invalido.html", status=400)
    form = ActivarCuentaForm(request.POST or None, usuario=usuario)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
            if not usuario.is_active or not default_token_generator.check_token(usuario, token):
                return render(request, "cuentas/enlace_recuperacion_invalido.html", status=400)
            usuario.set_password(form.cleaned_data["password1"])
            usuario.save(update_fields=["password"])
            RecuperacionClave.objects.filter(usuario=usuario, estado=RecuperacionClave.Estado.SOLICITADA).update(
                estado=RecuperacionClave.Estado.COMPLETADA, fecha_uso=timezone.now()
            )
        return redirect("recuperacion_completada")
    return render(request, "cuentas/restablecer_clave.html", {"form": form})


@require_http_methods(["GET"])
@never_cache
def recuperacion_completada(request):
    return render(request, "cuentas/recuperacion_completada.html")
