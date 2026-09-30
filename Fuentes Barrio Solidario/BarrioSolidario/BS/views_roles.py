"""Catálogo de roles y permisos efectivos de Barrio Solidario."""
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from .forms_roles import RolForm, PermisosRolForm
from .backends import PERMISOS_HABILITADOS
from .models import CambioRol, Rol, RolPermiso, UsuarioRol

logger = logging.getLogger(__name__)
# Solo exponemos permisos de módulos con comprobación de autorización implementada.


def _admin(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied("La configuración de roles requiere una cuenta administradora.")


def _permisos():
    return list(Permission.objects.filter(content_type__app_label="BS",
                                          codename__in=PERMISOS_HABILITADOS).order_by("codename"))


def _datos(rol, permitidos=None):
    return {"nombre": rol.nombre, "codigo": rol.codigo, "descripcion": rol.descripcion,
            "activo": rol.activo, "permisos": sorted(permitidos if permitidos is not None else
                 RolPermiso.objects.filter(rol=rol, activo=True).values_list("permiso__codename", flat=True))}


def _auditar(request, rol, accion, motivo, antes=None, despues=None):
    CambioRol.objects.create(rol=rol, actor=request.user, accion=accion,
                            motivo=motivo, antes=antes or {}, despues=despues or {})


def _borradores(request):
    return sum(clave.startswith("bs_borrador_rol_") for clave in request.session.keys())


@login_required(login_url="acceso")
def roles_panel(request):
    _admin(request)
    q = request.GET.get("q", "").strip()[:80]
    roles = Rol.objects.annotate(usuarios=Count("asignaciones__usuario", distinct=True)).order_by("nombre")
    if q:
        roles = roles.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q))
    return render(request, "roles/lista.html", {
        "roles": roles, "q": q, "total_roles": Rol.objects.count(),
        "usuarios_con_rol": UsuarioRol.objects.filter(activo=True, rol__activo=True).values("usuario_id").distinct().count(),
        "permisos_disponibles": len(_permisos()), "borradores": _borradores(request),
    })


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def crear_rol(request):
    _admin(request)
    form = RolForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            with transaction.atomic():
                rol = Rol.objects.create(codigo=d["codigo"], nombre=d["nombre"],
                                         descripcion=d["descripcion"], activo=d["activo"])
                _auditar(request, rol, "CREACION", "Rol creado desde el panel.", despues=_datos(rol))
        except IntegrityError:
            form.add_error("codigo", "Este código ya se encuentra registrado.")
        else:
            messages.success(request, "Rol creado. Ahora puedes configurar sus permisos.")
            return redirect("rol_detalle", pk=rol.pk)
    return render(request, "roles/nuevo.html", {"form": form})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def rol_detalle(request, pk):
    _admin(request)
    rol = get_object_or_404(Rol, pk=pk)
    disponibles = _permisos()
    permitidos_ids = {p.pk for p in disponibles}
    activos = set(RolPermiso.objects.filter(rol=rol, activo=True, permiso_id__in=permitidos_ids)
                  .values_list("permiso_id", flat=True))
    borrador_clave = f"bs_borrador_rol_{rol.pk}"
    borrador = request.session.get(borrador_clave)
    inicial = {"codigo": rol.codigo, "nombre": rol.nombre, "descripcion": rol.descripcion, "activo": rol.activo}
    datos_form = RolForm(initial=inicial, instancia=rol)
    permisos_form = PermisosRolForm(disponibles=disponibles, initial={
        "permisos": borrador["permisos"] if borrador else [str(pk) for pk in activos],
        "motivo": borrador["motivo"] if borrador else "",
    })
    if request.method == "POST":
        accion = request.POST.get("accion", "")
        if accion == "datos":
            datos_form = RolForm(request.POST, instancia=rol, initial=inicial)
            if datos_form.is_valid():
                d = datos_form.cleaned_data
                with transaction.atomic():
                    rol = Rol.objects.select_for_update().get(pk=rol.pk)
                    antes = _datos(rol)
                    rol.nombre, rol.descripcion, rol.activo = d["nombre"], d["descripcion"], d["activo"]
                    rol.save(update_fields=["nombre", "descripcion", "activo"])
                    _auditar(request, rol, "DATOS", "Actualización de información del rol.", antes, _datos(rol))
                messages.success(request, "Se actualizaron los datos del rol.")
                return redirect("rol_detalle", pk=pk)
        elif accion in ("borrador", "aplicar"):
            post = request.POST.copy()
            if accion == "borrador":
                post["confirmacion"] = "on"
            permisos_form = PermisosRolForm(post, disponibles=disponibles)
            if permisos_form.is_valid():
                elegidos = set(map(int, permisos_form.cleaned_data["permisos"]))
                motivo = permisos_form.cleaned_data["motivo"]
                if accion == "borrador":
                    request.session[borrador_clave] = {"permisos": sorted(map(str, elegidos)), "motivo": motivo}
                    request.session.modified = True
                    messages.success(request, "El borrador quedó guardado en esta sesión. Los permisos aún no han cambiado.")
                    return redirect("rol_detalle", pk=pk)
                try:
                    with transaction.atomic():
                        rol = Rol.objects.select_for_update().get(pk=rol.pk)
                        anteriores = set(RolPermiso.objects.filter(rol=rol, activo=True, permiso_id__in=permitidos_ids)
                                        .values_list("permiso_id", flat=True))
                        configurados = set(RolPermiso.objects.filter(rol=rol, permiso_id__in=permitidos_ids)
                                           .values_list("permiso_id", flat=True))
                        if anteriores == elegidos and configurados == permitidos_ids:
                            messages.info(request, "No hubo cambios de permisos.")
                        else:
                            antes = _datos(rol)
                            for identificador in permitidos_ids:
                                RolPermiso.objects.update_or_create(
                                    rol=rol, permiso_id=identificador,
                                    defaults={"activo": identificador in elegidos})
                            _auditar(request, rol, "PERMISOS", motivo, antes, _datos(rol))
                            messages.success(request, "Permisos actualizados y cambio registrado en auditoría.")
                except IntegrityError:
                    logger.exception("Conflicto al cambiar permisos del rol %s", pk)
                    permisos_form.add_error(None, "No se pudieron aplicar los permisos. Inténtalo nuevamente.")
                else:
                    request.session.pop(borrador_clave, None)
                    return redirect("rol_detalle", pk=pk)
        elif accion == "descartar":
            request.session.pop(borrador_clave, None)
            messages.info(request, "Borrador descartado.")
            return redirect("rol_detalle", pk=pk)
        else:
            raise PermissionDenied("Acción no permitida.")
    afectados = UsuarioRol.objects.filter(rol=rol, activo=True, estado_aprobacion=UsuarioRol.Aprobacion.APROBADO).count()
    historial = CambioRol.objects.filter(rol=rol).select_related("actor")[:12]
    usuarios = UsuarioRol.objects.filter(rol=rol).select_related("usuario").order_by("-fecha_asignacion")[:8]
    return render(request, "roles/detalle.html", {
        "rol": rol, "roles": Rol.objects.annotate(usuarios=Count("asignaciones__usuario", distinct=True)).order_by("nombre"),
        "datos_form": datos_form, "permisos_form": permisos_form, "disponibles": disponibles,
        "activos": activos, "borrador": borrador, "afectados": afectados,
        "historial": historial, "usuarios": usuarios, "accion_actual": request.POST.get("accion") if request.method == "POST" else "",
        "ultima_revision": historial[0] if historial else None,
    })


@login_required(login_url="acceso")
@csrf_protect
@require_POST
def duplicar_rol(request, pk):
    _admin(request)
    with transaction.atomic():
        original = get_object_or_404(Rol.objects.select_for_update(), pk=pk)
        codigo_base = original.codigo[:25]
        for numero in range(1, 100):
            codigo = f"{codigo_base}_C{numero}"
            if not Rol.objects.filter(codigo=codigo).exists():
                break
        else:
            messages.error(request, "No hay códigos disponibles para duplicar este rol.")
            return redirect("rol_detalle", pk=pk)
        nuevo = Rol.objects.create(codigo=codigo, nombre=f"Copia de {original.nombre}"[:80],
                                   descripcion=original.descripcion, activo=False)
        for relacion in RolPermiso.objects.filter(rol=original, activo=True):
            RolPermiso.objects.create(rol=nuevo, permiso=relacion.permiso, activo=True)
        _auditar(request, nuevo, "DUPLICACION", f"Copia del rol {original.codigo} (#{original.pk}); inicia inactivo.",
                 despues=_datos(nuevo))
    messages.success(request, "Rol duplicado como inactivo. Revisa sus datos y permisos antes de activarlo.")
    return redirect("rol_detalle", pk=nuevo.pk)


@login_required(login_url="acceso")
@csrf_protect
@require_POST
def desactivar_rol(request, pk):
    _admin(request)
    motivo = " ".join(request.POST.get("motivo", "").split())[:500]
    if len(motivo) < 10 or "<" in motivo or ">" in motivo:
        messages.error(request, "Escribe un motivo de al menos 10 caracteres sin código HTML.")
        return redirect("rol_detalle", pk=pk)
    with transaction.atomic():
        rol = get_object_or_404(Rol.objects.select_for_update(), pk=pk)
        if rol.activo:
            antes = _datos(rol)
            rol.activo = False
            rol.save(update_fields=["activo"])
            _auditar(request, rol, "DESACTIVACION", motivo, antes, _datos(rol))
            messages.success(request, "Rol desactivado. Ya no concede acceso a sus usuarios asignados.")
        else:
            messages.info(request, "El rol ya estaba desactivado.")
    return redirect("rol_detalle", pk=pk)
