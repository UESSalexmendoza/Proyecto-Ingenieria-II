"""Tablero administrativo y panel personal."""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from .models import ActuacionContacto, CasoContacto, InstitucionAval, PerfilUsuario, UsuarioRol


def _puede_moderar(usuario):
    from .views_contacto import puede_ver_contactos
    return puede_ver_contactos(usuario)


def _resumen(estados, conteos, total):
    return [{"nombre": nombre, "cantidad": conteos.get(codigo, 0),
             "porcentaje": round(100 * conteos.get(codigo, 0) / total) if total else 0}
            for codigo, nombre in estados]


@login_required(login_url="acceso")
def panel_cuenta(request):
    usuario = request.user
    if not usuario.is_superuser and not _puede_moderar(usuario):
        from .views_solicitudes import tiene_rol_solicitante, panel_solicitante
        if tiene_rol_solicitante(usuario):
            return panel_solicitante(request)
        from .views_voluntariado import rol_voluntario, panel_voluntario
        if rol_voluntario(usuario):
            return panel_voluntario(request)
    if not _puede_moderar(usuario):
        return render(request, "panel/inicio_usuario.html", {
            "perfil": PerfilUsuario.objects.filter(usuario=usuario).first(),
            "roles": UsuarioRol.objects.filter(usuario=usuario).select_related("rol"),
        })

    ahora = timezone.now()
    hoy = timezone.localdate()
    casos = CasoContacto.objects.all()
    conteos_casos = dict(casos.values("estado").annotate(n=Count("pk")).values_list("estado", "n"))
    total_casos = sum(conteos_casos.values())
    perfiles = PerfilUsuario.objects.all()
    conteos_perfiles = dict(perfiles.values("estado").annotate(n=Count("pk")).values_list("estado", "n"))
    total_perfiles = sum(conteos_perfiles.values())
    roles_pendientes = UsuarioRol.objects.filter(activo=True, estado_aprobacion=UsuarioRol.Aprobacion.PENDIENTE)
    pendientes = casos.filter(estado=CasoContacto.Estado.PENDIENTE)
    abiertos = casos.exclude(estado=CasoContacto.Estado.CERRADO)
    context = {
        "es_superusuario": usuario.is_superuser,
        "actualizado_en": ahora,
        "usuarios_pendientes": roles_pendientes.values("usuario_id").distinct().count() if usuario.is_superuser else None,
        "contactos_pendientes": conteos_casos.get(CasoContacto.Estado.PENDIENTE, 0),
        "contactos_revision": conteos_casos.get(CasoContacto.Estado.EN_REVISION, 0),
        "contactos_abiertos": abiertos.count(),
        "correos_pendientes": casos.filter(notificacion_estado_pendiente=True).count(),
        "instituciones_activas": InstitucionAval.objects.filter(activa=True).count() if usuario.is_superuser else None,
        "contactos_recientes": pendientes.order_by("creado_en")[:4],
        "roles_recientes": roles_pendientes.select_related("usuario", "rol").order_by("fecha_asignacion")[:3] if usuario.is_superuser else [],
        "actividad": ActuacionContacto.objects.select_related("caso", "actor").order_by("-fecha")[:5],
        "estados_contacto": _resumen(CasoContacto.Estado.choices, conteos_casos, total_casos),
        "estados_usuario": _resumen(PerfilUsuario.Estado.choices, conteos_perfiles, total_perfiles) if usuario.is_superuser else [],
        "casos_antiguos": abiertos.filter(creado_en__lt=ahora - timedelta(days=2)).count(),
        "contactos_hoy": casos.filter(creado_en__date=hoy).count(),
        "revisiones_hoy": ActuacionContacto.objects.filter(tipo=ActuacionContacto.Tipo.REVISION, fecha__date=hoy).count(),
        "cierres_hoy": casos.filter(estado=CasoContacto.Estado.CERRADO, revisado_en__date=hoy).count(),
    }
    return render(request, "panel/inicio.html", context)
