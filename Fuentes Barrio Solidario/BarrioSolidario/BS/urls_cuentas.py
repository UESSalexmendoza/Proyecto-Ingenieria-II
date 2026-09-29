from django.urls import path, include
from django.views.generic import RedirectView

from . import views_cuentas, views_social

urlpatterns = [
    path("cuenta/aceptar-datos-personales/", views_cuentas.aceptar_datos_personales, name="aceptar_datos_personales"),
    path("registro/google/completar/", views_social.completar_registro_google, name="social_completar"),
    path("registro/google/enviado/", views_social.enlace_enviado, name="social_enviado"),
    path("registro/google/confirmar/<str:token>/", views_social.confirmar_acceso_social, name="social_confirmar"),
    path("acceso/", views_cuentas.acceso, name="acceso"),
    path("registro/", views_cuentas.registro, name="registro"),
    path("registro/enviado/", views_cuentas.registro_enviado, name="registro_enviado"),
    path("registro/reenviar/", views_cuentas.reenviar_activacion, name="reenviar_activacion"),
    path("activar/<uidb64>/<token>/", views_cuentas.activar_cuenta, name="activar_cuenta"),
    path("cuenta/panel/", RedirectView.as_view(pattern_name="panel_cuenta", permanent=False)),
    path("cuenta/perfil/", RedirectView.as_view(pattern_name="perfil_cuenta", permanent=False)),
    path("cuenta/clave/", RedirectView.as_view(pattern_name="cambiar_clave_cuenta", permanent=False)),
    path("cuenta/salir/", views_cuentas.cerrar_sesion_cuenta, name="cerrar_sesion_cuenta"),
    path("recuperar-clave/", views_cuentas.recuperar_clave, name="recuperar_clave"),
    path("recuperar-clave/enviado/", views_cuentas.recuperacion_enviada, name="recuperacion_enviada"),
    path("recuperar-clave/<uidb64>/<token>/", views_cuentas.restablecer_clave, name="restablecer_clave"),
    path("recuperar-clave/completado/", views_cuentas.recuperacion_completada, name="recuperacion_completada"),
    path("", include("BS.urls_perfil")),
]
