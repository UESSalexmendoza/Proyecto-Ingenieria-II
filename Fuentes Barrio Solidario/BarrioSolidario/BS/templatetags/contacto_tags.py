from django import template

from BS.views_contacto import puede_ver_contactos

register = template.Library()


@register.filter
def puede_moderar_contactos(usuario):
    return puede_ver_contactos(usuario)
