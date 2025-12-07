"""
cooperativa/urls.py
URL principal del proyecto.

- Redirección de la raíz del sitio a la vista de login.
- Ruta de administración.
- Inclusión de URLs de la app 'taxis'.
- Inclusión de URLs de autenticación de Django.
- Login personalizado usando EmailOrUsernameAuthenticationForm.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

# Importamos la vista genérica de login de Django
from django.contrib.auth.views import LoginView
# Importamos nuestro formulario de login personalizado
from taxis.forms import EmailOrUsernameAuthenticationForm


urlpatterns = [
    # Raíz del sitio: redirige a la página de login
    # Ej: http://127.0.0.1:8000/ -> http://127.0.0.1:8000/login/
    path(
        "",
        RedirectView.as_view(
            pattern_name="login",   # nombre de la URL de login
            permanent=False,        # redirección temporal (302)
        ),
        name="root_redirect",
    ),

    # Admin de Django
    path("admin/", admin.site.urls),

    # Rutas de la app 'taxis'
    # Usa namespacing para evitar conflictos de nombres de URL
    path("taxis/", include(("taxis.urls", "taxis"), namespace="taxis")),

    # Ruta de LOGIN personalizada:
    # - Usa nuestro template registration/login.html
    # - Usa EmailOrUsernameAuthenticationForm (usuario o correo)
    path(
        "login/",
        LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=EmailOrUsernameAuthenticationForm,
        ),
        name="login",
    ),

    # Rutas de autenticación incorporadas (logout, password_change, etc.)
    # OJO: aquí también hay una ruta /accounts/login/, pero tu login principal es /login/
    path("accounts/", include("django.contrib.auth.urls")),
]
