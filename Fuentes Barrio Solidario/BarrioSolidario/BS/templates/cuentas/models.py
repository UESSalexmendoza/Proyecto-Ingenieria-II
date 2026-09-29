
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
    acepto_politicas_en = models.DateTimeField()
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.correo


class UsuarioRol(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="roles_barrio",
    )
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="asignaciones")
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "rol"], name="bs_usuario_rol_unico")
        ]

    def __str__(self):
        return f"{self.usuario_id}: {self.rol.codigo}"


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
