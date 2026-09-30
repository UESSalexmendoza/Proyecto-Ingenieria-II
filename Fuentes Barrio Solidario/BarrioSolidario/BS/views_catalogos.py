"""Catálogos del sistema con borradores, publicación y auditoría."""
import csv
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from .forms_catalogos import CatalogoForm, ValorForm, PublicacionForm
from .models import BorradorCatalogo, CambioCatalogo, CatalogoSistema, ValorCatalogo


def _admin(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied("La administración de catálogos requiere una cuenta administradora.")


def _foto(catalogo):
    return {
        "codigo": catalogo.codigo, "nombre": catalogo.nombre, "descripcion": catalogo.descripcion,
        "activo": catalogo.activo, "visible_formularios": catalogo.visible_formularios,
        "valores": [{"clave": str(v.pk), "codigo": v.codigo, "nombre": v.nombre,
                     "descripcion": v.descripcion, "orden": v.orden, "activo": v.activo,
                     "disponible_nuevas": v.disponible_nuevas,
                     "requiere_ubicacion": v.requiere_ubicacion,
                     "requiere_validacion": v.requiere_validacion}
                    for v in catalogo.valores.all().order_by("orden", "pk")],
    }


def _borrador(catalogo, usuario):
    obj, _ = BorradorCatalogo.objects.get_or_create(
        catalogo=catalogo, actor=usuario,
        defaults={"version_base": catalogo.version, "datos": _foto(catalogo)})
    return obj


def _guardar(borrador, datos):
    borrador.datos = datos
    borrador.save(update_fields=["datos", "actualizado_en"])


def _validar(datos, catalogo):
    cabecera = CatalogoForm(datos, instancia=catalogo, initial={"codigo": catalogo.codigo})
    if not cabecera.is_valid():
        raise ValueError("Revisa los datos del catálogo antes de publicar.")
    codigos = set()
    claves = set()
    limpios = []
    for valor in datos.get("valores", []):
        formulario = ValorForm(valor)
        if not formulario.is_valid():
            raise ValueError(f"Revisa el valor {valor.get('codigo', '(sin código)')} antes de publicar.")
        limpio = formulario.cleaned_data
        clave = str(valor.get("clave", ""))
        if clave in claves or limpio["codigo"].casefold() in codigos:
            raise ValueError("Hay identificadores o códigos de valores repetidos.")
        if not clave.startswith("nuevo-"):
            try:
                original = ValorCatalogo.objects.get(pk=int(clave), catalogo=catalogo)
            except (ValueError, ValorCatalogo.DoesNotExist):
                raise ValueError("Un valor ya no pertenece a este catálogo.") from None
            if original.codigo != limpio["codigo"]:
                raise ValueError("El código de un valor publicado no se puede modificar.")
        claves.add(clave)
        codigos.add(limpio["codigo"].casefold())
        limpios.append((clave, limpio))
    if set(catalogo.valores.values_list("pk", flat=True)) - {int(c) for c in claves if not c.startswith("nuevo-")}:
        raise ValueError("No se pueden eliminar valores publicados; desactívalos.")
    return cabecera.cleaned_data, limpios


@login_required(login_url="acceso")
def catalogos_panel(request):
    _admin(request)
    q = request.GET.get("q", "").strip()[:80]
    estado = request.GET.get("estado", "")
    catalogos = CatalogoSistema.objects.annotate(total_valores=Count("valores")).order_by("nombre")
    if q:
        catalogos = catalogos.filter(Q(codigo__icontains=q) | Q(nombre__icontains=q))
    if estado in ("activo", "inactivo"):
        catalogos = catalogos.filter(activo=(estado == "activo"))
    return render(request, "catalogos/lista.html", {
        "catalogos": catalogos, "q": q, "estado": estado,
        "total": CatalogoSistema.objects.count(),
        "activos": ValorCatalogo.objects.filter(activo=True, catalogo__activo=True).count(),
        "inactivos": ValorCatalogo.objects.filter(activo=False).count(),
        "pendientes": BorradorCatalogo.objects.count(),
    })


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def crear_catalogo(request):
    _admin(request)
    form = CatalogoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            with transaction.atomic():
                # Un catálogo nuevo comienza sin publicar; la vista de detalle gestiona la publicación.
                catalogo = CatalogoSistema.objects.create(
                    codigo=d["codigo"], nombre=d["nombre"], descripcion=d["descripcion"],
                    activo=False, visible_formularios=False)
                borrador = BorradorCatalogo.objects.create(
                    catalogo=catalogo, actor=request.user, version_base=catalogo.version,
                    datos={"codigo": catalogo.codigo, "nombre": catalogo.nombre,
                           "descripcion": catalogo.descripcion, "activo": d["activo"],
                           "visible_formularios": d["visible_formularios"], "valores": []})
                CambioCatalogo.objects.create(catalogo=catalogo, actor=request.user, accion="CREACION",
                    detalle="Se creó un catálogo sin publicar.", despues=borrador.datos)
        except IntegrityError:
            form.add_error("codigo", "Este código ya está registrado.")
        else:
            messages.success(request, "Catálogo creado como borrador. Agrega valores y publícalo cuando esté listo.")
            return redirect("catalogo_detalle", pk=catalogo.pk)
    return render(request, "catalogos/nuevo.html", {"form": form})


@login_required(login_url="acceso")
@csrf_protect
@require_http_methods(["GET", "POST"])
def catalogo_detalle(request, pk):
    _admin(request)
    catalogo = get_object_or_404(CatalogoSistema, pk=pk)
    borrador = BorradorCatalogo.objects.filter(catalogo=catalogo, actor=request.user).first()
    foto = borrador.datos if borrador else _foto(catalogo)
    metadata_form = CatalogoForm(initial=foto, instancia=catalogo)
    valor_form = ValorForm(initial={"orden": len(foto["valores"]) + 1, "activo": True, "disponible_nuevas": True})
    publicacion_form = PublicacionForm()
    if request.method == "POST":
        accion = request.POST.get("accion", "")
        if accion in ("datos", "valor", "estado_valor", "orden"):
            if borrador and borrador.version_base != catalogo.version:
                messages.error(request, "El catálogo cambió después de crear tu borrador. Descarta el borrador y vuelve a revisar los datos.")
                return redirect("catalogo_detalle", pk=pk)
            borrador = borrador or _borrador(catalogo, request.user)
            foto = borrador.datos
            if accion == "datos":
                metadata_form = CatalogoForm(request.POST, instancia=catalogo, initial={"codigo": catalogo.codigo})
                if metadata_form.is_valid():
                    foto.update(metadata_form.cleaned_data)
                    _guardar(borrador, foto)
                    messages.success(request, "Datos guardados en borrador.")
                    return redirect("catalogo_detalle", pk=pk)
            elif accion == "valor":
                valor_form = ValorForm(request.POST)
                if valor_form.is_valid():
                    d = valor_form.cleaned_data
                    clave = request.POST.get("clave", "").strip()[:48]
                    existente = next((v for v in foto["valores"] if v["clave"] == clave), None) if clave else None
                    if clave and not existente:
                        valor_form.add_error(None, "Este valor no está en el borrador.")
                    elif existente and existente["codigo"] != d["codigo"]:
                        valor_form.add_error("codigo", "El código de un valor existente no puede cambiarse.")
                    elif any(v["codigo"].casefold() == d["codigo"].casefold() and v is not existente for v in foto["valores"]):
                        valor_form.add_error("codigo", "Ya existe un valor con ese código.")
                    else:
                        item = {"clave": existente["clave"] if existente else f"nuevo-{uuid.uuid4().hex}", **d}
                        if existente:
                            foto["valores"][foto["valores"].index(existente)] = item
                        else:
                            foto["valores"].append(item)
                        _guardar(borrador, foto)
                        messages.success(request, "Valor guardado en borrador.")
                        return redirect("catalogo_detalle", pk=pk)
            else:
                clave = request.POST.get("clave", "")[:48]
                item = next((v for v in foto["valores"] if v["clave"] == clave), None)
                if item is None:
                    messages.error(request, "El valor no se encontró en el borrador.")
                elif accion == "estado_valor":
                    item["activo"] = not item["activo"]
                    if not item["activo"]:
                        item["disponible_nuevas"] = False
                    _guardar(borrador, foto)
                    messages.success(request, "Estado actualizado en borrador; todavía no está publicado.")
                    return redirect("catalogo_detalle", pk=pk)
                else:
                    orden = sorted(foto["valores"], key=lambda v: (v["orden"], v["codigo"]))
                    indice = next(i for i, v in enumerate(orden) if v["clave"] == clave)
                    destino = indice + (-1 if request.POST.get("direccion") == "arriba" else 1)
                    if 0 <= destino < len(orden):
                        orden[indice], orden[destino] = orden[destino], orden[indice]
                        for n, v in enumerate(orden, start=1):
                            v["orden"] = n
                        foto["valores"] = orden
                        _guardar(borrador, foto)
                    return redirect("catalogo_detalle", pk=pk)
        elif accion == "descartar":
            if borrador:
                borrador.delete()
                messages.info(request, "Borrador descartado. Los valores publicados permanecen intactos.")
            return redirect("catalogo_detalle", pk=pk)
        elif accion == "publicar":
            publicacion_form = PublicacionForm(request.POST)
            if not borrador:
                publicacion_form.add_error(None, "No hay cambios pendientes para publicar.")
            elif publicacion_form.is_valid():
                try:
                    with transaction.atomic():
                        catalogo = CatalogoSistema.objects.select_for_update().get(pk=pk)
                        borrador = BorradorCatalogo.objects.select_for_update().get(pk=borrador.pk)
                        if borrador.version_base != catalogo.version:
                            raise ValueError("Otro administrador publicó cambios. Descarta el borrador y vuelve a revisar el catálogo.")
                        d, valores = _validar(borrador.datos, catalogo)
                        antes = _foto(catalogo)
                        catalogo.nombre = d["nombre"]
                        catalogo.descripcion = d["descripcion"]
                        catalogo.activo = d["activo"]
                        catalogo.visible_formularios = d["visible_formularios"]
                        catalogo.version += 1
                        catalogo.save(update_fields=["nombre", "descripcion", "activo", "visible_formularios", "version", "actualizado_en"])
                        for clave, limpio in valores:
                            if clave.startswith("nuevo-"):
                                ValorCatalogo.objects.create(catalogo=catalogo, **limpio)
                            else:
                                ValorCatalogo.objects.filter(pk=int(clave), catalogo=catalogo).update(**limpio, actualizado_en=timezone.now())
                        despues = _foto(catalogo)
                        CambioCatalogo.objects.create(catalogo=catalogo, actor=request.user, accion="PUBLICACION",
                            detalle=publicacion_form.cleaned_data["motivo"], antes=antes, despues=despues)
                        borrador.delete()
                except (ValueError, IntegrityError, BorradorCatalogo.DoesNotExist) as exc:
                    publicacion_form.add_error(None, str(exc) if isinstance(exc, ValueError) else "No se pudo publicar; revisa los datos y vuelve a intentarlo.")
                else:
                    messages.success(request, "Cambios publicados y registrados en auditoría.")
                    return redirect("catalogo_detalle", pk=pk)
        else:
            raise PermissionDenied("Acción no permitida.")
    borrador = BorradorCatalogo.objects.filter(catalogo=catalogo, actor=request.user).first()
    foto = borrador.datos if borrador else _foto(catalogo)
    filtro = request.GET.get("estado", "")
    buscar = request.GET.get("q", "").strip()[:80]
    valores = sorted(foto["valores"], key=lambda v: (v["orden"], v["codigo"]))
    if filtro in ("activo", "inactivo"):
        valores = [v for v in valores if v["activo"] == (filtro == "activo")]
    if buscar:
        valores = [v for v in valores if buscar.casefold() in (v["codigo"] + " " + v["nombre"]).casefold()]
    clave_editar = request.GET.get("editar", "")[:48]
    valor_editar = next((v for v in foto["valores"] if v["clave"] == clave_editar), None)
    if valor_editar and not (request.method == "POST" and request.POST.get("accion") == "valor"):
        valor_form = ValorForm(initial=valor_editar)
    return render(request, "catalogos/detalle.html", {
        "catalogo": catalogo, "foto": foto, "borrador": borrador, "valores": valores,
        "catalogos": CatalogoSistema.objects.annotate(total_valores=Count("valores")).order_by("nombre"),
        "metadata_form": metadata_form, "valor_form": valor_form, "publicacion_form": publicacion_form,
        "busqueda": buscar, "estado_filtro": filtro,
        "historial": CambioCatalogo.objects.filter(catalogo=catalogo).select_related("actor")[:10],
        "accion_actual": request.POST.get("accion", "") if request.method == "POST" else "",
        "valor_editar": valor_editar,
    })


@login_required(login_url="acceso")
@csrf_protect
@require_POST
def duplicar_catalogo(request, pk):
    _admin(request)
    with transaction.atomic():
        original = get_object_or_404(CatalogoSistema.objects.select_for_update(), pk=pk)
        for n in range(1, 100):
            codigo = f"{original.codigo[:26]}_C{n}"
            if not CatalogoSistema.objects.filter(codigo=codigo).exists():
                break
        else:
            messages.error(request, "No hay códigos disponibles para duplicar este catálogo.")
            return redirect("catalogo_detalle", pk=pk)
        nuevo = CatalogoSistema.objects.create(codigo=codigo, nombre=f"Copia de {original.nombre}"[:100],
                descripcion=original.descripcion, activo=False, visible_formularios=False)
        for v in original.valores.all():
            ValorCatalogo.objects.create(catalogo=nuevo, codigo=v.codigo, nombre=v.nombre,
                descripcion=v.descripcion, orden=v.orden, activo=False, disponible_nuevas=False,
                requiere_ubicacion=v.requiere_ubicacion, requiere_validacion=v.requiere_validacion)
        CambioCatalogo.objects.create(catalogo=nuevo, actor=request.user, accion="DUPLICACION",
            detalle=f"Copia del catálogo {original.codigo}; inicia inactiva.", despues=_foto(nuevo))
    messages.success(request, "Catálogo duplicado e inactivo. Revisa sus valores antes de activarlo.")
    return redirect("catalogo_detalle", pk=nuevo.pk)


@login_required(login_url="acceso")
@require_GET
def exportar_catalogo(request, pk):
    _admin(request)
    catalogo = get_object_or_404(CatalogoSistema, pk=pk)
    salida = HttpResponse(content_type="text/csv; charset=utf-8")
    salida["Content-Disposition"] = f'attachment; filename="catalogo_{catalogo.codigo}.csv"'
    salida.write("\ufeff")
    escritor = csv.writer(salida)
    escritor.writerow(["Código", "Nombre", "Descripción", "Orden", "Activo", "Disponible", "Requiere ubicación", "Requiere validación"])
    def celda(valor):
        valor = str(valor)
        return "'" + valor if valor.lstrip().startswith(("=", "+", "-", "@")) else valor

    for v in catalogo.valores.all().order_by("orden", "pk"):
        escritor.writerow([celda(v.codigo), celda(v.nombre), celda(v.descripcion), v.orden,
            "Sí" if v.activo else "No", "Sí" if v.disponible_nuevas else "No",
            "Sí" if v.requiere_ubicacion else "No", "Sí" if v.requiere_validacion else "No"])
    return salida
