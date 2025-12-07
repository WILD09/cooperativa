"""
apps.py
Configuración de la aplicación Django 'taxis'.
Permite a Django reconocer y registrar la app dentro del proyecto.
"""

from django.apps import AppConfig  # Clase base para configuración de aplicaciones.


class TaxisConfig(AppConfig):
    """
    Configuración de la aplicación 'taxis'.

    - default_auto_field:
        Define el tipo de campo automático por defecto para las claves primarias.
        'BigAutoField' usa enteros grandes (BIGINT), recomendado en proyectos nuevos.
    - name:
        Nombre de la aplicación dentro del proyecto (ruta del módulo Python).
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "taxis"
