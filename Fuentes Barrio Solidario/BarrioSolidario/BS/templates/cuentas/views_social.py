"""Segundo paso por correo para el acceso de Google."""
import hashlib
import logging
from datetime import datetime
from smtplib import SMTPException

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .forms_cuentas import ROLES_PUBLICOS
from .forms_social import CompletarRegistroGoogleForm
from .models import EventoAcceso, PerfilUsuario, Rol, SolicitudAccesoSocial, UsuarioRol
from .views_cuentas import _adjuntar_logo_uees

logger = logging.getLogger(__name__)


def _candidate(request):
    value = request.session.get("bs_social_candidate")
    if not value or value.get("provider") != "google" or not value.get("uid"):
        return None
    try:
        if datetime.fromisoformat(value["vence"]) <= timezone.now():
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return value


def enviar_enlace_social(request, pending, token):
    path = reverse("social_confirmar", kwargs={"token": token})
    origin = settings.PUBLIC_BASE_URL.rstrip("/")
    url = f"{origin}{path}" if origin else request.build_absolute_uri(path)
    context = {"nombre": pending.nombres or (pending.usuario.first_name if pending.usuario else ""), "enlace": url, "acceso_con_clave": pending.proveedor == "password"}
    message = EmailMultiAlternatives(
        subject="Confirma tu acceso a Barrio Solidario",
        body=render_to_string("cuentas/correo_social.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[pending.correo],
    )
    message.attach_alternative(render_to_string("cuentas/correo_social.html", context), "text/html")
    _adjuntar_logo_uees(message)
    message.send(fail_silently=False)


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def completar_registro_google(request):
    candidate = _candidate(request)
    if candidate is None:
        request.session.pop("bs_social_candidate", None)
        messages.error(request, "Vuelve a identificarte con Google para continuar.")
        return redirect("acceso")

    initial = {"nombres": candidate.get("nombres", ""), "apellidos": candidate.get("apellidos", "")}
    form = CompletarRegistroGoogleForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        email = candidate["email"]
        User = get_user_model()
        fingerprint = hashlib.sha256(email.encode()).hexdigest()
        if not cache.add(f"bs:social-register:{fingerprint}", 1, 60):
            form.add_error(None, "Espera un minuto antes de solicitar otro enlace.")
        elif User.objects.filter(email__iexact=email).exists() or PerfilUsuario.objects.filter(correo__iexact=email).exists():
            cache.delete(f"bs:social-register:{fingerprint}")
            form.add_error(None, "Este correo ya está registrado. Entra con tu contraseña y vincula Google desde tu perfil.")
        else:
            try:
                with transaction.atomic():
                    pending, token = SolicitudAccesoSocial.crear(
                        email=email, provider="google", uid=candidate["uid"],
                        datos=form.cleaned_data,
                    )
                    enviar_enlace_social(request, pending, token)
            except (SMTPException, OSError):
                cache.delete(f"bs:social-register:{fingerprint}")
                logger.exception("No se pudo enviar correo de registro social")
                form.add_error(None, "No se pudo enviar el correo. Inténtalo más tarde.")
            else:
                request.session.pop("bs_social_candidate", None)
                return redirect("social_enviado")
    return render(request, "cuentas/social_completar.html", {"form": form, "correo": candidate["email"]})


@never_cache
def enlace_enviado(request):
    return render(request, "cuentas/social_enviado.html")


@never_cache
@require_http_methods(["GET"])
def confirmar_acceso_social(request, token):
    try:
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    except (ValueError, UnicodeError):
        raise Http404
    pending = SolicitudAccesoSocial.objects.filter(token_hash=digest).first()
    if pending is None or not pending.vigente:
        return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)
    User = get_user_model()
    try:
        with transaction.atomic():
            pending = SolicitudAccesoSocial.objects.select_for_update().get(pk=pending.pk)
            if not pending.vigente:
                return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)

            if pending.proveedor == "password":
                if not pending.usuario_id:
                    return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)
                user = User.objects.select_for_update().get(pk=pending.usuario_id)
                profile = PerfilUsuario.objects.filter(usuario=user).first()
                if not user.is_active or (profile and profile.estado != PerfilUsuario.Estado.ACTIVA) or user.email.casefold() != pending.correo.casefold():
                    return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)
            elif pending.usuario_id and pending.proveedor == "google":
                user = User.objects.select_for_update().get(pk=pending.usuario_id)
                profile = PerfilUsuario.objects.get(usuario=user)
                social = SocialAccount.objects.filter(user=user, provider=pending.proveedor, uid=pending.uid_proveedor).first()
                if not social or not user.is_active or profile.estado != PerfilUsuario.Estado.ACTIVA or user.email.casefold() != pending.correo.casefold():
                    return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)
            elif pending.proveedor == "google":
                if not pending.acepto_politicas_en or User.objects.filter(email__iexact=pending.correo).exists() or PerfilUsuario.objects.filter(correo__iexact=pending.correo).exists():
                    return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)
                rol, _ = Rol.objects.get_or_create(
                    codigo=pending.rol_codigo,
                    defaults={"nombre": dict(ROLES_PUBLICOS).get(pending.rol_codigo, pending.rol_codigo)},
                )
                if not rol.activo or pending.rol_codigo not in dict(ROLES_PUBLICOS):
                    return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)
                user = User(username=pending.correo, email=pending.correo, first_name=pending.nombres, last_name=pending.apellidos, is_active=True)
                user.set_unusable_password()
                user.save()
                PerfilUsuario.objects.create(
                    usuario=user, correo=pending.correo, telefono=pending.telefono,
                    estado=PerfilUsuario.Estado.ACTIVA, acepto_politicas_en=pending.acepto_politicas_en,
                )
                UsuarioRol.objects.create(usuario=user, rol=rol)
                SocialAccount.objects.create(user=user, provider="google", uid=pending.uid_proveedor)
                EmailAddress.objects.create(user=user, email=pending.correo, verified=True, primary=True)
                EventoAcceso.objects.create(usuario=user, tipo=EventoAcceso.Tipo.REGISTRO)
            else:
                return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)

            pending.utilizado_en = timezone.now()
            pending.save(update_fields=["utilizado_en"])
            EventoAcceso.objects.create(usuario=user, tipo=EventoAcceso.Tipo.ACCESO)
    except (IntegrityError, User.DoesNotExist, PerfilUsuario.DoesNotExist):
        logger.exception("No se pudo finalizar el acceso social")
        return render(request, "cuentas/social_confirmar.html", {"invalido": True}, status=400)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    if pending.proveedor == "password" and not request.session.pop("bs_recordarme", False):
        request.session.set_expiry(0)
    messages.success(request, "Acceso confirmado. Bienvenido a Barrio Solidario.")
    return redirect("inicio")
