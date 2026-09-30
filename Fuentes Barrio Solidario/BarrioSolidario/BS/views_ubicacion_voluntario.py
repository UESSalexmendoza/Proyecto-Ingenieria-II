"""Ubicación aproximada voluntaria para sugerencias por distancia."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .models import PerfilUsuario, UsuarioRol


class UbicacionVoluntarioForm(forms.Form):
    latitud = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitud = forms.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)
    distancia_maxima_km = forms.IntegerField(min_value=1, max_value=100)
    consentimiento = forms.BooleanField(required=True)


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def ubicacion_voluntario(request):
    autorizado = UsuarioRol.objects.filter(usuario=request.user, rol__codigo="VOLUNTARIO", rol__activo=True,
        activo=True, estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).exists()
    if not autorizado:
        raise PermissionDenied("Esta opción requiere un rol de voluntario aprobado.")
    perfil = PerfilUsuario.objects.filter(usuario=request.user, estado=PerfilUsuario.Estado.ACTIVA).first()
    if not perfil:
        raise PermissionDenied("El perfil debe estar activo.")
    if request.method == "POST" and request.POST.get("accion") == "revocar":
        perfil.permitir_ubicacion_aproximada = False
        perfil.latitud_ubicacion = None
        perfil.longitud_ubicacion = None
        perfil.ubicacion_actualizada_en = timezone.now()
        perfil.save(update_fields=["permitir_ubicacion_aproximada", "latitud_ubicacion",
                                    "longitud_ubicacion", "ubicacion_actualizada_en", "actualizado_en"])
        messages.success(request, "La ubicación fue retirada y ya no se usará para sugerir asignaciones.")
        return redirect("panel_cuenta")
    form = UbicacionVoluntarioForm(request.POST or None, initial={
        "latitud": perfil.latitud_ubicacion, "longitud": perfil.longitud_ubicacion,
        "distancia_maxima_km": perfil.distancia_maxima_km,
        "consentimiento": perfil.permitir_ubicacion_aproximada,
    })
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        perfil.latitud_ubicacion, perfil.longitud_ubicacion = d["latitud"], d["longitud"]
        perfil.distancia_maxima_km = d["distancia_maxima_km"]
        perfil.permitir_ubicacion_aproximada = True
        perfil.ubicacion_actualizada_en = timezone.now()
        perfil.save(update_fields=["latitud_ubicacion", "longitud_ubicacion", "distancia_maxima_km",
                                   "permitir_ubicacion_aproximada", "ubicacion_actualizada_en", "actualizado_en"])
        messages.success(request, "Tu ubicación aproximada y radio de cobertura fueron guardados.")
        return redirect("panel_cuenta")
    return render(request, "solicitudes/ubicacion_voluntario.html", {"form": form})
