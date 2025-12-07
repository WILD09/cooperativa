"""
ASGI config for cooperativa project.

Este módulo expone la aplicación ASGI como una variable de nivel de módulo
llamada ``application``.

Se usa cuando se despliega el proyecto en un servidor ASGI (Daphne, Uvicorn,
Hypercorn, etc.), según la documentación oficial de Django.
"""

import os  # Módulo estándar para trabajar con variables de entorno y rutas.

from django.core.asgi import get_asgi_application  # Crea la instancia ASGI de Django.


# Define el módulo de settings por defecto que usará Django al inicializar
# la aplicación ASGI. Debe apuntar al archivo de configuración principal.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cooperativa.settings")

# Objeto ASGI que el servidor usará como punto de entrada para atender peticiones.
application = get_asgi_application()
