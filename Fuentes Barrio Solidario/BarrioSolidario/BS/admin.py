from django.contrib import admin

from .models import (
    EventoAcceso,
    PerfilUsuario,
    RecuperacionClave,
    Rol,
    RolPermiso,
    UsuarioRol,
)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "correo", "telefono", "estado")
    search_fields = ("correo", "usuario__username")
    list_filter = ("estado",)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(UsuarioRol)
class UsuarioRolAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rol", "activo", "fecha_asignacion")
    list_filter = ("rol", "activo")


admin.site.register(RolPermiso)
admin.site.register(RecuperacionClave)
admin.site.register(EventoAcceso)