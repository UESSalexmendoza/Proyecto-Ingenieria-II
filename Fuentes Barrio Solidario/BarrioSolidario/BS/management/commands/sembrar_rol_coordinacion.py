"""Habilita el rol que emplea el módulo de coordinación sin alterar roles existentes."""
from django.core.management.base import BaseCommand
from BS.models import Rol


class Command(BaseCommand):
    help = "Crea o habilita el rol COORDINADOR en el catálogo de roles."

    def handle(self, *args, **options):
        rol, creado = Rol.objects.get_or_create(codigo="COORDINADOR", defaults={
            "nombre": "Coordinación y atención",
            "descripcion": "Revisa solicitudes y postulaciones, asigna voluntarios y supervisa atenciones.",
            "activo": True,
        })
        if not creado and not rol.activo:
            rol.activo = True
            rol.save(update_fields=["activo"])
        self.stdout.write(self.style.SUCCESS(
            "Rol COORDINADOR creado." if creado else "Rol COORDINADOR disponible. Se conservaron sus datos."))
