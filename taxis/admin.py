from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Conductor, Vehiculo, Deuda, Pago, 
    MovimientoAudit, ConfiguracionCooperativa, ConfiguracionGlobal,
    UbicacionGeografica, ConfiguracionFinanzas, PagoMensual
)
# ✅ BORRADO: from .models import Notificacion, NotificacionLectura, Municipio, Parroquia


# 1. USUARIOS (Vital para gestionar Presidentes vs Asociados)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Información Extra', {'fields': ('role', 'phone_number', 'avatar', 'is_email_verified')}),
    )


admin.site.register(CustomUser, CustomUserAdmin)


# 2. CONFIGURACIÓN (Lo nuevo + Lo viejo)
@admin.register(ConfiguracionGlobal)
class ConfiguracionGlobalAdmin(admin.ModelAdmin):
    list_display = ('tasa_bcv', 'fecha_actualizacion')


@admin.register(ConfiguracionCooperativa)
class ConfiguracionCooperativaAdmin(admin.ModelAdmin):
    # Ya no usamos tasa_bcv_actual aquí, pero mostramos la fecha
    list_display = ("monto_cuota_usd", "ultima_actualizacion")


@admin.register(ConfiguracionFinanzas)
class ConfiguracionFinanzasAdmin(admin.ModelAdmin):
    list_display = ('monto_cuota_usd', 'dia_vencimiento', 'descripcion', 'actualizado_en')


# 3. UBICACIÓN
@admin.register(UbicacionGeografica)
class UbicacionGeograficaAdmin(admin.ModelAdmin):
    list_display = ("estado", "municipio", "parroquia", "sector")
    list_filter = ("estado", "municipio")


# 4. CONDUCTORES (✅ CORREGIDO - USA 'estado' NO 'activo')
@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    """Admin para gestión de conductores con filtros mejorados"""
    
    # ✅ MEJORADO: Columnas optimizadas
    list_display = (
        "get_nombre_completo",
        "get_cedula_completa", 
        "email",
        "telefono_principal",
        "estado",           # ✅ Campo correcto del modelo
        "tiene_vehiculo"
    )
    
    # ✅ CORREGIDO: Usa 'estado' que existe en el modelo
    list_filter = (
        "estado",           # Opciones: activo/inactivo
        "ubicacion",        
        "sexo",             
        "estadocivil"
    )
    
    search_fields = (
        "nombres", 
        "apellidos", 
        "cedula_identidad", 
        "email",
        "telefono_principal"
    )
    
    ordering = ('apellidos', 'nombres')
    
    # ✅ NUEVO: Método para nombre completo
    def get_nombre_completo(self, obj):
        return f"{obj.nombres} {obj.apellidos}"
    get_nombre_completo.short_description = 'Nombre Completo'
    get_nombre_completo.admin_order_field = 'apellidos'
    
    # ✅ NUEVO: Método para cédula completa
    def get_cedula_completa(self, obj):
        return f"{obj.cedula_prefijo}-{obj.cedula_identidad}"
    get_cedula_completa.short_description = 'Cédula'
    get_cedula_completa.admin_order_field = 'cedula_identidad'
    
    # ✅ NUEVO: Método para mostrar si tiene vehículo
    def tiene_vehiculo(self, obj):
        count = obj.vehiculos.count()
        if count > 0:
            return f"✅ {count}"
        return "❌ No"
    tiene_vehiculo.short_description = 'Vehículos'
    
    # ✅ NUEVO: Optimizar consultas (reduce queries a la DB)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'ubicacion').prefetch_related('vehiculos')


# 5. VEHÍCULOS (✅ MEJORADO CON FILTROS)
@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    """Admin para gestión de vehículos con filtros mejorados"""
    
    list_display = (
        "numero_casco",
        "placa", 
        "get_conductor_nombre",
        "marca", 
        "modelo",
        "condicion"         # Operativo/Inoperativo
    )
    
    list_filter = (
        "condicion",        # Operativo/Inoperativo
        "marca",
        "combustible_tipo"
    )
    
    search_fields = (
        "placa", 
        "serial_niv", 
        "conductor__cedula_identidad",
        "conductor__nombres",
        "conductor__apellidos",
        "numero_casco"
    )
    
    ordering = ('numero_casco',)
    
    # ✅ Método para mostrar nombre del conductor
    def get_conductor_nombre(self, obj):
        return f"{obj.conductor.nombres} {obj.conductor.apellidos}"
    get_conductor_nombre.short_description = 'Conductor'
    get_conductor_nombre.admin_order_field = 'conductor__apellidos'
    
    # ✅ Optimizar consultas
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('conductor')


# 6. FINANZAS (CORREGIDO: monto_bs en lugar de monto_usd)
@admin.register(Deuda)
class DeudaAdmin(admin.ModelAdmin):
    list_display = ("conductor", "mes", "anio", "monto_bs", "pagada")
    list_filter = ("mes", "anio", "pagada")
    search_fields = ("conductor__nombres", "conductor__cedula_identidad")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("deuda", "monto_bs", "tasa_bcv", "fecha_pago")
    list_filter = ("fecha_pago",)


@admin.register(PagoMensual)
class PagoMensualAdmin(admin.ModelAdmin):
    list_display = ('conductor', 'mes', 'anio', 'monto_usd', 'fecha_pago', 'registrado_por')
    list_filter = ('anio', 'mes', 'fecha_pago')
    search_fields = ('conductor__nombres', 'conductor__apellidos', 'conductor__cedula_identidad')
    date_hierarchy = 'fecha_pago'


# 7. AUDITORÍA Y SISTEMA
@admin.register(MovimientoAudit)
class MovimientoAuditAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "modulo", "accion")
    list_filter = ("modulo", "usuario")
    readonly_fields = ("fecha", "usuario", "modulo", "accion")