from django.shortcuts import redirect
from django.shortcuts import render
from django.conf import settings

from .models import PerfilUsuario


class ConsentimientoDatosMiddleware:
    """Solicita la aceptación al abrir la primera sesión del usuario."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        nombre = request.resolver_match.url_name if request.resolver_match else None
        if nombre in {"aceptar_datos_personales", "datos_personales", "cerrar_sesion_cuenta"}:
            return None
        if PerfilUsuario.objects.filter(
            usuario=request.user, acepto_datos_personales_en__isnull=True,
        ).exists():
            return redirect("aceptar_datos_personales")
        return None


class PaginaNoEncontradaMiddleware:
    """Presenta la misma página 404 incluso con DEBUG activado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404 or request.method not in {"GET", "HEAD"}:
            return response
        path = request.path_info
        exclusions = ("/admin/", "/" + settings.STATIC_URL.lstrip("/"))
        if settings.MEDIA_URL:
            exclusions += ("/" + settings.MEDIA_URL.lstrip("/"),)
        if any(prefix and path.startswith(prefix) for prefix in exclusions):
            return response
        if "text/html" not in request.headers.get("Accept", "text/html"):
            return response
        return render(request, "errores/404.html", status=404)
