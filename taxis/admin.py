from django.contrib import admin
from datetime import date
from .models import Conductor, Taxi


if Conductor in admin.site._registry:
    admin.site.unregister(Conductor)


@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'apellido', 'telefono', 'cedula_identidad',
        'edad_calculada', 'sexo', 'ubicacion_str', 'patente_vigente'
    )
    search_fields = (
        'nombre', 'apellido', 'telefono', 'cedula_identidad',
        'ubicacion__ciudad', 'ubicacion__estado', 'ubicacion__municipio', 'ubicacion__sector'
    )
    list_filter = ('sexo', 'pago_patente_realizado')

    fieldsets = (
        ('Información Personal', {
            'fields': (
                'nombre', 'apellido', 'telefono', 'cedula_identidad',
                'sexo', 'fecha_nacimiento'
            )
        }),
        ('Ubicación geográfica', {
            'fields': ('ubicacion',)
        }),
        ('Patente', {
            'fields': ('pago_patente_realizado', 'fecha_pago_patente')
        }),
    )

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        # Ocultar pago_patente_realizado y fecha_pago_patente en creación
        if obj is None:
            fields = [f for f in fields if f not in ('pago_patente_realizado', 'fecha_pago_patente')]
        return fields

    def edad_calculada(self, obj):
        if obj.fecha_nacimiento:
            hoy = date.today()
            return hoy.year - obj.fecha_nacimiento.year - (
                (hoy.month, hoy.day) < (obj.fecha_nacimiento.month, obj.fecha_nacimiento.day)
            )
        return None
    edad_calculada.short_description = 'Edad'

    def ubicacion_str(self, obj):
        return str(obj.ubicacion) if obj.ubicacion else '-'
    ubicacion_str.short_description = 'Ubicación Geográfica'

    def patente_vigente(self, obj):
        return obj.patente_vigente
    patente_vigente.boolean = True
    patente_vigente.short_description = 'Patente Vigente'


if Taxi in admin.site._registry:
    admin.site.unregister(Taxi)

@admin.register(Taxi)
class TaxiAdmin(admin.ModelAdmin):
    list_display = ('placa', 'modelo', 'anio', 'conductor')
    search_fields = ('placa', 'modelo', 'nombre_vehiculo')
    list_filter = ('anio', 'modelo', 'conductor')
