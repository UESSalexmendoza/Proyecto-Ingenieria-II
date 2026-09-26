from django.urls import path

from . import views_cuentas

urlpatterns = [
    path("acceso/", views_cuentas.acceso, name="acceso"),
    path("registro/", views_cuentas.registro, name="registro"),
    path("registro/enviado/", views_cuentas.registro_enviado, name="registro_enviado"),
    path("registro/reenviar/", views_cuentas.reenviar_activacion, name="reenviar_activacion"),
    path("activar/<uidb64>/<token>/", views_cuentas.activar_cuenta, name="activar_cuenta"),
    path("cuenta/panel/", views_cuentas.panel_cuenta, name="panel_cuenta"),
    path("cuenta/perfil/", views_cuentas.perfil_cuenta, name="perfil_cuenta"),
    path("cuenta/clave/", views_cuentas.cambiar_clave_cuenta, name="cambiar_clave_cuenta"),
    path("cuenta/salir/", views_cuentas.cerrar_sesion_cuenta, name="cerrar_sesion_cuenta"),
    path("recuperar-clave/", views_cuentas.recuperar_clave, name="recuperar_clave"),
    path("recuperar-clave/enviado/", views_cuentas.recuperacion_enviada, name="recuperacion_enviada"),
    path("recuperar-clave/<uidb64>/<token>/", views_cuentas.restablecer_clave, name="restablecer_clave"),
    path("recuperar-clave/completado/", views_cuentas.recuperacion_completada, name="recuperacion_completada"),
]
