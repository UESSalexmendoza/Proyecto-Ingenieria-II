"""Recepción y revisión de casos enviados desde el portal público."""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_http_methods

from .forms_contacto import CasoContactoForm, RevisionCasoForm
from .models import ActuacionContacto, CasoContacto, UsuarioRol, RolPermiso
from .services_contacto import guardar_revision

logger = logging.getLogger(__name__)


def puede_revisar_contactos(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser or user.has_perm("BS.change_casocontacto"):
        return True
    # Conserva el acceso de moderadores anteriores hasta configurar explícitamente
    # el permiso del rol; después, la revocación desde Roles sí tiene efecto.
    configurado = RolPermiso.objects.filter(
        rol__codigo__iexact="MODERADOR", permiso__codename="change_casocontacto",
        permiso__content_type__app_label="BS",
    ).exists()
    return not configurado and UsuarioRol.objects.filter(
        usuario=user, rol__codigo__iexact="MODERADOR", rol__activo=True,
        activo=True, estado_aprobacion=UsuarioRol.Aprobacion.APROBADO,
    ).exists()


def puede_ver_contactos(user):
    return (puede_revisar_contactos(user) or
            bool(user.is_authenticated and user.is_active and user.has_perm("BS.view_casocontacto")))


def _enviar_acuse(caso, request):
    enlace = request.build_absolute_uri(reverse("inicio"))
    contexto = {"nombre": caso.nombre, "referencia": caso.pk, "enlace": enlace}
    correo = EmailMultiAlternatives(
        subject=f"Recibimos tu mensaje | Barrio Solidario #{caso.pk}",
        body=(f"Hola {caso.nombre}:\n\nHemos recibido tu mensaje (caso #{caso.pk}). "
              "Nuestro equipo revisará la información y responderá a este correo "
              "una vez que el caso haya sido analizado.\n\nEquipo Barrio Solidario"),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[caso.email],
    )
    correo.attach_alternative(render_to_string("contacto/correo_contacto.html", contexto), "text/html")
    # La cabecera existente del proyecto usa el logo UEES embebido mediante CID.
    from .views_cuentas import _adjuntar_logo_uees
    _adjuntar_logo_uees(correo)
    correo.send(fail_silently=False)


@csrf_protect
@require_POST
def registrar(request):
    form = CasoContactoForm(request.POST)
    if not form.is_valid():
        from .models import InstitucionAval
        return render(request, "publica/index.html", {
            "instituciones": InstitucionAval.objects.filter(activa=True),
            "contacto_form": form,
        }, status=400)
    caso = form.save()  # Estado PENDIENTE por defecto, aun si falla SMTP.
    actuacion = ActuacionContacto.objects.create(
        caso=caso, tipo=ActuacionContacto.Tipo.CREACION,
        estado_nuevo=caso.estado, resultado_correo=ActuacionContacto.Correo.PENDIENTE,
    )
    try:
        _enviar_acuse(caso, request)
    except Exception:
        logger.exception("No se pudo enviar el acuse del caso de contacto %s", caso.pk)
        actuacion.resultado_correo = ActuacionContacto.Correo.FALLIDO
        actuacion.save(update_fields=["resultado_correo"])
        messages.warning(request, f"Registramos tu mensaje con el número #{caso.pk}, pero no pudimos enviar la confirmación por correo. Nuestro equipo revisará el caso.")
    else:
        caso.acuse_enviado_en = timezone.now()
        caso.save(update_fields=["acuse_enviado_en"])
        actuacion.resultado_correo = ActuacionContacto.Correo.ENVIADO
        actuacion.save(update_fields=["resultado_correo"])
        messages.success(request, f"Recibimos tu mensaje. El caso #{caso.pk} está pendiente de revisión y enviamos una confirmación a {caso.email}.")
    return redirect(reverse("inicio") + "#contacto")


@login_required(login_url="acceso")
def lista(request):
    if not puede_ver_contactos(request.user):
        raise PermissionDenied
    casos = CasoContacto.objects.select_related("revisado_por").all()
    estado = request.GET.get("estado", "")
    if estado in CasoContacto.Estado.values:
        casos = casos.filter(estado=estado)
    return render(request, "contacto/lista.html", {"casos": casos[:100], "estado": estado, "estados": CasoContacto.Estado.choices})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def detalle(request, pk):
    if not puede_ver_contactos(request.user) or (request.method == "POST" and not puede_revisar_contactos(request.user)):
        raise PermissionDenied
    caso = get_object_or_404(CasoContacto, pk=pk)
    form = RevisionCasoForm(request.POST or None, instance=caso)
    if request.method == "POST" and form.is_valid():
        guardado, notificado = guardar_revision(
            caso.pk, actor=request.user,
            nuevo_estado=form.cleaned_data["estado"],
            nota=form.cleaned_data["nota_revision"], request=request,
        )
        if not guardado:
            messages.info(request, "No había cambios para guardar.")
        elif notificado is False:
            messages.warning(request, "La actuación quedó guardada, pero no se pudo enviar el correo de actualización. La notificación sigue pendiente y puede reintentarse guardando nuevamente.")
        elif notificado is True:
            messages.success(request, "Actuación guardada y actualización enviada al correo del remitente.")
        else:
            messages.success(request, "La actuación quedó guardada en el historial.")
        return redirect("contacto_detalle", pk=pk)
    return render(request, "contacto/detalle.html", {
        "caso": caso, "form": form, "puede_editar": puede_revisar_contactos(request.user),
        "actuaciones": caso.actuaciones.select_related("actor"),
    })
