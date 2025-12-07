"""
WSGI config for cooperativa project.

Este módulo expone la aplicación WSGI como una variable de nivel de módulo
llamada ``application``.

Se usa tanto por:
- el servidor de desarrollo de Django,
- como en despliegues en servidores WSGI (Gunicorn, uWSGI, mod_wsgi, etc.).

Más info: https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os  # Módulo estándar para trabajar con variables de entorno.

from django.core.wsgi import get_wsgi_application  # Crea la instancia WSGI de Django.


# Define el módulo de settings por defecto que usará Django al inicializar
# la aplicación WSGI. Debe apuntar al archivo de configuración principal.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cooperativa.settings")

# Objeto WSGI que el servidor usará como punto de entrada para atender peticiones HTTP.
application = get_wsgi_application()
