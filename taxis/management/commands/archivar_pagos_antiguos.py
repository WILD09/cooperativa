from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models           # 👈 IMPORTANTE: para models.Count

from taxis.models import PagoMensual


class Command(BaseCommand):
    help = 'Archiva pagos mensuales con más de 5 años de antigüedad'

    def add_arguments(self, parser):
        parser.add_argument(
            '--años',
            type=int,
            default=5,
            help='Cantidad de años de antigüedad para archivar (por defecto: 5)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula el archivado sin guardar cambios'
        )

    def handle(self, *args, **options):
        años_antiguedad = options['años']
        dry_run = options['dry_run']

        año_limite = date.today().year - años_antiguedad

        self.stdout.write(
            self.style.WARNING(
                f'\n📦 Buscando pagos anteriores a {año_limite}...\n'
            )
        )

        # Buscar pagos sin archivar anteriores al año límite
        pagos_archivar = PagoMensual.objects.filter(
            archivado=False,
            anio__lt=año_limite
        )

        total = pagos_archivar.count()

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ No hay pagos para archivar.')
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'⚠️  Se encontraron {total} pagos para archivar.\n'
            )
        )

        # Mostrar desglose por año
        resumen = pagos_archivar.values('anio').annotate(
            cantidad=models.Count('id')   # 👈 aquí ya existe models
        ).order_by('anio')

        self.stdout.write('📊 Desglose por año:')
        for item in resumen:
            self.stdout.write(f"   • Año {item['anio']}: {item['cantidad']} pagos")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n🔍 Modo simulación (--dry-run). No se guardaron cambios.\n'
                )
            )
            return

        # Confirmar acción
        confirmacion = input(
            '\n¿Desea continuar con el archivado? (escriba "SI" para confirmar): '
        )

        if confirmacion.strip().upper() != 'SI':
            self.stdout.write(
                self.style.ERROR('❌ Operación cancelada.\n')
            )
            return

        # Archivar pagos
        archivados = pagos_archivar.update(
            archivado=True,
            fecha_archivado=timezone.now()
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Se archivaron exitosamente {archivados} pagos.\n'
            )
        )

        # Estadísticas finales
        total_activos = PagoMensual.objects.filter(archivado=False).count()
        total_archivados = PagoMensual.objects.filter(archivado=True).count()

        self.stdout.write('📈 Estadísticas actuales:')
        self.stdout.write(f'   • Pagos activos: {total_activos}')
        self.stdout.write(f'   • Pagos archivados: {total_archivados}')
        self.stdout.write(f'   • Total en base de datos: {total_activos + total_archivados}\n')
