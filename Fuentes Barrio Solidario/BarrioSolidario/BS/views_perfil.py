"""Perfil, panel y acciones propias del usuario autenticado."""
import json
from io import BytesIO
from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.db import transaction
from django.core.files.base import ContentFile
from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from .forms_cuentas import ROLES_PUBLICOS
from .forms_perfil import PerfilCuentaForm
from .models import EventoAcceso, PerfilUsuario, Rol, UsuarioRol, SolicitudCorreccionPerfil

ROLES_SOLICITABLES = (*ROLES_PUBLICOS, ("PATROCINADOR", "Patrocinador / aliado"))


def _normalizar_avatar(archivo):
    """Conserva el recorte elegido y limita el archivo final a un avatar cuadrado."""
    from PIL import Image, ImageOps

    archivo.seek(0)
    with Image.open(archivo) as original:
        if original.width * original.height > 24_000_000:
            raise ValueError("La imagen supera la resolución permitida.")
        imagen = ImageOps.exif_transpose(original)
        imagen = ImageOps.fit(imagen, (512, 512), method=Image.Resampling.LANCZOS)
        if imagen.mode != "RGB":
            rgba = imagen.convert("RGBA")
            fondo = Image.new("RGB", imagen.size, "white")
            fondo.paste(rgba, mask=rgba.getchannel("A"))
            imagen = fondo
        salida = BytesIO()
        imagen.save(salida, format="JPEG", quality=88, optimize=True)
    return ContentFile(salida.getvalue(), name="avatar_recortado.jpg")

@login_required(login_url="acceso")
def panel_cuenta(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    roles = UsuarioRol.objects.filter(usuario=request.user).select_related("rol")
    return render(request, "panel/inicio.html", {"perfil": perfil, "roles": roles})


@login_required(login_url="acceso")
@require_http_methods(["GET", "POST"])
@csrf_protect
def perfil_cuenta(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    if perfil is None:
        messages.error(request, "Tu cuenta aún no tiene un perfil de Barrio Solidario asociado.")
        return redirect("panel_cuenta")
    if request.method == "POST" and request.POST.get("modo") == "borrador":
        datos = {}
        for nombre in PerfilCuentaForm.base_fields:
            if nombre == "avatar":
                continue
            campo = PerfilCuentaForm.base_fields[nombre]
            datos[nombre] = request.POST.get(nombre) is not None if isinstance(campo.widget, forms.CheckboxInput) else request.POST.get(nombre, "")[:500]
        request.session["bs_perfil_borrador"] = datos
        messages.success(request, "Borrador guardado. La foto se añadirá al guardar el perfil.")
        return redirect("perfil_cuenta")
    form = PerfilCuentaForm(request.POST or None, request.FILES or None, usuario=request.user, perfil=perfil)
    if request.method == "GET" and request.session.get("bs_perfil_borrador"):
        form.initial.update(request.session["bs_perfil_borrador"])
    if request.method == "POST" and request.POST.get("modo") == "final" and request.POST.get("confirmacion_datos") != "1":
        form.add_error(None, "Confirma que los datos son correctos para guardar el perfil.")
    if request.method == "POST" and form.is_valid():
        imagen_avatar = None
        if form.cleaned_data.get("avatar"):
            try:
                imagen_avatar = _normalizar_avatar(form.cleaned_data["avatar"])
            except (OSError, ValueError) as exc:
                form.add_error("avatar", str(exc) if isinstance(exc, ValueError) else "No se pudo procesar la imagen.")
        if not form.errors:
            with transaction.atomic():
                request.user.first_name = form.cleaned_data["nombres"]
                request.user.last_name = form.cleaned_data["apellidos"]
                request.user.save(update_fields=["first_name", "last_name"])
                if perfil:
                    campos = ("telefono", "fecha_nacimiento", "sector_aproximado", "contacto_alternativo",
                          "canal_preferido", "recibir_notificaciones", "alto_contraste", "informacion_adicional",
                          "idioma", "zona_horaria", "disponibilidad", "permitir_ubicacion_aproximada",
                          "compartir_ubicacion_atencion", "recibir_recordatorios", "recibir_mensajes",
                          "recibir_resumen_semanal", "distancia_maxima_km", "notificaciones_desde",
                          "notificaciones_hasta", "modo_silencioso", "tamano_texto", "subrayar_enlaces",
                          "reducir_animaciones", "lectura_simplificada", "lectura_idioma",
                          "ocultar_datos_personales", "permitir_contacto_coordinacion", "permitir_contacto_usuarios",
                          "ocultar_informacion_adicional")
                    for campo in campos:
                        setattr(perfil, campo, form.cleaned_data[campo])
                    if imagen_avatar:
                        perfil.avatar = imagen_avatar
                        campos = (*campos, "avatar")
                    perfil.save(update_fields=[*campos, "actualizado_en"])
            messages.success(request, "Tu perfil se actualizó correctamente.")
            request.session.pop("bs_perfil_borrador", None)
            return redirect("perfil_cuenta")
    roles = UsuarioRol.objects.filter(usuario=request.user).select_related("rol")
    datos = (request.user.first_name, request.user.last_name, request.user.email,
             perfil.telefono if perfil else "", perfil.sector_aproximado if perfil else "",
             perfil.fecha_nacimiento if perfil else None, perfil.contacto_alternativo if perfil else "")
    completitud = round(sum(bool(dato) for dato in datos) / len(datos) * 100)
    sesiones = []
    for sesion in Session.objects.filter(expire_date__gt=timezone.now()):
        if str(sesion.get_decoded().get("_auth_user_id")) == str(request.user.pk):
            sesiones.append({"actual": sesion.session_key == request.session.session_key,
                              "vence": sesion.expire_date})
    return render(request, "perfil/perfil.html", {
        "form": form, "perfil": perfil, "roles": roles, "completitud": completitud,
        "sesiones": sesiones, "eventos": EventoAcceso.objects.filter(usuario=request.user)[:10],
        "correcciones": SolicitudCorreccionPerfil.objects.filter(usuario=request.user).order_by("-creada_en")[:3],
        "roles_disponibles": ROLES_SOLICITABLES,
    })


@login_required(login_url="acceso")
@require_POST
@csrf_protect
def descartar_borrador_perfil(request):
    request.session.pop("bs_perfil_borrador", None)
    messages.info(request, "Se descartó el borrador.")
    return redirect("perfil_cuenta")


@login_required(login_url="acceso")
@require_http_methods(["GET"])
def avatar_cuenta(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    if not perfil or not perfil.avatar:
        raise Http404
    try:
        respuesta = FileResponse(perfil.avatar.open("rb"), content_type="image/png" if perfil.avatar.name.lower().endswith(".png") else "image/jpeg")
        respuesta["Cache-Control"] = "private, no-store"
        return respuesta
    except OSError:
        raise Http404


@login_required(login_url="acceso")
@require_POST
@csrf_protect
def eliminar_avatar_cuenta(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    if perfil and perfil.avatar:
        perfil.avatar.delete(save=True)
    return redirect("perfil_cuenta")


@login_required(login_url="acceso")
@require_POST
@csrf_protect
def solicitar_rol_cuenta(request):
    codigo = request.POST.get("rol", "")
    if codigo not in dict(ROLES_SOLICITABLES):
        messages.error(request, "Selecciona un rol disponible.")
        return redirect("perfil_cuenta")
    with transaction.atomic():
        rol, _ = Rol.objects.get_or_create(codigo=codigo, defaults={"nombre": dict(ROLES_SOLICITABLES)[codigo]})
        if not rol.activo:
            messages.error(request, "Este rol no está disponible.")
        elif UsuarioRol.objects.filter(usuario=request.user, rol=rol).exists():
            messages.info(request, "Ya tienes una solicitud o asignación para ese rol.")
        else:
            UsuarioRol.objects.create(usuario=request.user, rol=rol)
            messages.success(request, "Solicitamos el rol. Podrás ver aquí su estado de aprobación.")
    return redirect("perfil_cuenta")


@login_required(login_url="acceso")
@require_POST
@csrf_protect
def solicitar_correccion_cuenta(request):
    descripcion = request.POST.get("descripcion", "").strip()
    if not 10 <= len(descripcion) <= 500:
        messages.error(request, "Describe la corrección en 10 a 500 caracteres.")
    else:
        SolicitudCorreccionPerfil.objects.create(usuario=request.user, descripcion=descripcion)
        messages.success(request, "Recibimos tu solicitud de corrección.")
    return redirect("perfil_cuenta")


@login_required(login_url="acceso")
@require_http_methods(["GET"])
def descargar_datos_cuenta(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    roles = UsuarioRol.objects.filter(usuario=request.user).select_related("rol")
    datos = {
        "usuario": {"nombres": request.user.first_name, "apellidos": request.user.last_name,
                    "correo": request.user.email, "fecha_registro": request.user.date_joined.isoformat()},
        "perfil": {campo.name: getattr(perfil, campo.name) for campo in perfil._meta.fields
                   if campo.name not in {"usuario", "avatar"}} if perfil else None,
        "avatar": bool(perfil and perfil.avatar),
        "roles": [{"nombre": item.rol.nombre, "estado": item.estado_aprobacion,
                   "fecha_revision": item.fecha_revision, "observacion": item.observacion_revision} for item in roles],
        "solicitudes_correccion": [{"descripcion": item.descripcion, "estado": item.estado,
                                   "creada_en": item.creada_en} for item in
                                  SolicitudCorreccionPerfil.objects.filter(usuario=request.user)],
    }
    respuesta = HttpResponse(json.dumps(datos, ensure_ascii=False, default=str, indent=2), content_type="application/json; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="mis_datos_barrio_solidario.json"'
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@login_required(login_url="acceso")
@require_POST
@csrf_protect
def cerrar_otras_sesiones_cuenta(request):
    for sesion in Session.objects.filter(expire_date__gt=timezone.now()):
        if sesion.session_key != request.session.session_key and str(sesion.get_decoded().get("_auth_user_id")) == str(request.user.pk):
            sesion.delete()
    messages.success(request, "Cerramos las otras sesiones de tu cuenta.")
    return redirect("perfil_cuenta")


@login_required(login_url="acceso")
@require_POST
@csrf_protect
def desactivar_cuenta(request):
    if request.POST.get("confirmacion") != "DESACTIVAR":
        messages.error(request, "Escribe DESACTIVAR para confirmar.")
        return redirect("perfil_cuenta")
    with transaction.atomic():
        PerfilUsuario.objects.filter(usuario=request.user).update(estado=PerfilUsuario.Estado.INACTIVA)
        request.user.is_active = False
        request.user.save(update_fields=["is_active"])
        EventoAcceso.objects.create(usuario=request.user, tipo=EventoAcceso.Tipo.SALIDA)
    logout(request)
    messages.success(request, "Tu cuenta se desactivó. Contacta al equipo si necesitas reactivarla.")
    return redirect("inicio")
