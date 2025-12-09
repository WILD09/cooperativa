# urls.py
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

from django.urls import path  # Importa la función path para definir rutas URL.

from .views import (  # Importa todas las vistas que se usarán en las rutas.
    ConductorListView,              # Vista para listar conductores.
    ConductorDetailView,            # Vista para detalle de un conductor.
    TaxiListView,                   # Vista para listar taxis.
    TaxiDetailView,                 # Vista para detalle de un taxi.
    ConductorCreateView,            # Vista para crear un conductor.
    ConductorUpdateView,            # Vista para editar un conductor.
    ConductorDeleteView,            # Vista para eliminar un conductor.
    TaxiCreateView,                 # Vista para crear un taxi.
    TaxiUpdateView,                 # Vista para editar un taxi.
    TaxiDeleteView,                 # Vista para eliminar un taxi.
    register_presidente_asociado,   # Vista de registro (presidente / asociado).
    select_role,                    # Vista para seleccionar el rol antes de registrar.
    index,                          # Vista de página de inicio de la app.
    verify_email_view,              # Vista para verificar el correo con código.
    verification_success_view,      # Vista de éxito tras verificación del correo.
    dashboard_admin,                # Dashboard para rol presidente.
    dashboard_asociado,             # Dashboard para rol asociado.
    login_redirect_view,            # Vista que redirige según rol tras login.
    password_reset_request_view,    # Paso 1: solicitar código de reset por correo.
    password_reset_verify_view,     # Paso 2: verificar código de reset.
    password_reset_new_password_view,  # Paso 3: definir nueva contraseña.
    password_reset_complete_view,   # Vista final tras reset exitoso.
    eliminar_cuenta_presidente,
)

# Define el espacio de nombres de la app en las URLs reversas: 'taxis:...'
app_name = "taxis"

# Lista de patrones de URL de la aplicación.
urlpatterns = [
    # ----------------------------
    # PÁGINAS GENERALES / DASHBOARD
    # ----------------------------

    # Ruta raíz de la app 'taxis', muestra la página de inicio.
    path("", index, name="index"),

    # Dashboard para el rol presidente (administrador).
    path("dashboard/", dashboard_admin, name="dashboard-admin"),

    # Dashboard para el rol asociado.
    path("dashboard-asociado/", dashboard_asociado, name="dashboard-asociado"),

    # ----------------------------
    # CRUD CONDUCTORES
    # ----------------------------

    # Lista de conductores.
    path("conductores/", ConductorListView.as_view(), name="conductor-list"),

    # Detalle de un conductor específico (por pk).
    path("conductores/<int:pk>/", ConductorDetailView.as_view(), name="conductor-detail"),

    # Crear un nuevo conductor.
    path("conductores/crear/", ConductorCreateView.as_view(), name="conductor-create"),

    # Editar un conductor existente.
    path("conductores/<int:pk>/editar/", ConductorUpdateView.as_view(), name="conductor-edit"),

    # Eliminar un conductor.
    path("conductores/<int:pk>/borrar/", ConductorDeleteView.as_view(), name="conductor-delete"),

    # ----------------------------
    # CRUD TAXIS
    # ----------------------------

    # Lista de taxis.
    path("taxis/", TaxiListView.as_view(), name="taxi-list"),

    # Detalle de un taxi específico (por pk).
    path("taxis/<int:pk>/", TaxiDetailView.as_view(), name="taxi-detail"),

    # Crear un nuevo taxi.
    path("taxis/crear/", TaxiCreateView.as_view(), name="taxi-create"),

    # Editar un taxi existente.
    path("taxis/<int:pk>/editar/", TaxiUpdateView.as_view(), name="taxi-edit"),

    # Eliminar un taxi.
    path("taxis/<int:pk>/borrar/", TaxiDeleteView.as_view(), name="taxi-delete"),

    # ----------------------------
    # REGISTRO Y VERIFICACIÓN POR CORREO
    # ----------------------------

    # Pantalla para elegir rol (presidente o asociado) antes de registrarse.
    path("seleccionar-rol/", select_role, name="select_role"),

    # Pantalla de registro (usa el rol elegido para decidir el formulario).
    path("registro/", register_presidente_asociado, name="register"),

    # Verificación de correo electrónico con código de 6 dígitos.
    # Recibe el ID del usuario que está verificando su cuenta.
    path(
        "verificar-correo/<int:user_id>/",
        verify_email_view,
        name="verify_email",
    ),

    # Pantalla de verificación completada con éxito (correo verificado).
    path(
        "verificacion/completada/",
        verification_success_view,
        name="verification_success",
    ),

    # ----------------------------
    # REDIRECCIÓN POST-LOGIN
    # ----------------------------

    # Redirige al dashboard adecuado según el rol del usuario logueado.
    path("redirigir-despues-login/", login_redirect_view, name="login-redirect"),

    # ----------------------------
    # RESTABLECIMIENTO DE CONTRASEÑA POR EMAIL
    # ----------------------------

    # Paso 1: formulario para introducir el correo y solicitar el código.
    path(
        "password-reset/",
        password_reset_request_view,
        name="password_reset",
    ),

    # Paso 2: pantalla para introducir el código enviado al correo.
    path(
        "password-reset/verify/",
        password_reset_verify_view,
        name="password_reset_verify",
    ),

    # Paso 3: pantalla para introducir y confirmar la nueva contraseña.
    path(
        "password-reset/new-password/",
        password_reset_new_password_view,
        name="password_reset_new_password",
    ),

    # Paso final: confirmación de que la contraseña se cambió correctamente.
    path(
        "password-reset/complete/",
        password_reset_complete_view,
        name="password_reset_complete",
    ),

     path(
        "presidente/eliminar-cuenta/",
        eliminar_cuenta_presidente,
        name="eliminar_cuenta_presidente",
    ),
]
