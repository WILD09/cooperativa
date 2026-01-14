"""
cooperativa/urls.py
URL principal del proyecto.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

# Importamos la vista login desde taxis para la raíz, 
# pero idealmente usaremos el name 'taxis:login' en el redirect
from taxis.views import CustomLoginView 

urlpatterns = [
    # -------------------------------------------------------------------------
    # REDIRECCIÓN RAÍZ
    # -------------------------------------------------------------------------
    # Redirige a 'taxis:login' en lugar de 'login' a secas para usar el namespace
    path(
        "",
        RedirectView.as_view(
            pattern_name="taxis:login", 
            permanent=False,
        ),
        name="root_redirect",
    ),

    # -------------------------------------------------------------------------
    # ADMIN DE DJANGO
    # -------------------------------------------------------------------------
    path("admin/", admin.site.urls),

    # -------------------------------------------------------------------------
    # APP PRINCIPAL (TAXIS) - ¡AQUÍ ESTÁ EL CAMBIO CLAVE!
    # -------------------------------------------------------------------------
    # Agregamos namespace="taxis" para que coincida con app_name='taxis'
    path("taxis/", include("taxis.urls", namespace="taxis")),

    # -------------------------------------------------------------------------
    # AUTENTICACIÓN (LOGIN CUSTOM GLOBAL)
    # -------------------------------------------------------------------------
    # Opcional: Mantener esta ruta corta si quieres acceder a /login/ directamente
    # pero apuntando a la lógica de tu app.
    path(
        "login/",
        CustomLoginView.as_view(),
        name="login",
    ),

    # -------------------------------------------------------------------------
    # NOTA SOBRE PASSWORD RESET:
    # -------------------------------------------------------------------------
    # Como ya definimos las rutas de 'reset/password/' DENTRO de taxis/urls.py
    # usando tus templates personalizados (taxis/password_reset...), 
    # NO es necesario repetirlas aquí afuera a menos que quieras rutas duplicadas.
    # El include de abajo ("django.contrib.auth.urls") provee las versiones por defecto,
    # pero tus rutas en 'taxis/' tendrán prioridad si se usan correctamente.
    
    path("accounts/", include("django.contrib.auth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
