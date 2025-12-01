from django.urls import path
from django.contrib.auth import views as auth_views
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
    register,  # Función vista para registro
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
    index,  # Vista raíz
)

app_name = 'taxis'

urlpatterns = [
    path('', index, name='index'),  # Vista raíz

    path('conductores/', ConductorListView.as_view(), name='conductor-list'),
    path('conductores/<int:pk>/', ConductorDetailView.as_view(), name='conductor-detail'),
    path('conductores/crear/', ConductorCreateView.as_view(), name='conductor-create'),
    path('conductores/<int:pk>/editar/', ConductorUpdateView.as_view(), name='conductor-edit'),
    path('conductores/<int:pk>/borrar/', ConductorDeleteView.as_view(), name='conductor-delete'),

    path('taxis/', TaxiListView.as_view(), name='taxi-list'),
    path('taxis/<int:pk>/', TaxiDetailView.as_view(), name='taxi-detail'),
    path('taxis/crear/', TaxiCreateView.as_view(), name='taxi-create'),
    path('taxis/<int:pk>/editar/', TaxiUpdateView.as_view(), name='taxi-edit'),
    path('taxis/<int:pk>/borrar/', TaxiDeleteView.as_view(), name='taxi-delete'),

    # Registro de usuarios con función vista personalizada
    path('registro/', register, name='register'),

    # Rutas para restablecer contraseña con templates personalizados
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='taxis/forgot-password.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='taxis/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='taxis/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='taxis/password_reset_complete.html'),
         name='password_reset_complete'),
]
