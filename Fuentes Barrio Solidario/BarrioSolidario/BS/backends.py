"""Permisos de roles aprobados, activos y con una cuenta habilitada."""
from django.contrib.auth.backends import BaseBackend
from .models import PerfilUsuario, RolPermiso, UsuarioRol

PERMISOS_HABILITADOS = ("view_casocontacto", "change_casocontacto")


class BarrioRolBackend(BaseBackend):
    def get_all_permissions(self, user_obj, obj=None):
        if obj is not None or not user_obj.is_authenticated or not user_obj.is_active:
            return set()
        if not PerfilUsuario.objects.filter(usuario=user_obj, estado=PerfilUsuario.Estado.ACTIVA).exists():
            return set()
        asignaciones = RolPermiso.objects.filter(
            activo=True, rol__activo=True,
            rol__asignaciones__usuario=user_obj,
            rol__asignaciones__activo=True,
            rol__asignaciones__estado_aprobacion=UsuarioRol.Aprobacion.APROBADO,
            permiso__content_type__app_label="BS",
            permiso__codename__in=PERMISOS_HABILITADOS,
        ).values_list("permiso__content_type__app_label", "permiso__codename")
        return {f"{app}.{codigo}" for app, codigo in asignaciones}
