"""
Módulo de configuración de URLs para la aplicación 'taxis'.
Define las rutas de acceso a vistas relacionadas con:
- página de inicio,
- dashboards,
- CRUD de conductores y taxis,
- flujo de registro y verificación por correo,
- restablecimiento de contraseña,
- redirección post-login.
"""

from django.urls import path

from .views import (
    ConductorListView,
    ConductorDetailView,
    TaxiListView,
    TaxiDetailView,
    ConductorCreateView,
    ConductorUpdateView,
    ConductorDeleteView,
    TaxiCreateView,
    TaxiUpdateView,
    TaxiDeleteView,
    register_presidente,
    select_role,
    index,
    verify_email_view,
    verification_success_view,
    panel_general,
    login_redirect_view,
    password_reset_request_view,
    password_reset_verify_view,
    password_reset_new_password_view,
    password_reset_complete_view,
    actualizar_avatar_presidente,
)

app_name = "taxis"

urlpatterns = [
    # ... (anteriores)
    path(
        "presidente/actualizar-avatar/",
        actualizar_avatar_presidente,
        name="actualizar_avatar_presidente",
    ),
    # PÁGINAS GENERALES / DASHBOARD
    path("", index, name="index"),

    # Panel General - Nuevo dashboard principal del Presidente
    path("panel-general/", panel_general, name="panel-general"),



    # CRUD CONDUCTORES

    path("conductores/", ConductorListView.as_view(), name="conductor-list"),
    path("conductores/<int:pk>/", ConductorDetailView.as_view(), name="conductor-detail"),
    path("conductores/crear/", ConductorCreateView.as_view(), name="conductor-create"),
    path("conductores/<int:pk>/editar/", ConductorUpdateView.as_view(), name="conductor-edit"),
    path("conductores/<int:pk>/borrar/", ConductorDeleteView.as_view(), name="conductor-delete"),

    # CRUD TAXIS
    path("taxis/", TaxiListView.as_view(), name="taxi-list"),
    path("taxis/<int:pk>/", TaxiDetailView.as_view(), name="taxi-detail"),
    path("taxis/crear/", TaxiCreateView.as_view(), name="taxi-create"),
    path("taxis/<int:pk>/editar/", TaxiUpdateView.as_view(), name="taxi-edit"),
    path("taxis/<int:pk>/borrar/", TaxiDeleteView.as_view(), name="taxi-delete"),

    # REGISTRO Y VERIFICACIÓN POR CORREO
    path("seleccionar-rol/", select_role, name="select_role"),
    path("registro/", register_presidente, name="register"),
    path(
        "verificar-correo/<int:user_id>/",
        verify_email_view,
        name="verify_email",
    ),
    path(
        "verificacion/completada/",
        verification_success_view,
        name="verification_success",
    ),

    # REDIRECCIÓN POST-LOGIN
    path("redirigir-despues-login/", login_redirect_view, name="login-redirect"),

    # RESTABLECIMIENTO DE CONTRASEÑA POR EMAIL
    path(
        "password-reset/",
        password_reset_request_view,
        name="password_reset",
    ),
    path(
        "password-reset/verify/",
        password_reset_verify_view,
        name="password_reset_verify",
    ),
    path(
        "password-reset/new-password/",
        password_reset_new_password_view,
        name="password_reset_new_password",
    ),
    path(
        "password-reset/complete/",
        password_reset_complete_view,
        name="password_reset_complete",
    ),


]
