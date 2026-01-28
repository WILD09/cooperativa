# Archivo: taxis/management/commands/test_dates.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from taxis.models import Conductor, Vehiculo

class Command(BaseCommand):
    help = "Adelanta o retrasa fechas de vencimiento para testing de alertas"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=30,
            help='Cantidad de días a adelantar (negativo = retrasar). Default: 30'
        )
        
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['conductor', 'vehiculo', 'ambos'],
            default='ambos',
            help='Qué tipo de documentos modificar. Default: ambos'
        )
        
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Restaura todas las fechas a 30 días en el futuro (cancela cambios)'
        )
        
        parser.add_argument(
            '--estado',
            type=str,
            choices=['activo', 'inactivo', 'todos'],
            default='activo',
            help='Solo conductores con estado específico'
        )

    def handle(self, *args, **options):
        dias = options['dias']
        tipo = options['tipo']
        reset = options['reset']
        estado = options['estado']
        
        hoy = timezone.now().date()
        
        # ====================================================================
        # OPCIÓN: RESET (Restaurar fechas)
        # ====================================================================
        if reset:
            self.stdout.write(
                self.style.WARNING('⚠️  RESTAURANDO TODAS LAS FECHAS A 30 DÍAS EN FUTURO...')
            )
            fecha_futura = hoy + timedelta(days=30)
            
            # Conductores
            if tipo in ['conductor', 'ambos']:
                updated_c = Conductor.objects.all().update(
                    cedula_vencimiento=fecha_futura,
                    rif_vencimiento=fecha_futura
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✅ {updated_c} conductores restaurados')
                )
            
            # Vehículos
            if tipo in ['vehiculo', 'ambos']:
                updated_v = Vehiculo.objects.all().update(
                    patente_vencimiento=fecha_futura,
                    licencia_vencimiento=fecha_futura,
                    rcv_vencimiento=fecha_futura,
                    medico_vencimiento=fecha_futura
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✅ {updated_v} vehículos restaurados')
                )
            
            self.stdout.write(self.style.SUCCESS('🎉 Restauración completada'))
            return
        
        # ====================================================================
        # ADELANTAR O RETRASAR FECHAS
        # ====================================================================
        
        # Calcular nueva fecha
        if dias > 0:
            nueva_fecha = hoy - timedelta(days=dias)  # Pasado = vencido
            accion = f"adelantado {dias} días al pasado (VENCIDO)"
            estilo = self.style.ERROR
        else:
            nueva_fecha = hoy + timedelta(days=abs(dias))  # Futuro = no vencido
            accion = f"retrasado {abs(dias)} días al futuro (VIGENTE)"
            estilo = self.style.SUCCESS
        
        self.stdout.write(
            estilo(f'📅 Modificando fechas: {accion}')
        )
        self.stdout.write(f'   Hoy: {hoy}')
        self.stdout.write(f'   Nueva fecha: {nueva_fecha}\n')
        
        # ====================================================================
        # CONDUCTORES
        # ====================================================================
        if tipo in ['conductor', 'ambos']:
            self.stdout.write(self.style.HTTP_INFO('👤 CONDUCTORES:'))
            
            if estado == 'todos':
                qs = Conductor.objects.all()
                estado_texto = "todos"
            else:
                qs = Conductor.objects.filter(estado=estado)
                estado_texto = f"estado '{estado}'"
            
            updated_c = qs.update(
                cedula_vencimiento=nueva_fecha,
                rif_vencimiento=nueva_fecha
            )
            
            self.stdout.write(f'   ✅ {updated_c} conductores ({estado_texto})')
            self.stdout.write(f'   📄 Documentos: Cédula y RIF\n')
        
        # ====================================================================
        # VEHÍCULOS
        # ====================================================================
        if tipo in ['vehiculo', 'ambos']:
            self.stdout.write(self.style.HTTP_INFO('🚗 VEHÍCULOS:'))
            
            updated_v = Vehiculo.objects.all().update(
                patente_vencimiento=nueva_fecha,
                licencia_vencimiento=nueva_fecha,
                rcv_vencimiento=nueva_fecha,
                medico_vencimiento=nueva_fecha
            )
            
            self.stdout.write(f'   ✅ {updated_v} vehículos')
            self.stdout.write(f'   📄 Documentos: Patente, Licencia, RCV, Médico\n')
        
        # ====================================================================
        # RESUMEN
        # ====================================================================
        self.stdout.write(self.style.SUCCESS('🎉 Modificación completada'))
        self.stdout.write(
            f'\n💡 Recarga el panel: http://127.0.0.1:8000/taxis/panel/'
        )
        self.stdout.write(
            self.style.WARNING(
                '\n⚠️  NOTA: Para revertir cambios, usa: python manage.py test_dates --reset'
            )
        )
#comando para ejecutar: python manage.py test_dates --dias 15
