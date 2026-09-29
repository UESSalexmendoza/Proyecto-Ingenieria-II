"""Pantallas de error de Barrio Solidario."""

from django.shortcuts import render


def pagina_no_encontrada(request):
    """Responde a cualquier URL que no coincida con las rutas anteriores."""
    return render(request, "errores/404.html", status=404)
