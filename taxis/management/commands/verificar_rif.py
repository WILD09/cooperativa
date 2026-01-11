from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from taxis.models import Conductor
# from notificaciones.models import Notificacion (Asumiendo que tienes esto)

class Command(BaseCommand):
    help = 'Verifica vencimiento de RIF y notifica'

    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        aviso_previo = hoy + timedelta(days=15)

        # 1. Buscar los que vencen en 15 días EXACTOS
        por_vencer = Conductor.objects.filter(fecha_vencimiento_rif=aviso_previo)
        for c in por_vencer:
            # Enviar Email
            print(f"Enviando correo aviso a {c.user.email}...")
            # Crear Notificación interna
            # Notificacion.objects.create(user=c.user, titulo="Tu RIF vence pronto", ...)

        # 2. Buscar los que vencen HOY
        vencidos_hoy = Conductor.objects.filter(fecha_vencimiento_rif=hoy)
        for c in vencidos_hoy:
            print(f"URGENTE: RIF vencido para {c.user.email}...")
            # Bloquear sistema o notificar urgencia
