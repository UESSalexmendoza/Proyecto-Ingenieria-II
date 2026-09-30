"""Gestión de instituciones desde el panel del usuario administrador."""
from io import BytesIO

from PIL import Image, ImageOps
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from .forms_instituciones import InstitucionAvalForm
from .models import InstitucionAval


def _administrador(usuario):
    return usuario.is_authenticated and usuario.is_active and usuario.is_superuser


solo_admin = user_passes_test(_administrador, login_url="panel_cuenta")


def _normalizar_imagen(archivo):
    archivo.seek(0)
    with Image.open(archivo) as original:
        imagen = ImageOps.exif_transpose(original)
        if imagen.width * imagen.height > 24_000_000:
            raise ValueError("La imagen supera la resolución permitida.")
        # El navegador envía el recorte elegido. Para cargas sin JavaScript,
        # centramos la imagen a la misma relación de aspecto del card (5:3).
        imagen = ImageOps.fit(imagen.convert("RGBA"), (900, 540), method=Image.Resampling.LANCZOS)
        salida = BytesIO()
        imagen.save(salida, format="PNG", optimize=True)
    if salida.tell() > 4 * 1024 * 1024:
        raise ValueError("El recorte es demasiado grande; prueba otra imagen.")
    return ContentFile(salida.getvalue(), name="institucion.png")


@solo_admin
@require_http_methods(["GET"])
def lista(request):
    return render(request, "instituciones/lista.html", {
        "instituciones": InstitucionAval.objects.all(),
    })


@solo_admin
@csrf_protect
@require_http_methods(["GET", "POST"])
def editar(request, pk=None):
    institucion = get_object_or_404(InstitucionAval, pk=pk) if pk is not None else None
    form = InstitucionAvalForm(request.POST or None, request.FILES or None, instance=institucion)
    if request.method == "POST" and form.is_valid():
        objeto = form.save(commit=False)
        archivo = form.cleaned_data.get("imagen")
        if archivo:
            try:
                objeto.imagen = _normalizar_imagen(archivo)
            except (OSError, ValueError) as exc:
                form.add_error("imagen", str(exc) if isinstance(exc, ValueError) else "No se pudo procesar la imagen.")
        if not form.errors:
            anterior = institucion.imagen.name if institucion and archivo else None
            objeto.save()
            if anterior and anterior != objeto.imagen.name:
                objeto.imagen.storage.delete(anterior)
            messages.success(request, "Institución guardada correctamente.")
            return redirect("instituciones_panel")
    return render(request, "instituciones/formulario.html", {"form": form, "institucion": institucion})


@solo_admin
@csrf_protect
@require_POST
def eliminar(request, pk):
    institucion = get_object_or_404(InstitucionAval, pk=pk)
    archivo = institucion.imagen.name
    institucion.delete()
    if archivo:
        institucion.imagen.storage.delete(archivo)
    messages.success(request, "Institución eliminada.")
    return redirect("instituciones_panel")
