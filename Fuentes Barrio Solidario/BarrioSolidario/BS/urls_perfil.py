from django.urls import path

from . import views_cuentas, views_perfil

urlpatterns = [
    path("panel/", views_perfil.panel_cuenta, name="panel_cuenta"),
    path("perfil/", views_perfil.perfil_cuenta, name="perfil_cuenta"),
    path("perfil/borrador/descartar/", views_perfil.descartar_borrador_perfil, name="descartar_borrador_perfil"),
    path("perfil/avatar/", views_perfil.avatar_cuenta, name="avatar_cuenta"),
    path("perfil/avatar/eliminar/", views_perfil.eliminar_avatar_cuenta, name="eliminar_avatar_cuenta"),
    path("perfil/rol/solicitar/", views_perfil.solicitar_rol_cuenta, name="solicitar_rol_cuenta"),
    path("perfil/correccion/solicitar/", views_perfil.solicitar_correccion_cuenta, name="solicitar_correccion_cuenta"),
    path("perfil/datos/descargar/", views_perfil.descargar_datos_cuenta, name="descargar_datos_cuenta"),
    path("perfil/sesiones/cerrar-otras/", views_perfil.cerrar_otras_sesiones_cuenta, name="cerrar_otras_sesiones_cuenta"),
    path("perfil/desactivar/", views_perfil.desactivar_cuenta, name="desactivar_cuenta"),
    path("perfil/clave/", views_cuentas.cambiar_clave_cuenta, name="cambiar_clave_cuenta"),
]
