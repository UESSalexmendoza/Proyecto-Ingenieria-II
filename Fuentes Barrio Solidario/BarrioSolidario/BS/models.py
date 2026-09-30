
import hashlib
import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import models


class Rol(models.Model):
    codigo = models.CharField(max_length=32, unique=True)
    nombre = models.CharField(max_length=80)
    descripcion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    permisos = models.ManyToManyField(Permission, through="RolPermiso", blank=True)

    def __str__(self):
        return self.nombre


class CambioRol(models.Model):
    """Auditoría de configuración de roles, sin datos sensibles de los usuarios."""
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="cambios_configuracion")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name="cambios_roles_barrio")
    accion = models.CharField(max_length=24)
    antes = models.JSONField(default=dict, blank=True)
    despues = models.JSONField(default=dict, blank=True)
    motivo = models.CharField(max_length=500)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha", "-pk")
        verbose_name = "Cambio de rol"
        verbose_name_plural = "Cambios de roles"


class InstitucionAval(models.Model):
    """Instituciones publicadas en el portal por un administrador."""

    nombre = models.CharField(max_length=120)
    descripcion = models.CharField(max_length=240)
    url = models.URLField(max_length=300)
    imagen = models.ImageField(upload_to="instituciones/%Y/%m/")
    activa = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("orden", "nombre", "pk")
        verbose_name = "Institución que nos avala"
        verbose_name_plural = "Instituciones que nos avalan"

    def __str__(self):
        return self.nombre


class CasoContacto(models.Model):
    """Consulta pública recibida desde el formulario del portal."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_REVISION = "EN_REVISION", "En revisión"
        RESPONDIDO = "RESPONDIDO", "Respondido"
        CERRADO = "CERRADO", "Cerrado"

    nombre = models.CharField(max_length=120)
    email = models.EmailField(max_length=254)
    telefono = models.CharField(max_length=20, blank=True)
    institucion = models.CharField(max_length=120, blank=True)
    mensaje = models.TextField(max_length=3000)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    acuse_enviado_en = models.DateTimeField(null=True, blank=True)
    notificacion_estado_pendiente = models.BooleanField(default=False)
    estado_notificado_en = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="contactos_revisados_barrio",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    nota_revision = models.TextField(
        "Nota para el remitente", max_length=2000, blank=True,
        help_text="Se enviará por correo al remitente al guardar un cambio de estado o de nota.",
    )

    class Meta:
        ordering = ("-creado_en",)
        verbose_name = "Caso de contacto"
        verbose_name_plural = "Casos de contacto"

    def __str__(self):
        return f"Caso #{self.pk}: {self.nombre}"


class ActuacionContacto(models.Model):
    class Tipo(models.TextChoices):
        CREACION = "CREACION", "Creación"
        REVISION = "REVISION", "Revisión"
        REINTENTO = "REINTENTO", "Reintento de notificación"

    class Correo(models.TextChoices):
        NO_APLICA = "NO_APLICA", "No aplica"
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADO = "ENVIADO", "Enviado"
        FALLIDO = "FALLIDO", "Fallido"

    caso = models.ForeignKey(CasoContacto, on_delete=models.CASCADE, related_name="actuaciones")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="actuaciones_contacto")
    fecha = models.DateTimeField(auto_now_add=True)
    estado_anterior = models.CharField(max_length=15, blank=True)
    estado_nuevo = models.CharField(max_length=15)
    nota = models.TextField(max_length=2000, blank=True)
    resultado_correo = models.CharField(max_length=10, choices=Correo.choices,
                                       default=Correo.NO_APLICA)

    class Meta:
        ordering = ("fecha", "pk")
        verbose_name = "Actuación de contacto"
        verbose_name_plural = "Actuaciones de contacto"

    def __str__(self):
        return f"{self.get_tipo_display()} del caso #{self.caso_id}"


class RolPermiso(models.Model):
    """Enlaza roles de Barrio Solidario con permisos de Django."""

    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="rol_permisos")
    permiso = models.ForeignKey(
        Permission, on_delete=models.PROTECT, related_name="roles_barrio"
    )
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rol", "permiso"], name="bs_rol_permiso_unico")
        ]


class PerfilUsuario(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACTIVA = "ACTIVA", "Activa"
        SUSPENDIDA = "SUSPENDIDA", "Suspendida"
        INACTIVA = "INACTIVA", "Inactiva"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="perfil_barrio",
    )
    correo = models.EmailField(max_length=254, unique=True)
    telefono = models.CharField(max_length=25)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ACTIVA)
    acepto_politicas_en = models.DateTimeField(null=True, blank=True)
    acepto_datos_personales_en = models.DateTimeField(null=True, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sector_aproximado = models.CharField(max_length=80, blank=True)
    contacto_alternativo = models.CharField(max_length=15, blank=True)
    canal_preferido = models.CharField(max_length=20, default="PLATAFORMA")
    recibir_notificaciones = models.BooleanField(default=True)
    alto_contraste = models.BooleanField(default=False)
    informacion_adicional = models.CharField(max_length=500, blank=True)
    idioma = models.CharField(max_length=8, default="es")
    zona_horaria = models.CharField(max_length=40, default="America/Guayaquil")
    disponibilidad = models.CharField(max_length=120, blank=True)
    permitir_ubicacion_aproximada = models.BooleanField(default=False)
    compartir_ubicacion_atencion = models.BooleanField(default=False)
    recibir_recordatorios = models.BooleanField(default=True)
    recibir_mensajes = models.BooleanField(default=True)
    recibir_resumen_semanal = models.BooleanField(default=False)
    distancia_maxima_km = models.PositiveSmallIntegerField(default=10)
    notificaciones_desde = models.TimeField(default="07:00")
    notificaciones_hasta = models.TimeField(default="21:00")
    modo_silencioso = models.BooleanField(default=True)
    tamano_texto = models.CharField(max_length=12, default="mediano")
    subrayar_enlaces = models.BooleanField(default=True)
    reducir_animaciones = models.BooleanField(default=False)
    lectura_simplificada = models.BooleanField(default=False)
    lectura_idioma = models.CharField(max_length=8, default="es")
    ocultar_datos_personales = models.BooleanField(default=True)
    permitir_contacto_coordinacion = models.BooleanField(default=True)
    permitir_contacto_usuarios = models.BooleanField(default=False)
    ocultar_informacion_adicional = models.BooleanField(default=True)
    latitud_ubicacion = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud_ubicacion = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ubicacion_actualizada_en = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="avatares/%Y/%m/", blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.correo


class UsuarioRol(models.Model):
    class Aprobacion(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de aprobación"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="roles_barrio",
    )
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="asignaciones")
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    estado_aprobacion = models.CharField(max_length=12, choices=Aprobacion.choices, default=Aprobacion.PENDIENTE)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    observacion_revision = models.CharField(max_length=300, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="roles_revisados_barrio",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "rol"], name="bs_usuario_rol_unico")
        ]

    def __str__(self):
        return f"{self.usuario_id}: {self.rol.codigo}"

    @property
    def puede_operar(self):
        return self.activo and self.rol.activo and self.estado_aprobacion == self.Aprobacion.APROBADO


class ActuacionUsuario(models.Model):
    """Historial de administración; nunca almacena contraseñas ni tokens."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="actuaciones_administrativas")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="acciones_usuarios_barrio")
    accion = models.CharField(max_length=50)
    detalle = models.CharField(max_length=500, blank=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-fecha", "-pk")
        verbose_name = "Actuación sobre usuario"
        verbose_name_plural = "Actuaciones sobre usuarios"


class SolicitudCorreccionPerfil(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        RESUELTA = "RESUELTA", "Resuelta"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="correcciones_perfil")
    descripcion = models.CharField(max_length=500)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)


class EventoAcceso(models.Model):
    """Auditoría básica sin contraseñas ni tokens."""

    class Tipo(models.TextChoices):
        REGISTRO = "REGISTRO", "Registro"
        ACCESO = "ACCESO", "Acceso"
        ACCESO_FALLIDO = "ACCESO_FALLIDO", "Acceso fallido"
        SALIDA = "SALIDA", "Cierre de sesión"
        RECUPERACION = "RECUPERACION", "Recuperación de contraseña"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="eventos_acceso_barrio",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    exitoso = models.BooleanField(default=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_hora"]


class RecuperacionClave(models.Model):
    """Trazabilidad de solicitudes; el token seguro lo gestiona Django."""

    class Estado(models.TextChoices):
        SOLICITADA = "SOLICITADA", "Solicitada"
        COMPLETADA = "COMPLETADA", "Completada"
        VENCIDA = "VENCIDA", "Vencida"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="recuperaciones_barrio",
    )
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    fecha_expiracion = models.DateTimeField()
    fecha_uso = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.SOLICITADA
    )


class SolicitudAccesoSocial(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="solicitudes_sociales_barrio",
    )
    correo = models.EmailField(max_length=150)
    proveedor = models.CharField(max_length=32)
    uid_proveedor = models.CharField(max_length=255)
    nombres = models.CharField(max_length=60, blank=True)
    apellidos = models.CharField(max_length=60, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    rol_codigo = models.CharField(max_length=32, blank=True)
    acepto_politicas_en = models.DateTimeField(null=True, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    creado_en = models.DateTimeField(default=timezone.now)
    vence_en = models.DateTimeField()
    utilizado_en = models.DateTimeField(null=True, blank=True)

    @classmethod
    def crear(cls, *, email, provider, uid, usuario=None, datos=None):
        datos = datos or {}
        token = secrets.token_urlsafe(32)
        pending = cls.objects.create(
            usuario=usuario, correo=email, proveedor=provider, uid_proveedor=uid,
            nombres=datos.get("nombres", ""), apellidos=datos.get("apellidos", ""),
            telefono=datos.get("telefono", ""), rol_codigo=datos.get("tipoUsuario", ""),
            acepto_politicas_en=timezone.now() if datos.get("aceptaPoliticas") else None,
            token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
            vence_en=timezone.now() + timedelta(minutes=10),
        )
        return pending, token

    @property
    def vigente(self):
        return self.utilizado_en is None and self.vence_en > timezone.now()


class CatalogoSistema(models.Model):
    """Definición administrable de un conjunto de valores del sistema."""
    codigo = models.CharField(max_length=32, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300)
    activo = models.BooleanField(default=False)
    visible_formularios = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("nombre", "pk")
        verbose_name = "Catálogo del sistema"
        verbose_name_plural = "Catálogos del sistema"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class ValorCatalogo(models.Model):
    catalogo = models.ForeignKey(CatalogoSistema, on_delete=models.PROTECT, related_name="valores")
    codigo = models.CharField(max_length=32)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True)
    orden = models.PositiveSmallIntegerField(default=1)
    activo = models.BooleanField(default=True)
    disponible_nuevas = models.BooleanField(default=True)
    requiere_ubicacion = models.BooleanField(default=False)
    requiere_validacion = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("orden", "pk")
        constraints = [models.UniqueConstraint(fields=("catalogo", "codigo"), name="bs_catalogo_codigo_unico")]
        verbose_name = "Valor de catálogo"
        verbose_name_plural = "Valores de catálogo"

    def __str__(self):
        return f"{self.catalogo.codigo}: {self.nombre}"


class BorradorCatalogo(models.Model):
    catalogo = models.ForeignKey(CatalogoSistema, on_delete=models.CASCADE, related_name="borradores")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="borradores_catalogo")
    datos = models.JSONField(default=dict)
    version_base = models.PositiveIntegerField()
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("catalogo", "actor"), name="bs_borrador_catalogo_actor_unico")]


class CambioCatalogo(models.Model):
    catalogo = models.ForeignKey(CatalogoSistema, on_delete=models.PROTECT, related_name="historial_publicacion")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    accion = models.CharField(max_length=24)
    detalle = models.CharField(max_length=500)
    antes = models.JSONField(default=dict)
    despues = models.JSONField(default=dict)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha", "-pk")
        verbose_name = "Cambio de catálogo"
        verbose_name_plural = "Cambios de catálogos"


class SolicitudAsistencia(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        EN_REVISION = "EN_REVISION", "En revisión"
        APROBADA = "APROBADA", "Aprobada"
        OBSERVADA = "OBSERVADA", "Observada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        CANCELADA = "CANCELADA", "Cancelada"
        COMPLETADA = "COMPLETADA", "Completada"

    class Destinatario(models.TextChoices):
        PROPIA = "PROPIA", "Para mí"
        ADULTO_CUIDADO = "ADULTO_CUIDADO", "Para un adulto mayor a mi cuidado"

    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="solicitudes_asistencia_barrio")
    tipo_ayuda = models.ForeignKey(ValorCatalogo, on_delete=models.PROTECT,
                                   related_name="solicitudes_tipo_ayuda")
    prioridad = models.ForeignKey(ValorCatalogo, on_delete=models.PROTECT,
                                  related_name="solicitudes_prioridad")
    destinatario = models.CharField(max_length=18, choices=Destinatario.choices)
    descripcion = models.TextField(max_length=500)
    fecha_requerida = models.DateField()
    sector_referencia = models.CharField(max_length=160)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    consentimiento_ubicacion_en = models.DateTimeField(null=True, blank=True)
    persona_contacto = models.CharField(max_length=120)
    telefono_contacto = models.CharField(max_length=15)
    correo_contacto = models.EmailField(max_length=254, null=True, blank=True)
    disponibilidad = models.CharField(max_length=25)
    observaciones = models.TextField(max_length=500, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR, db_index=True)
    acepto_tratamiento_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    enviada_en = models.DateTimeField(null=True, blank=True)
    confirmacion_enviada_en = models.DateTimeField(null=True, blank=True)
    confirmacion_pendiente = models.BooleanField(default=False)
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="solicitudes_revisadas_barrio")
    revisado_en = models.DateTimeField(null=True, blank=True)
    nota_revision = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("-creado_en", "-pk")
        verbose_name = "Solicitud de asistencia"
        verbose_name_plural = "Solicitudes de asistencia"

    @property
    def codigo(self):
        return f"SOL-{self.creado_en.year}-{self.pk:04d}" if self.pk and self.creado_en else "Pendiente"

    @property
    def disponibilidad_legible(self):
        nombres = {"MANANA": "Mañana", "TARDE": "Tarde", "NOCHE": "Noche"}
        return ", ".join(nombres.get(item, item) for item in self.disponibilidad.split(",") if item)

    @property
    def codigo_acceso(self):
        """Identificador público opaco; no revela el consecutivo interno."""
        import hashlib
        import hmac
        if not self.pk:
            return ""
        from django.conf import settings
        clave = settings.SECRET_KEY.encode("utf-8")
        contenido = f"barrio-solidario:solicitud:{self.pk}".encode("utf-8")
        return hmac.new(clave, contenido, hashlib.sha256).hexdigest()[:32]


class ActuacionSolicitud(models.Model):
    solicitud = models.ForeignKey(SolicitudAsistencia, on_delete=models.CASCADE,
                                 related_name="actuaciones")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, related_name="actuaciones_solicitud_barrio")
    accion = models.CharField(max_length=32)
    descripcion = models.CharField(max_length=350)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha", "-pk")
        verbose_name = "Actuación de solicitud"
        verbose_name_plural = "Actuaciones de solicitudes"


class PostulacionVoluntario(models.Model):
    """Oferta del voluntario; su aceptación no asigna automáticamente la solicitud."""
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        ENVIADA = "ENVIADA", "Pendiente de revisión"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        RETIRADA = "RETIRADA", "Retirada"

    solicitud = models.ForeignKey(SolicitudAsistencia, on_delete=models.PROTECT, related_name="postulaciones")
    voluntario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name="postulaciones_voluntariado")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR, db_index=True)
    fecha_disponible = models.DateField(null=True, blank=True)
    hora_desde = models.TimeField(null=True, blank=True)
    hora_hasta = models.TimeField(null=True, blank=True)
    tiene_transporte = models.BooleanField(default=False)
    mensaje = models.CharField(max_length=400, blank=True)
    confirmado_en = models.DateTimeField(null=True, blank=True)
    acepto_revision_en = models.DateTimeField(null=True, blank=True)
    enviada_en = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="postulaciones_revisadas")
    revisado_en = models.DateTimeField(null=True, blank=True)
    nota_revision = models.CharField(max_length=300, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["solicitud", "voluntario"], name="bs_postulacion_unica")]
        ordering = ("-actualizado_en",)
        verbose_name = "Postulación de voluntario"
        verbose_name_plural = "Postulaciones de voluntarios"
