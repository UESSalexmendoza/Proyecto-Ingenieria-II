from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .forms_contacto import validar_texto_plano
from .services_contacto import guardar_revision

from .models import (
    EventoAcceso,
    PerfilUsuario,
    RecuperacionClave,
    Rol,
    RolPermiso,
    UsuarioRol,
    SolicitudCorreccionPerfil,
    CasoContacto,
    ActuacionContacto,
    PostulacionVoluntario,
)


class RevisionPostulacionAdminForm(forms.ModelForm):
    class Meta:
        model = PostulacionVoluntario
        fields = "__all__"

    def clean_estado(self):
        nuevo = self.cleaned_data["estado"]
        if self.instance.pk and nuevo != self.instance.estado:
            if self.instance.estado != PostulacionVoluntario.Estado.ENVIADA or nuevo not in (
                    PostulacionVoluntario.Estado.APROBADA, PostulacionVoluntario.Estado.RECHAZADA):
                raise ValidationError("Solo se puede aprobar o rechazar una postulación enviada.")
        return nuevo


@admin.register(PostulacionVoluntario)
class PostulacionVoluntarioAdmin(admin.ModelAdmin):
    form = RevisionPostulacionAdminForm
    list_display = ("solicitud", "voluntario", "estado", "fecha_disponible", "enviada_en", "revisado_en")
    list_filter = ("estado", "enviada_en")
    search_fields = ("voluntario__email", "=solicitud__id")
    readonly_fields = ("solicitud", "voluntario", "fecha_disponible", "hora_desde", "hora_hasta",
        "tiene_transporte", "mensaje", "confirmado_en", "acepto_revision_en", "enviada_en",
        "creado_en", "actualizado_en", "revisado_por", "revisado_en")
    fields = readonly_fields + ("estado", "nota_revision")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        campos = super().get_readonly_fields(request, obj)
        if obj and obj.estado != PostulacionVoluntario.Estado.ENVIADA:
            return (*campos, "estado")
        return campos

    def save_model(self, request, obj, form, change):
        if "estado" in form.changed_data:
            obj.revisado_por = request.user
            obj.revisado_en = timezone.now()
        super().save_model(request, obj, form, change)
        if "estado" in form.changed_data:
            from .views_voluntariado import notificar_resultado_postulacion
            transaction.on_commit(lambda: notificar_resultado_postulacion(obj.pk, request))


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "correo", "telefono", "estado", "acepto_datos_personales_en")
    search_fields = ("correo", "usuario__username")
    list_filter = ("estado",)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(UsuarioRol)
class UsuarioRolAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rol", "estado_aprobacion", "fecha_revision", "activo", "fecha_asignacion")
    list_filter = ("rol", "estado_aprobacion", "activo")
    search_fields = ("usuario__username", "usuario__email")

    def save_model(self, request, obj, form, change):
        if "estado_aprobacion" in form.changed_data:
            obj.fecha_revision = timezone.now() if obj.estado_aprobacion != obj.Aprobacion.PENDIENTE else None
            obj.revisado_por = request.user if obj.fecha_revision else None
        super().save_model(request, obj, form, change)


admin.site.register(RolPermiso)
admin.site.register(RecuperacionClave)
admin.site.register(EventoAcceso)


@admin.register(SolicitudCorreccionPerfil)
class SolicitudCorreccionPerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "estado", "creada_en", "resuelta_en")
    list_filter = ("estado",)
    search_fields = ("usuario__email", "descripcion")

    def save_model(self, request, obj, form, change):
        if "estado" in form.changed_data:
            obj.resuelta_en = timezone.now() if obj.estado == obj.Estado.RESUELTA else None
        super().save_model(request, obj, form, change)


class AdminCasoContactoForm(forms.ModelForm):
    class Meta:
        model = CasoContacto
        fields = "__all__"

    def clean_nota_revision(self):
        return validar_texto_plano(self.cleaned_data["nota_revision"])


class ActuacionContactoInline(admin.TabularInline):
    model = ActuacionContacto
    extra = 0
    can_delete = False
    readonly_fields = ("fecha", "tipo", "actor", "estado_anterior", "estado_nuevo", "nota", "resultado_correo")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CasoContacto)
class CasoContactoAdmin(admin.ModelAdmin):
    form = AdminCasoContactoForm
    inlines = (ActuacionContactoInline,)
    list_display = ("id", "nombre", "email", "estado", "creado_en", "acuse_enviado_en", "notificacion_estado_pendiente")
    list_filter = ("estado", "notificacion_estado_pendiente", "creado_en")
    search_fields = ("nombre", "email", "institucion", "mensaje")
    readonly_fields = ("nombre", "email", "telefono", "institucion", "mensaje", "creado_en", "acuse_enviado_en", "revisado_por", "revisado_en", "notificacion_estado_pendiente", "estado_notificado_en")
    fields = ("nombre", "email", "telefono", "institucion", "mensaje", "creado_en", "acuse_enviado_en", "estado", "nota_revision", "revisado_por", "revisado_en", "notificacion_estado_pendiente", "estado_notificado_en")

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        guardado, notificado = guardar_revision(
            obj.pk, actor=request.user, nuevo_estado=form.cleaned_data["estado"],
            nota=form.cleaned_data["nota_revision"], request=request,
        )
        if notificado is False:
            self.message_user(request, "El estado se guardó, pero no se pudo enviar el correo. La notificación está pendiente; guarda otra vez para reintentar.", level="warning")
        elif notificado is True:
            self.message_user(request, "Se envió al remitente la actualización del estado.", level="success")
