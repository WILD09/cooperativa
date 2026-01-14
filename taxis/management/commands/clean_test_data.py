from django.core.management.base import BaseCommand
from taxis.models import Conductor, Vehiculo, CustomUser

class Command(BaseCommand):
    help = 'Borra todos los conductores y vehículos de prueba de la base de datos.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando limpieza de datos de prueba...'))
        
        vehiculos_count = Vehiculo.objects.all().count()
        Vehiculo.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Se eliminaron {vehiculos_count} vehículos.'))
        
        conductores_count = Conductor.objects.all().count()
        Conductor.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Se eliminaron {conductores_count} conductores.'))
        
        self.stdout.write(self.style.SUCCESS('Limpieza completada exitosamente.'))
