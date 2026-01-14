from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Conductor, Vehiculo, Deuda, Pago, 
    Notificacion, MovimientoAudit, ConfiguracionCooperativa, ConfiguracionGlobal,
    UbicacionGeografica, Municipio, Parroquia
)

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

# 3. UBICACIÓN (NUEVO: Municipios y Parroquias para la cascada)
@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Parroquia)
class ParroquiaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'municipio')
    list_filter = ('municipio',)
    search_fields = ('nombre',)

@admin.register(UbicacionGeografica)
class UbicacionGeograficaAdmin(admin.ModelAdmin):
    list_display = ("estado", "municipio", "parroquia", "sector")
    list_filter = ("estado", "municipio")

# 4. CONDUCTORES
@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    # Mantenemos tus campos originales + estado
    list_display = ("nombres", "apellidos", "cedula_prefijo", "cedula_identidad", "email", "telefono_principal", "activo")
    search_fields = ("nombres", "apellidos", "cedula_identidad", "email")
    list_filter = ("sexo", "estado_civil", "estado")

# 5. VEHÍCULOS
@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ("placa", "marca", "modelo", "numero_casco", "condicion", "conductor")
    search_fields = ("placa", "serial_niv", "conductor__cedula_identidad", "numero_casco")
    list_filter = ("condicion", "marca")

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

# 7. AUDITORÍA Y SISTEMA
@admin.register(MovimientoAudit)
class MovimientoAuditAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "modulo", "accion")
    list_filter = ("modulo", "usuario")
    readonly_fields = ("fecha", "usuario", "modulo", "accion")

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "fecha", "leida")
    list_filter = ("leida", "fecha")
