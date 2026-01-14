"""
Comando para generar deudas mensuales.
Ejecutar con: python manage.py generar_deudas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from taxis.models import Conductor, Deuda, ConfiguracionCooperativa, Notificacion, MovimientoAudit
from datetime import date

class Command(BaseCommand):
    help = 'Genera las deudas mensuales de $5 USD para todos los afiliados activos.'

    def handle(self, *args, **options):
        hoy = date.today()
        mes = hoy.month
        anio = hoy.year

        self.stdout.write(self.style.NOTICE(f'Iniciando generación de deudas para {mes}/{anio}...'))

        # 1. Obtener configuración
        config = ConfiguracionCooperativa.objects.first()
        monto = config.monto_cuota_usd if config else 5.00

        # 2. Filtrar conductores SIN deuda este mes
        afiliados_totales = Conductor.objects.count()
        conductores_sin_deuda = Conductor.objects.exclude(deudas__mes=mes, deudas__anio=anio)
        
        deudas_para_crear = []
        
        for c in conductores_sin_deuda:
            deudas_para_crear.append(
                Deuda(conductor=c, mes=mes, anio=anio, monto_usd=monto)
            )
            
        creadas = len(deudas_para_crear)
        ya_existian = afiliados_totales - creadas

        # 3. Guardado Masivo (Bulk Create)
        if deudas_para_crear:
            Deuda.objects.bulk_create(deudas_para_crear)
            
            # Crear Notificación Global del Sistema
            Notificacion.objects.create(
                titulo="Deudas Mensuales Generadas",
                mensaje=f"Se han generado {creadas} nuevas deudas de ${monto} USD correspondientes al mes {mes}/{anio}.",
                leida=False
            )
            
            # Auditoría (Usuario None porque es sistema)
            MovimientoAudit.objects.create(
                usuario=None, 
                accion=f"Generación automática de {creadas} deudas (Cron)", 
                modulo="Finanzas"
            )

        self.stdout.write(self.style.SUCCESS(
            f'Proceso completado. Creadas: {creadas}, Ya existían: {ya_existian}.'
        ))
