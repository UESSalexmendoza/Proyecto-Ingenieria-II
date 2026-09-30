"""Crea opciones iniciales sin alterar catálogos ya administrados."""
from django.core.management.base import BaseCommand
from django.db import transaction
from BS.models import CatalogoSistema, ValorCatalogo


class Command(BaseCommand):
    help = "Crea los catálogos iniciales para el formulario de solicitudes."

    @transaction.atomic
    def handle(self, *args, **options):
        iniciales = [
            ("TIPOS_AYUDA", "Tipos de ayuda", "Clasificación de solicitudes de asistencia.", [
                ("MEDICAMENTOS", "Compra de medicamentos"), ("ALIMENTOS", "Compra de alimentos"),
                ("ACOMPANAMIENTO", "Acompañamiento"), ("TRANSPORTE", "Transporte"),
                ("APOYO_DOMESTICO", "Apoyo doméstico"), ("TRAMITE_BASICO", "Trámite básico"),
                ("ORIENTACION", "Orientación comunitaria"), ("OTRA", "Otra ayuda"),
            ]),
            ("PRIORIDADES", "Prioridades", "Prioridad declarada por el solicitante, sujeta a revisión.", [
                ("NORMAL", "Normal"), ("ALTA", "Alta"), ("URGENTE", "Urgente (no emergencias)"),
            ]),
        ]
        for codigo, nombre, descripcion, valores in iniciales:
            catalogo, creado = CatalogoSistema.objects.get_or_create(
                codigo=codigo, defaults={"nombre": nombre, "descripcion": descripcion, "activo": True, "visible_formularios": True})
            if creado:
                for orden, (clave, etiqueta) in enumerate(valores, 1):
                    ValorCatalogo.objects.create(catalogo=catalogo, codigo=clave, nombre=etiqueta,
                                                 orden=orden, activo=True, disponible_nuevas=True)
                self.stdout.write(self.style.SUCCESS(f"Creado: {catalogo.codigo} ({len(valores)} valores)."))
            else:
                self.stdout.write(f"Conservado sin cambios: {catalogo.codigo}.")
