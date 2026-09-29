from django.contrib import admin
from django.utils import timezone

from .models import (
    EventoAcceso,
    PerfilUsuario,
    RecuperacionClave,
    Rol,
    RolPermiso,
    UsuarioRol,
    SolicitudCorreccionPerfil,
)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "correo", "telefono", "estado", "acepto_datos_personales_en")
    search_fields = ("correo", "usuario__username")
    list_filter = ("estado",)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(UsuarioRol)
class UsuarioRolAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rol", "estado_aprobacion", "fecha_revision", "activo", "fecha_asignacion")
    list_filter = ("rol", "estado_aprobacion", "activo")
    search_fields = ("usuario__username", "usuario__email")

    def save_model(self, request, obj, form, change):
        if "estado_aprobacion" in form.changed_data:
            obj.fecha_revision = timezone.now() if obj.estado_aprobacion != obj.Aprobacion.PENDIENTE else None
            obj.revisado_por = request.user if obj.fecha_revision else None
        super().save_model(request, obj, form, change)


admin.site.register(RolPermiso)
admin.site.register(RecuperacionClave)
admin.site.register(EventoAcceso)


@admin.register(SolicitudCorreccionPerfil)
class SolicitudCorreccionPerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "estado", "creada_en", "resuelta_en")
    list_filter = ("estado",)
    search_fields = ("usuario__email", "descripcion")

    def save_model(self, request, obj, form, change):
        if "estado" in form.changed_data:
            obj.resuelta_en = timezone.now() if obj.estado == obj.Estado.RESUELTA else None
        super().save_model(request, obj, form, change)
