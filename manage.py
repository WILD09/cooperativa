#!/usr/bin/env python
"""
manage.py
Punto de entrada de línea de comandos para el proyecto Django.

Permite ejecutar comandos administrativos como:
- runserver
- migrate
- createsuperuser
- test
etc.
"""

import os
import sys


def main():
    """
    Ejecuta tareas administrativas de Django.

    - Define la variable de entorno DJANGO_SETTINGS_MODULE,
      apuntando al módulo de settings del proyecto ('cooperativa.settings').
    - Importa y delega en execute_from_command_line, que interpreta
      los argumentos de la línea de comandos (sys.argv).
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cooperativa.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Mensaje de error más claro si Django no está instalado o el entorno no está activo.
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # Ejecuta el comando solicitado (por ejemplo 'runserver', 'migrate', etc.).
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    # Solo se ejecuta main() cuando el archivo se corre directamente (no en import).
    main()
