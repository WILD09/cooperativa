from django.core.management.base import BaseCommand
from taxis.models import Conductor, Taxi, CustomUser

class Command(BaseCommand):
    help = 'Borra todos los conductores y taxis de prueba de la base de datos.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando limpieza de datos de prueba...'))
        
        taxis_count = Taxi.objects.all().count()
        Taxi.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Se eliminaron {taxis_count} taxis.'))
        
        conductores_count = Conductor.objects.all().count()
        Conductor.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Se eliminaron {conductores_count} conductores.'))
        
        # Opcional: Podríamos querer borrar usuarios asociados que no sean admin/presidente
        # Pero por ahora solo conductores y taxis como se pidió.
        
        self.stdout.write(self.style.SUCCESS('Limpieza completada exitosamente.'))
