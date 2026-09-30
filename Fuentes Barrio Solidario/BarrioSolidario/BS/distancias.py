"""Distancia aproximada para una futura asignación por radio de cobertura."""
from math import asin, cos, radians, sin, sqrt


def distancia_km(latitud_origen, longitud_origen, latitud_destino, longitud_destino):
    """Distancia geodésica estimada; no equivale a distancia vial ni duración."""
    a1, o1, a2, o2 = map(lambda v: radians(float(v)),
                         (latitud_origen, longitud_origen, latitud_destino, longitud_destino))
    dlat, dlon = a2 - a1, o2 - o1
    hav = sin(dlat / 2) ** 2 + cos(a1) * cos(a2) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(min(1, sqrt(hav)))


def candidatos_en_radio(solicitud):
    """Genera pares (usuario, distancia) de voluntarios con ubicación autorizada."""
    from .models import PerfilUsuario, UsuarioRol
    if solicitud.latitud is None or solicitud.longitud is None:
        return []
    perfiles = PerfilUsuario.objects.filter(
        estado=PerfilUsuario.Estado.ACTIVA, usuario__is_active=True,
        permitir_ubicacion_aproximada=True,
        latitud_ubicacion__isnull=False, longitud_ubicacion__isnull=False,
        usuario__roles_barrio__rol__codigo="VOLUNTARIO",
        usuario__roles_barrio__rol__activo=True,
        usuario__roles_barrio__activo=True,
        usuario__roles_barrio__estado_aprobacion=UsuarioRol.Aprobacion.APROBADO,
    ).select_related("usuario").distinct()
    candidatos = []
    for perfil in perfiles:
        km = distancia_km(solicitud.latitud, solicitud.longitud,
                          perfil.latitud_ubicacion, perfil.longitud_ubicacion)
        if km <= perfil.distancia_maxima_km:
            candidatos.append((perfil.usuario, round(km, 2)))
    return sorted(candidatos, key=lambda item: item[1])
