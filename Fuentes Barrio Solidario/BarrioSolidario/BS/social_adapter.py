"""Acceso social únicamente para cuentas de Barrio Solidario ya registradas."""
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import PerfilUsuario


class BarrioSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        # El alta y la aprobación continúan a cargo del flujo del MVP.
        return False

    def pre_social_login(self, request, sociallogin):
        usuario = sociallogin.user
        if usuario.pk:
            perfil = PerfilUsuario.objects.filter(usuario_id=usuario.pk).first()
            if not usuario.is_active or (perfil and perfil.estado != PerfilUsuario.Estado.ACTIVA):
                messages.error(request, "Tu cuenta todavía no está habilitada para iniciar sesión.")
                raise ImmediateHttpResponse(redirect("acceso"))

    def get_connect_redirect_url(self, request, socialaccount):
        return reverse("perfil_cuenta")
