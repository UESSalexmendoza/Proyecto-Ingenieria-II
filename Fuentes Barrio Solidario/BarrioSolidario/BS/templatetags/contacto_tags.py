from django import template

from BS.views_contacto import puede_ver_contactos

register = template.Library()


@register.filter
def puede_moderar_contactos(usuario):
    return puede_ver_contactos(usuario)


@register.filter
def es_solicitante(usuario):
    from BS.views_solicitudes import tiene_rol_solicitante
    return tiene_rol_solicitante(usuario)


@register.filter
def es_voluntario(usuario):
    from BS.views_voluntariado import rol_voluntario
    return rol_voluntario(usuario)


@register.filter
def puede_revisar_solicitudes(usuario):
    from BS.views_solicitudes import _es_revisor
    return _es_revisor(usuario)
