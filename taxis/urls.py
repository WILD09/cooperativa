from django.urls import path
from . import views

# IMPORTANTE: Este namespace debe coincidir con el usado en los templates (ej: taxis:panel_general)
app_name = 'taxis'

urlpatterns = [
    # ==========================================
    # 1. AUTENTICACIÓN Y REGISTRO (Públicos)
    # ==========================================
    path('registro/', views.select_role, name='select_role'), 
    path('registro/presidente/', views.register_presidente, name='register_presidente'),
    path('registro/verificacion-pendiente/', views.VerificationPendingView.as_view(), name='verification_pending'),
    path('activacion-exitosa/', views.ActivationSuccessView.as_view(), name='activation_success'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('accounts/password_reset/resend/', views.password_reset_resend, name='password_reset_resend'),
    path('confirmar-presidente/<uuid:token>/', views.confirm_president_registration, name='confirm_president_registration'),
    path('reenviar-activacion/', views.activation_resend, name='activation_resend'),
    path('cancelar-registro/', views.cancel_registration, name='cancel_registration'),


    # ==========================================
    # 2. DASHBOARD Y PANEL (Privados)
    # ==========================================
    path('panel/', views.panel_general, name='panel_general'),
    path('ayuda/', views.ayuda_sistema, name='ayuda_sistema'),

    # ==========================================
    # 3. GESTIÓN DE CONDUCTORES (AFILIADOS)
    # ==========================================
    path('conductores/', views.ConductorListView.as_view(), name='conductor_list'),
    path('conductores/nuevo/', views.ConductorCreateView.as_view(), name='conductor_create'),
    path('conductores/<int:pk>/', views.ConductorDetailView.as_view(), name='conductor_detail'),
    path('conductores/<int:pk>/editar/', views.ConductorUpdateView.as_view(), name='conductor_update'),
    path('conductores/<int:pk>/eliminar/', views.ConductorDeleteView.as_view(), name='conductor_delete'),
    
    # AJAX para carga dinámica y validaciones
    path('ajax/check-duplicado/', views.ajax_check_duplicado, name='ajax_check_duplicado'),
    path('ajax/buscar-chofer/', views.buscar_chofer, name='buscar_chofer'),

    # ==========================================
    # 4. GESTIÓN DE VEHÍCULOS
    # ==========================================
    path('vehiculos/', views.VehiculoListView.as_view(), name='vehiculo_list'),
    path('vehiculos/nuevo/', views.VehiculoCreateView.as_view(), name='vehiculo_create'),
    path('vehiculos/<int:pk>/', views.VehiculoDetailView.as_view(), name='vehiculo_detail'),
    path('vehiculos/<int:pk>/editar/', views.VehiculoUpdateView.as_view(), name='vehiculo_update'),
    path('vehiculos/<int:pk>/eliminar/', views.VehiculoDeleteView.as_view(), name='vehiculo_delete'),
    
    # API de validación en tiempo real
    path('api/validar-vehiculo/', views.validar_datos_vehiculo, name='validar_datos_vehiculo'),

    # ==========================================
    # 5. DT5 - DATOS DE TRANSPORTISTAS
    # ==========================================
    path('dt5/', views.DT5ListView.as_view(), name='dt5_list'),
    path('dt5/<int:pk>/', views.DT5DetailView.as_view(), name='dt5_detail'),
    path('reportes/dt5/pdf/', views.reporte_dt5_pdf, name='reporte_dt5_pdf'),
    path('reportes/dt5/excel/', views.reporte_dt5_excel, name='reporte_dt5_excel'),

    # ==========================================
    # 6. DOCUMENTOS Y REPORTES
    # ==========================================
    path('documentos/', views.DocumentoLegalListView.as_view(), name='legal_list'),
    path('documentos/nuevo/', views.DocumentoLegalCreateView.as_view(), name='legal_create'),
    path('documentos/<int:pk>/eliminar/', views.DocumentoLegalDeleteView.as_view(), name='legal_delete'),
    
    # Reportes Afiliados
    path('reportes/afiliados/pdf/', views.reporte_afiliados_pdf, name='reporte_afiliados_pdf'),
    path('reportes/afiliados/excel/', views.reporte_afiliados_excel, name='reporte_afiliados_excel'),
    
    # Reportes Vehículos
    path('reportes/vehiculos/pdf/', views.reporte_vehiculos_pdf, name='reporte_vehiculos_pdf'),
    path('reportes/vehiculos/excel/', views.reporte_vehiculos_excel, name='reporte_vehiculos_excel'),
    

    # ==========================================
    # 7. FINANZAS Y AUDITORÍA
    # ==========================================
    # Sistema antiguo (deprecado, mantener por compatibilidad temporal)
    path('finanzas/deudas-antiguo/', views.DeudaListView.as_view(), name='deuda_list'),
    path('finanzas/pagos-antiguo/', views.PagoListView.as_view(), name='pago_list'),
    path('finanzas/deudas-antiguo/<int:pk>/pagar/', views.RegistrarPagoView.as_view(), name='registrar_pago'),
    
    # NUEVO MÓDULO DE FINANZAS SIMPLIFICADO
    path('finanzas/', views.finanzas_principal, name='finanzas_principal'),
    path('finanzas/registrar/<int:conductor_id>/', views.finanzas_registrar_pago, name='finanzas_registrar_pago'),
    path('finanzas/historial/', views.finanzas_historial, name='finanzas_historial'),
    path('finanzas/ver/<int:pago_id>/', views.finanzas_ver_pago, name='finanzas_ver_pago'),
    path('finanzas/cierre-mensual/', views.ejecutar_cierre_mensual, name='ejecutar_cierre_mensual'),
    path('auditoria/', views.MovimientoAuditListView.as_view(), name='auditoria_list'),

    # ==========================================
    # 8. PERFIL Y CONFIGURACIÓN
    # ==========================================
    path('perfil/', views.PerfilUsuarioView.as_view(), name='perfil_usuario'),
    path('perfil/avatar/', views.actualizar_avatar_presidente, name='actualizar_avatar_presidente'),
    path('perfil/cambiar-clave/', views.CambiarClaveView.as_view(), name='cambiar_clave'),
    path('perfil/eliminar-cuenta/', views.SolicitarEliminacionCuentaView.as_view(), name='solicitar_eliminacion'),
    path('perfil/eliminar-cuenta/confirmar/', views.ConfirmarEliminacionCuentaView.as_view(), name='confirmar_eliminacion'),
]
