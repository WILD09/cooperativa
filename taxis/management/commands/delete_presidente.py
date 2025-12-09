from django.core.management.base import BaseCommand
from taxis.models import CustomUser

class Command(BaseCommand):
    help = "Elimina todos los usuarios con rol 'presidente' (excepto superusuarios)."

    def handle(self, *args, **options):
        qs = CustomUser.objects.filter(role="presidente", is_superuser=False)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Eliminados {count} usuarios con rol 'presidente' (no superusuarios)."
        ))
