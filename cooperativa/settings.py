"""
cooperativa/settings.py
Configuración principal del proyecto Django 'cooperativa'.

- Seguridad básica (SECRET_KEY, DEBUG, ALLOWED_HOSTS).
- Apps instaladas, middlewares, plantillas.
- Base de datos (PostgreSQL mediante variables de entorno).
- Autenticación (usuario personalizado, validador de contraseñas).
- Internacionalización, estáticos, email, Twilio, mensajes y login.
"""

from pathlib import Path
import os

from django.contrib.messages import constants as messages  # Mapeo de niveles de mensajes.
from decouple import config                                 # Lectura de variables desde .env.


# -------------------------------------------------------------------
# RUTA BASE DEL PROYECTO
# -------------------------------------------------------------------

# BASE_DIR apunta al directorio raíz del proyecto (carpeta que contiene manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------------------------------------------------
# SEGURIDAD BÁSICA
# -------------------------------------------------------------------

# Clave secreta usada por Django para firmar cookies, tokens, etc.
# En producción debe venir desde la variable de entorno DJANGO_SECRET_KEY.
SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="django-insecure-development-key-change-in-production",
)

# Modo debug:
# - True en desarrollo (muestra errores detallados).
# - False en producción (no muestra detalles de error).
DEBUG = config("DJANGO_DEBUG", default="True").lower() == "true"

# Lista de hosts permitidos para servir la aplicación.
# Se lee desde DJANGO_ALLOWED_HOSTS (separados por comas); por defecto localhost.
ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
).split(",")


# -------------------------------------------------------------------
# CABECERAS Y COOKIES SEGURAS
# -------------------------------------------------------------------

# Activa filtro de XSS en navegadores compatibles.
SECURE_BROWSER_XSS_FILTER = True

# Previene que el navegador intente adivinar el tipo de contenido.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Cookies de sesión solo accesibles desde HTTP (no por JavaScript).
SESSION_COOKIE_HTTPONLY = True

# Cookie de CSRF solo accesible desde HTTP.
CSRF_COOKIE_HTTPONLY = True

# Bloquea carga del sitio en iframes (protección contra clickjacking).
X_FRAME_OPTIONS = "DENY"

# Redirección a HTTPS (True en producción detrás de HTTPS).
SECURE_SSL_REDIRECT = config(
    "DJANGO_SECURE_SSL_REDIRECT", default="False"
).lower() == "true"

# Marca cookie de CSRF como segura (solo por HTTPS) según entorno.
CSRF_COOKIE_SECURE = config(
    "DJANGO_CSRF_COOKIE_SECURE", default="False"
).lower() == "true"

# Marca cookie de sesión como segura (solo por HTTPS) según entorno.
SESSION_COOKIE_SECURE = config(
    "DJANGO_SESSION_COOKIE_SECURE", default="False"
).lower() == "true"


# -------------------------------------------------------------------
# APLICACIONES INSTALADAS
# -------------------------------------------------------------------

INSTALLED_APPS = [
    # Apps de Django por defecto.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Apps propias del proyecto.
    "core",     # (asumiendo que contiene vistas/plantillas generales).
    "taxis",    # Aplicación principal de la cooperativa de taxis.
    # Apps de terceros.
    "widget_tweaks",  # Para modificar widgets de formularios en plantillas.
]


# -------------------------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# -------------------------------------------------------------------
# CONFIGURACIÓN DE URLS Y TEMPLATES
# -------------------------------------------------------------------

# Módulo que contiene la configuración principal de URLs del proyecto.
ROOT_URLCONF = "cooperativa.urls"

# Configuración del motor de plantillas.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Directorio global de plantillas (además de las plantillas de cada app).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,  # Busca plantillas dentro de cada app (templates/).
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Aplicación WSGI, usada en despliegues tradicionales (Apache, Gunicorn, etc.).
WSGI_APPLICATION = "cooperativa.wsgi.application"


# -------------------------------------------------------------------
# BASE DE DATOS
# -------------------------------------------------------------------

# Configuración de la base de datos principal (PostgreSQL).
# Todos los parámetros se leen desde variables de entorno.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",          # Motor de base de datos.
        "NAME": config("DB_NAME"),                          # Nombre de la base.
        "USER": config("DB_USER"),                          # Usuario de base de datos.
        "PASSWORD": config("DB_PASSWORD"),                  # Contraseña.
        "HOST": config("DB_HOST", default="localhost"),     # Host de la base.
        "PORT": config("DB_PORT", default="5432"),          # Puerto (5432 por defecto).
    }
}


# -------------------------------------------------------------------
# VALIDACIÓN DE CONTRASEÑAS
# -------------------------------------------------------------------

# Lista de validadores de contraseñas.
# Aquí se usa un validador personalizado mínimo (longitud).
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "taxis.validators.CustomMinLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]


# -------------------------------------------------------------------
# MODELO DE USUARIO PERSONALIZADO
# -------------------------------------------------------------------

# Indica a Django que use el modelo CustomUser definido en la app 'taxis'.
AUTH_USER_MODEL = "taxis.CustomUser"


# -------------------------------------------------------------------
# INTERNACIONALIZACIÓN Y ZONA HORARIA
# -------------------------------------------------------------------

# Código de idioma por defecto (Español de Venezuela).
LANGUAGE_CODE = "es-ve"

# Zona horaria por defecto.
TIME_ZONE = "America/Caracas"

# Habilita internazionalización (traducciones).
USE_I18N = True

# Usa fechas/horas conscientes de zona horaria (timezone-aware).
USE_TZ = True


# -------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS
# -------------------------------------------------------------------

# URL base para servir archivos estáticos.
STATIC_URL = "/static/"

# Directorios adicionales donde buscar archivos estáticos en desarrollo.
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]


# -------------------------------------------------------------------
# CLAVE PRIMARIA POR DEFECTO
# -------------------------------------------------------------------

# Tipo de campo automático por defecto para claves primarias.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -------------------------------------------------------------------
# CONFIGURACIÓN DE CORREO (SMTP / EMAIL)
# -------------------------------------------------------------------

# Backend de email que se usará:
# - Por defecto, consola (imprime correos en la terminal).
# - En producción, suele configurarse un backend SMTP real.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

# Parámetros SMTP (solo se usan si EMAIL_BACKEND es SMTP real).
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default="True").lower() == "true"

# Credenciales SMTP.
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# Dirección de correo por defecto usada en el campo "From" de los emails.
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default=f"Cooperativa <{EMAIL_HOST_USER}>",
)


# -------------------------------------------------------------------
# CONFIGURACIÓN DE ACTIVACIÓN / REGISTRO
# -------------------------------------------------------------------

# Días que dura válida una activación de cuenta (si se usa django-registration).
ACCOUNT_ACTIVATION_DAYS = config("ACCOUNT_ACTIVATION_DAYS", default=3, cast=int)

# Indica si el usuario se inicia sesión automáticamente tras registro (aquí False).
REGISTRATION_AUTO_LOGIN = False

# URL adonde redirigir después de login (se usa nombre de URL de la app 'taxis').
LOGIN_REDIRECT_URL = "taxis:login-redirect"


# -------------------------------------------------------------------
# TWILIO (PARA SMS) – ACTUALMENTE NO SE USA EN EL FLUJO DE VERIFICACIÓN
# -------------------------------------------------------------------

# Credenciales de Twilio (por si se reactivan SMS en el futuro).
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_FROM_NUMBER = config("TWILIO_FROM_NUMBER", default="")  # Número emisor


# -------------------------------------------------------------------
# CONFIGURACIÓN DE MENSAJES (Bootstrap alerts)
# -------------------------------------------------------------------

# Mapea los niveles de mensajes de Django a clases de Bootstrap.
MESSAGE_TAGS = {
    messages.DEBUG: "alert-secondary",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}


# -------------------------------------------------------------------
# LOGIN / LOGOUT
# -------------------------------------------------------------------

# URL a la que se redirige después de hacer logout.
LOGOUT_REDIRECT_URL = "/accounts/login/"

# URL de la página de login (usada por @login_required).
LOGIN_URL = "/accounts/login/"
