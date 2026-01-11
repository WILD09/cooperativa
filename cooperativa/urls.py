"""
cooperativa/urls.py
URL principal del proyecto.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from taxis.views import CustomLoginView
from taxis.forms import EmailOrUsernameAuthenticationForm

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path(
        "",
        RedirectView.as_view(
            pattern_name="login",
            permanent=False,
        ),
        name="root_redirect",
    ),

    path("admin/", admin.site.urls),

    path("taxis/", include(("taxis.urls", "taxis"), namespace="taxis")),

    path(
        "login/",
        CustomLoginView.as_view(),
        name="login",
    ),

    path("accounts/", include("django.contrib.auth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
