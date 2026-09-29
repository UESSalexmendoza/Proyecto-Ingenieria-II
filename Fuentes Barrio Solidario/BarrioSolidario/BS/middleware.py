from django.shortcuts import redirect

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
