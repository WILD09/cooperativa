"""
cooperativa/urls.py
URL principal del proyecto.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

from taxis.views import CustomLoginView

urlpatterns = [
    # -------------------------------------------------------------------------
    # REDIRECCIÓN RAÍZ
    # -------------------------------------------------------------------------
    path(
        "",
        RedirectView.as_view(
            pattern_name="taxis:login",
            permanent=False,
        ),
        name="root_redirect",
    ),

    # -------------------------------------------------------------------------
    # ADMIN
    # -------------------------------------------------------------------------
    path("admin/", admin.site.urls),

    # -------------------------------------------------------------------------
    # APP PRINCIPAL (TAXIS)
    # -------------------------------------------------------------------------
    path("taxis/", include(("taxis.urls", "taxis"), namespace="taxis")),

    # -------------------------------------------------------------------------
    # LOGIN CORTO (opcional)
    # -------------------------------------------------------------------------
    path("login/", CustomLoginView.as_view(), name="login"),

    # -------------------------------------------------------------------------
    # FAVICON
    # -------------------------------------------------------------------------
    path(
        "favicon.ico",
        RedirectView.as_view(url=settings.STATIC_URL + "img/logo.ico", permanent=True),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
