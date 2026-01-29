"""
cooperativa/settings.py
Configuración principal del proyecto Django 'cooperativa'.
Optimizado para Render, desarrollo local con python-decouple.
"""


from pathlib import Path
import os
from django.contrib.messages import constants as messages
from decouple import config
import dj_database_url


# -------------------------------------------------------------------
# RUTA BASE DEL PROYECTO
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent



# -------------------------------------------------------------------
# SEGURIDAD BÁSICA
# -------------------------------------------------------------------
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-development-key-change-in-production",
)


DEBUG = config("DEBUG", default="True").lower() == "true"


ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
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



SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default="False").lower() == "true"
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default="False").lower() == "true"
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default="False").lower() == "true"



# -------------------------------------------------------------------
# APLICACIONES INSTALADAS
# -------------------------------------------------------------------
INSTALLED_APPS = [
    # TUS APPS PRIMERO
    "taxis",   
    "core",    
    
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "widget_tweaks", 
]



# -------------------------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
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
# BASE DE DATOS (LOCAL + PRODUCTION)
# -------------------------------------------------------------------
if os.environ.get("DATABASE_URL"):
    # En Render/Producción: usa la variable DATABASE_URL
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=600,
        )
    }
else:
    # En desarrollo local: usa SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }



# -------------------------------------------------------------------
# VALIDACIÓN DE CONTRASEÑAS Y USUARIO
# -------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "taxis.validators.CustomMinLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]



AUTH_USER_MODEL = "taxis.CustomUser"



# -------------------------------------------------------------------
# INTERNACIONALIZACIÓN
# -------------------------------------------------------------------
LANGUAGE_CODE = "es-ve"
TIME_ZONE = "America/Caracas"
USE_I18N = True
USE_TZ = True



# -------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA
# -------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"



MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"



DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"



# -------------------------------------------------------------------
# CONFIGURACIÓN DE CORREO (SMTP REAL)
# -------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True



EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="tucorreo@gmail.com")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="tu_app_password")



DEFAULT_FROM_EMAIL = f"Cooperativa <{EMAIL_HOST_USER}>"



# -------------------------------------------------------------------
# LOGIN / LOGOUT
# -------------------------------------------------------------------
LOGIN_URL = "/login/"
LOGOUT_REDIRECT_URL = "/login/"

# Usamos el namespace 'taxis' para evitar errores de reversa
LOGIN_REDIRECT_URL = "taxis:panel_general"



MESSAGE_TAGS = {
    messages.DEBUG: "alert-secondary",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}



# -------------------------------------------------------------------
# CONFIGURACIÓN DE CACHE (Para reenvío de correos con límite)
# -------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}



# -------------------------------------------------------------------
# TIEMPO DE VALIDEZ DE TOKENS (Global: Reset Password y Activación)
# -------------------------------------------------------------------
# 86400 segundos = 24 horas
PASSWORD_RESET_TIMEOUT = 86400
