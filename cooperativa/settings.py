"""
cooperativa/settings.py
Configuración principal del proyecto Django 'cooperativa'.

- Seguridad básica (SECRET_KEY, DEBUG, ALLOWED_HOSTS).
- Apps instaladas, middlewares, plantillas.
- Base de datos (PostgreSQL vía DATABASE_URL, con fallback a SQLite).
- Autenticación (usuario personalizado, validador de contraseñas).
- Internacionalización, estáticos (WhiteNoise), email, Twilio, mensajes y login.
"""

from pathlib import Path
import os

from django.contrib.messages import constants as messages  # Mapeo de niveles de mensajes.
from decouple import config                                 # Lectura de variables desde .env.
import dj_database_url                                      # Para parsear DATABASE_URL


# -------------------------------------------------------------------
# RUTA BASE DEL PROYECTO
# -------------------------------------------------------------------

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
# Para Render, luego pon algo como: "tu-app.onrender.com"
ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
).split(",")


# -------------------------------------------------------------------
# CABECERAS Y COOKIES SEGURAS
# -------------------------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

SECURE_SSL_REDIRECT = config(
    "DJANGO_SECURE_SSL_REDIRECT", default="False"
).lower() == "true"

CSRF_COOKIE_SECURE = config(
    "DJANGO_CSRF_COOKIE_SECURE", default="False"
).lower() == "true"

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
    "core",    # Vistas/plantillas generales.
    "taxis",   # Aplicación principal de la cooperativa de taxis.

    # Apps de terceros.
    "widget_tweaks",  # Para modificar widgets de formularios en plantillas.
]


# -------------------------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise para servir estáticos en producción (Render, etc.)
    "whitenoise.middleware.WhiteNoiseMiddleware",

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

ROOT_URLCONF = "cooperativa.urls"

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

WSGI_APPLICATION = "cooperativa.wsgi.application"


# -------------------------------------------------------------------
# BASE DE DATOS
# -------------------------------------------------------------------
#
# En Render es típico usar una variable DATABASE_URL (PostgreSQL).
# En desarrollo, si no hay DATABASE_URL, se usa SQLite por defecto.
# Si quieres forzar PostgreSQL con variables separadas, puedes ajustar.

default_db_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", default_db_url),
        conn_max_age=600,
    )
}


# -------------------------------------------------------------------
# VALIDACIÓN DE CONTRASEÑAS
# -------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "taxis.validators.CustomMinLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]


# -------------------------------------------------------------------
# MODELO DE USUARIO PERSONALIZADO
# -------------------------------------------------------------------

AUTH_USER_MODEL = "taxis.CustomUser"


# -------------------------------------------------------------------
# INTERNACIONALIZACIÓN Y ZONA HORARIA
# -------------------------------------------------------------------

LANGUAGE_CODE = "es-ve"
TIME_ZONE = "America/Caracas"
USE_I18N = True
USE_TZ = True


# -------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS
# -------------------------------------------------------------------
#
# Configuración compatible con WhiteNoise:
# - STATICFILES_DIRS: directorio de estáticos en desarrollo.
# - STATIC_ROOT: carpeta a donde collectstatic reúne todos los estáticos.
# - STATICFILES_STORAGE: almacenamiento comprimido para producción.

STATIC_URL = "/static/"

STATICFILES_DIRS = [BASE_DIR / "static"]

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# -------------------------------------------------------------------
# CLAVE PRIMARIA POR DEFECTO
# -------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -------------------------------------------------------------------
# CONFIGURACIÓN DE CORREO (SMTP / EMAIL)
# -------------------------------------------------------------------

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default="True").lower() == "true"

EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default=f"Cooperativa <{EMAIL_HOST_USER}>",
)


# -------------------------------------------------------------------
# CONFIGURACIÓN DE ACTIVACIÓN / REGISTRO
# -------------------------------------------------------------------

ACCOUNT_ACTIVATION_DAYS = config("ACCOUNT_ACTIVATION_DAYS", default=3, cast=int)
REGISTRATION_AUTO_LOGIN = False

# URL adonde redirigir después de login (según rol, vista en app 'taxis').
LOGIN_REDIRECT_URL = "taxis:login-redirect"


# -------------------------------------------------------------------
# TWILIO (PARA SMS) – ACTUALMENTE NO SE USA EN EL FLUJO DE VERIFICACIÓN
# -------------------------------------------------------------------

TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_FROM_NUMBER = config("TWILIO_FROM_NUMBER", default="")


# -------------------------------------------------------------------
# CONFIGURACIÓN DE MENSAJES (Bootstrap alerts)
# -------------------------------------------------------------------

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
#
# Ahora tu login principal está en /login/ (no /accounts/login/).

LOGIN_URL = "/login/"
LOGOUT_REDIRECT_URL = "/login/"
