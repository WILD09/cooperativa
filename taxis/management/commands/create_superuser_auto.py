"""
Comando personalizado de Django para crear superusuario automáticamente.
Se ejecuta durante el deploy en Render.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Crea un superusuario automáticamente si no existe'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Configuración del superusuario
        username = 'admin'
        email = 'admin@cooperativa.com'
        password = 'admin123'  # Cambiar después del primer login
        
        # Verificar si ya existe
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'El usuario "{username}" ya existe. No se creó.')
            )
        else:
            # Crear superusuario
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f'✅ Superusuario "{username}" creado exitosamente!')
            )
            self.stdout.write(
                self.style.WARNING('⚠️  IMPORTANTE: Cambia la contraseña después del primer login')
            )