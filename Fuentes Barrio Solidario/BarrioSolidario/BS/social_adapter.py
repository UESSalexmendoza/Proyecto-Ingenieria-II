"""Intercepta los accesos sociales antes de que allauth abra una sesión."""
import hashlib
import logging
from datetime import timedelta

from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import PerfilUsuario, SolicitudAccesoSocial
from .views_social import enviar_enlace_social

logger = logging.getLogger(__name__)
PROVEEDORES = {"google": "Google", "microsoft": "Microsoft"}


class BarrioSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        # El alta y la confirmación se realizan en el flujo propio del MVP.
        return False

    def pre_social_login(self, request, sociallogin):
        provider = sociallogin.account.provider
        if provider not in PROVEEDORES:
            messages.error(request, "Este proveedor todavía no está disponible.")
            raise ImmediateHttpResponse(redirect("acceso"))

        # Conectar desde una sesión ya abierta es un flujo distinto al de acceso.
        if sociallogin.state.get("process") == "connect":
            if provider == "microsoft":
                messages.error(request, "La vinculación de Microsoft requiere un flujo de confirmación separado.")
                raise ImmediateHttpResponse(redirect("perfil_cuenta"))
            if not request.user.is_authenticated or (
                (sociallogin.user.email or "").casefold() != (request.user.email or "").casefold()
            ):
                messages.error(request, "El correo de Google debe coincidir con el de tu cuenta.")
                raise ImmediateHttpResponse(redirect("perfil_cuenta"))
            return

        email = (sociallogin.user.email or "").strip().casefold()
        verified = any(
            address.verified and address.email.strip().casefold() == email
            for address in sociallogin.email_addresses
        )
        # Microsoft puede devolver una dirección sin marcarla como verificada.
        # El enlace al buzón confirma su posesión antes de crear la cuenta/sesión.
        try:
            validate_email(email)
            usable_email = len(email) <= 150
        except ValidationError:
            usable_email = False
        if not usable_email or (provider == "google" and not verified):
            messages.error(request, f"{PROVEEDORES[provider]} no proporcionó un correo válido para continuar.")
            raise ImmediateHttpResponse(redirect("acceso"))

        if sociallogin.user.pk:
            user = sociallogin.user
            profile = PerfilUsuario.objects.filter(usuario=user).first()
            linked = SocialAccount.objects.filter(user=user, provider=provider, uid=sociallogin.account.uid).exists()
            if not linked or not user.is_active or profile is None or profile.estado != PerfilUsuario.Estado.ACTIVA or user.email.casefold() != email:
                messages.error(request, "Tu cuenta todavía no está habilitada.")
                raise ImmediateHttpResponse(redirect("acceso"))
            fingerprint = hashlib.sha256(email.encode()).hexdigest()
            if not cache.add(f"bs:social-mail:{fingerprint}", 1, 60):
                messages.info(request, "Revisa tu correo para continuar.")
                raise ImmediateHttpResponse(redirect("social_enviado"))
            try:
                with transaction.atomic():
                    pending, token = SolicitudAccesoSocial.crear(
                        email=email, provider=provider, uid=sociallogin.account.uid,
                        usuario=user,
                    )
                    enviar_enlace_social(request, pending, token)
            except Exception:
                cache.delete(f"bs:social-mail:{fingerprint}")
                logger.exception("Error enviando enlace de acceso social")
                messages.error(request, "No se pudo enviar el enlace. Inténtalo más tarde.")
                raise ImmediateHttpResponse(redirect("acceso"))
            request.session["bs_correo_acceso_enviado"] = email
            raise ImmediateHttpResponse(redirect("social_enviado"))

        # No se enlazan automáticamente cuentas existentes por coincidencia de correo.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists() or PerfilUsuario.objects.filter(correo__iexact=email).exists():
            messages.error(request, "Este correo ya tiene una cuenta. Entra con tu método habitual; no se vinculan cuentas automáticamente.")
            raise ImmediateHttpResponse(redirect("acceso"))

        request.session["bs_social_candidate"] = {
            "email": email,
            "uid": sociallogin.account.uid,
            "provider": provider,
            "nombres": sociallogin.user.first_name,
            "apellidos": sociallogin.user.last_name,
            "vence": (timezone.now() + timedelta(minutes=10)).isoformat(),
        }
        raise ImmediateHttpResponse(redirect("social_completar_microsoft" if provider == "microsoft" else "social_completar"))

    def get_connect_redirect_url(self, request, socialaccount):
        return reverse("perfil_cuenta")
