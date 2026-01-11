"""
admin.py
Configuración del panel de administración para los modelos:
- Conductor
- Taxi
Personaliza cómo se muestran y gestionan en el admin de Django.
"""

from datetime import date

from django.contrib import admin

from .models import Conductor, Taxi


# -------------------------------------------------------------------
# ADMIN: CONDUCTOR
# -------------------------------------------------------------------

# Si Conductor ya estaba registrado en el admin por defecto, se desregistra
# para poder aplicar nuestra configuración personalizada ConductorAdmin.
if Conductor in admin.site._registry:
    admin.site.unregister(Conductor)


@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    """
    Configuración del modelo Conductor en el panel de administración.

    Adaptado al nuevo modelo:
    - nombres / apellidos
    - telefono_principal / telefono_secundario
    - relación 1–1 con UbicacionGeografica
    """

    # Columnas que se muestran en la lista de conductores del admin.
    list_display = (
        "nombres",
        "apellidos",
        "telefono_principal",
        "cedula_identidad",
        "edad_calculada",
        "sexo",
        "estado_civil",
        "ubicacion_str",
        "patente_vigente",
    )

    # Campos por los que se puede buscar desde la barra de búsqueda.
    search_fields = (
        "nombres",
        "apellidos",
        "telefono_principal",
        "cedula_identidad",
        "ubicacion__direccion",
        "ubicacion__estado",
        "ubicacion__municipio",
        "ubicacion__parroquia",
        "ubicacion__sector",
    )

    # Filtros laterales por sexo y estado de pago de patente.
    list_filter = ("sexo", "estado_civil", "pago_patente_realizado")

    # Agrupación de campos en secciones dentro del formulario del admin.
    fieldsets = (
        (
            "Información Personal",
            {
                "fields": (
                    "user",
                    "cedula_identidad",
                    "nombres",
                    "apellidos",
                    "sexo",
                    "estado_civil",
                    "fecha_nacimiento",
                    "rif",
                )
            },
        ),
        (
            "Contacto",
            {
                "fields": (
                    "telefono_principal",
                    "telefono_secundario",
                )
            },
        ),
        (
            "Ubicación geográfica",
            {
                "fields": ("ubicacion",),
            },
        ),
        (
            "Patente",
            {
                "fields": ("pago_patente_realizado", "fecha_pago_patente"),
            },
        ),
    )

    def get_fields(self, request, obj=None):
        """
        Controla qué campos se muestran en el formulario del admin.

        Si obj es None (crear nuevo), igualmente mostramos todo:
        la lógica de negocio decidirá si se usan o no los campos de patente.
        """
        return super().get_fields(request, obj)

    def edad_calculada(self, obj):
        """
        Calcula la edad del conductor a partir de su fecha de nacimiento.
        Se muestra como columna en list_display.
        """
        if obj.fecha_nacimiento:
            hoy = date.today()
            return hoy.year - obj.fecha_nacimiento.year - (
                (hoy.month, hoy.day) < (obj.fecha_nacimiento.month, obj.fecha_nacimiento.day)
            )
        return None

    edad_calculada.short_description = "Edad"

    def ubicacion_str(self, obj):
        """
        Devuelve la ubicación geográfica en formato de texto
        o '-' si no hay ubicación asociada.
        """
        return str(obj.ubicacion) if obj.ubicacion else "-"

    ubicacion_str.short_description = "Ubicación Geográfica"

    def patente_vigente(self, obj):
        """
        Usa la propiedad patente_vigente del modelo Conductor
        para mostrar si la patente está vigente (True/False).
        """
        return obj.patente_vigente

    patente_vigente.boolean = True
    patente_vigente.short_description = "Patente Vigente"


# -------------------------------------------------------------------
# ADMIN: TAXI
# -------------------------------------------------------------------

# Si Taxi ya estaba registrado, se desregistra para aplicar TaxiAdmin.
if Taxi in admin.site._registry:
    admin.site.unregister(Taxi)


@admin.register(Taxi)
class TaxiAdmin(admin.ModelAdmin):
    """
    Configuración del modelo Taxi en el panel de administración.
    """

    # Columnas mostradas en la lista de taxis.
    list_display = ("placa", "modelo", "anio", "conductor")

    # Campos que se pueden buscar desde la barra de búsqueda.
    search_fields = ("placa", "modelo", "nombre_vehiculo", "conductor__cedula_identidad")

    # Filtros laterales por año, modelo y conductor.
    list_filter = ("anio", "modelo", "conductor")
