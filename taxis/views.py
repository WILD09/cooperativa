# Standard library
import calendar
import os
import random
import time
from datetime import date, timedelta
from io import BytesIO

# Third-party (reportes)
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from xhtml2pdf import pisa

# Django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.hashers import make_password
from django.views.decorators.http import require_http_methods


# Local
from .forms import (
    ConductorForm, VehiculoForm, PresidenteRegisterForm,
    EmailOrUsernameAuthenticationForm, PagoForm,
    UbicacionGeograficaForm, PagoMensualForm
)
from .models import (
    Conductor, Vehiculo, CustomUser, UbicacionGeografica,
    Deuda, Pago, MovimientoAudit, ConfiguracionCooperativa, ConfiguracionGlobal,
    DocumentoLegal, EmailVerificationCode,
    ConfiguracionFinanzas,
    PagoMensual, PendingPresidentRegistration
)
from .utils import render_to_pdf

# --- DATOS FIJOS DE LA COOPERATIVA ---
DATOS_COOP = {
    'nombre': 'WILSON TORRES 33, R.L.',
    'rif': 'J-40126249-0',
    'direccion': 'CALLE LA GLORIA, CASA N° 115-C, SECTOR JESÚS BANDRES. SAN JUAN DE LOS MORROS - ESTADO GUÁRICO',
    'presidente': 'WILSON TORRES',
    'telefono': '0416-6444886',
    'email': 'wilsontorres27@gmail.com',
    'municipio': 'JUAN GERMAN ROSCIO',
}

def obtener_rutas_logos():
    """
    Obtiene rutas de logos absolutas para xhtml2pdf en Windows.
    Prioriza la ruta estática confirmada por el usuario.
    """
    # Ruta base del proyecto
    base_dir = settings.BASE_DIR
    
    # Directorios donde buscar
    search_dirs = [
        os.path.join(base_dir, 'static', 'img'),
        os.path.join(settings.STATIC_ROOT, 'img') if settings.STATIC_ROOT else None,
        os.path.join(base_dir, 'media', 'vehiculos'),
    ]
    
    logo_transporte = ""
    logo_mision = ""
    
    for directory in search_dirs:
        if not directory or not os.path.exists(directory):
            continue
            
        t_path = os.path.join(directory, 'logo_transporte.png')
        m_path = os.path.join(directory, 'logo_gran_mision.png')
        
        if not logo_transporte and os.path.exists(t_path):
            # En Windows xhtml2pdf a veces prefiere la ruta absoluta con / y sin file:///
            logo_transporte = t_path.replace(os.sep, '/')
            
        if not logo_mision and os.path.exists(m_path):
            logo_mision = m_path.replace(os.sep, '/')
            
        if logo_transporte and logo_mision:
            break
            
    return logo_transporte, logo_mision

# ====================================================================
# CONFIGURACIÓN Y SISTEMA (AJAX)
# ====================================================================

@login_required
@require_http_methods(["GET"])
def ajax_check_duplicado(request):
    """
    Vista AJAX para validar unicidad de:
    - cedula (cédula de identidad)
    - rif (RIF del conductor)
    - email (correo electrónico)
    - telefono (teléfono principal)
    
    Parámetros GET esperados:
    - campo: tipo de validación (cedula, rif, email, telefono)
    - valor: valor a validar
    - excludeid: ID del conductor actual (para edición, excluir de búsqueda)
    
    Retorna:
    - {'existe': True/False}
    """
    # ✅ CORRECCIÓN 1: Nombre de parámetro 'excludeid' (sin guion, minúscula)
    campo = request.GET.get('campo')
    valor = request.GET.get('valor', '').strip()
    exclude_id = request.GET.get('excludeid')  # ✅ CORREGIDO

    # Validar entrada básica
    if not campo or not valor:
        return JsonResponse({'existe': False})

    existe = False

    # Base de querysets
    qs_cond = Conductor.objects.all()
    
    # ✅ CORRECCIÓN 2: Convertir a int y manejar excepciones
    if exclude_id:
        try:
            exclude_id = int(exclude_id)
            qs_cond = qs_cond.exclude(pk=exclude_id)
        except (ValueError, TypeError):
            pass  # Si no es un número válido, ignorar la exclusión

    qs_users = CustomUser.objects.all()

    # ✅ VALIDACIONES POR TIPO DE CAMPO
    
    if campo == 'cedula':
        # ✅ CORRECCIÓN 3: Limpiar números igual que en el formulario
        val_limpio = ''.join(filter(str.isdigit, valor))
        existe = qs_cond.filter(cedula_identidad=val_limpio).exists()

    elif campo == 'rif':
        # ✅ CORRECCIÓN 4: Limpiar números para RIF
        val_limpio = ''.join(filter(str.isdigit, valor))
        existe = qs_cond.filter(rif=val_limpio).exists()

    elif campo == 'email':
        # Email se valida sin cambios (case-insensitive)
        existe_cond = qs_cond.filter(email__iexact=valor).exists()
        existe_user = qs_users.filter(email__iexact=valor).exists()
        existe = existe_cond or existe_user

    elif campo == 'telefono':
        # Limpiar teléfono y comparar últimos 10 dígitos
        val_limpio = ''.join(filter(str.isdigit, valor))
        val_comparar = val_limpio[-10:] if len(val_limpio) >= 10 else val_limpio

        # A. Revisar en Conductores
        for c in qs_cond:
            if c.telefono_principal:
                db_limpio = ''.join(filter(str.isdigit, c.telefono_principal))
                db_comparar = db_limpio[-10:] if len(db_limpio) >= 10 else db_limpio
                if db_comparar == val_comparar:
                    existe = True
                    break

        # B. Revisar en Usuarios (solo si no encontró en Conductores)
        if not existe:
            for u in qs_users:
                tlf_user = getattr(u, 'phone_number', '')
                if tlf_user:
                    db_limpio = ''.join(filter(str.isdigit, str(tlf_user)))
                    db_comparar = db_limpio[-10:] if len(db_limpio) >= 10 else db_limpio
                    if db_comparar == val_comparar:
                        existe = True
                        break

    return JsonResponse({'existe': existe})

@login_required
def buscar_chofer(request):
    """
    AJAX: Buscar chofer (Conductor) por cédula.
    Retorna:
    - encontrado: bool
    - id: int
    - nombre: str
    """
    cedula = request.GET.get('cedula', '').strip()
    if not cedula:
        return JsonResponse({'encontrado': False})

    cedula_limpia = ''.join(filter(str.isdigit, cedula))
    if not cedula_limpia:
        return JsonResponse({'encontrado': False})

    conductor = Conductor.objects.filter(cedula_identidad=cedula_limpia).first()
    if not conductor:
        return JsonResponse({'encontrado': False})

    return JsonResponse({
        'encontrado': True,
        'id': conductor.id,
        'nombre': f"{conductor.nombres} {conductor.apellidos}",
    })

@login_required
def validar_datos_vehiculo(request):
    """
    API AJAX para validar Placa, Serial y Casco en tiempo real.
    Devuelve si existe y un mensaje personalizado.
    """
    campo = request.GET.get('campo')
    valor = request.GET.get('valor', '').strip().upper()
    exclude_id = request.GET.get('exclude_id')

    if not campo or not valor:
        return JsonResponse({'existe': False})

    existe = False
    mensaje = ""
    qs = Vehiculo.objects.all()
    
    if exclude_id and exclude_id not in ['None', '']:
        qs = qs.exclude(id=exclude_id)

    if campo == 'placa':
        existe = qs.filter(placa=valor).exists()
        if existe:
            mensaje = "Esta placa ya está registrada en el sistema."
            
    elif campo == 'serial_niv':
        existe = qs.filter(serial_niv=valor).exists()
        if existe:
            mensaje = "Este serial de carrocería (NIV) ya existe."
            
    elif campo == 'numero_casco':
        existe = qs.filter(numero_casco=valor).exists()
        if existe:
            mensaje = "Este número de casco ya está asignado a otro vehículo."

    return JsonResponse({'existe': existe, 'mensaje': mensaje})


@login_required
def ejecutar_cierre_mensual(request):
    if request.user.role.upper() != 'PRESIDENTE':
        messages.error(request, "No tienes permisos para ejecutar esta acción.")
        return redirect('taxis:panel_general')

    tasa_actual = ConfiguracionGlobal.get_tasa()
    monto_bs = float(tasa_actual) * 5.00

    afiliados_activos = Conductor.objects.filter(estado='activo')
    hoy = timezone.now().date()
    count_deudas = 0
    
    with transaction.atomic():
        for afiliado in afiliados_activos:
            existe = Deuda.objects.filter(conductor=afiliado, mes=hoy.month, anio=hoy.year).exists()
            if not existe:
                Deuda.objects.create(
                    conductor=afiliado, mes=hoy.month, anio=hoy.year,
                    monto_bs=monto_bs, concepto=f"Cuota {hoy.month}/{hoy.year}",
                    pagada=False, fecha_vencimiento=hoy + timezone.timedelta(days=5)
                )
                count_deudas += 1

        fecha_limite = timezone.now() - timezone.timedelta(days=365)
        pagos_viejos = Pago.objects.filter(fecha_pago__lt=fecha_limite)
        count_borrados = pagos_viejos.count()
        pagos_viejos.delete()

    MovimientoAudit.objects.create(
        usuario=request.user,
        accion=f"Ejecutó cierre mensual: {count_deudas} deudas generadas",
        modulo="Finanzas"
    )
    messages.success(request, f"Cierre completado: {count_deudas} deudas nuevas, {count_borrados} pagos archivados.")
    return redirect('taxis:panel_general')

# ====================================================================
# PERFIL Y GESTOR DOCUMENTAL
# ====================================================================

class PerfilUsuarioView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    fields = ['first_name', 'last_name', 'email', 'phone_number', 'avatar']
    template_name = 'taxis/perfil_usuario.html'
    success_url = reverse_lazy('taxis:perfil_usuario')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Tu perfil ha sido actualizado.")

        MovimientoAudit.objects.create(
        usuario=self.request.user,
        accion=f"Actualizó perfil ({self.request.user.first_name} {self.request.user.last_name})",
        modulo="Perfiles"
    )
        return super().form_valid(form)

class CambiarClaveView(LoginRequiredMixin, PasswordChangeView):
    form_class = PasswordChangeForm
    template_name = 'taxis/cambiar_clave.html'
    success_url = reverse_lazy('taxis:perfil_usuario')

    def form_valid(self, form):
        messages.success(self.request, "Contraseña actualizada correctamente.")
        return super().form_valid(form)

class DocumentoLegalListView(LoginRequiredMixin, ListView):
    model = DocumentoLegal
    template_name = 'taxis/legal_list.html'
    context_object_name = 'documentos'

class DocumentoLegalCreateView(LoginRequiredMixin, CreateView):
    model = DocumentoLegal
    fields = ['titulo', 'archivo', 'descripcion']
    template_name = 'taxis/legal_form.html'
    success_url = reverse_lazy('taxis:legal_list')

    def form_valid(self, form):
        messages.success(self.request, "Documento subido al repositorio.")
        return super().form_valid(form)

class DocumentoLegalDeleteView(LoginRequiredMixin, DeleteView):
    model = DocumentoLegal
    template_name = 'taxis/legal_confirm_delete.html'
    success_url = reverse_lazy('taxis:legal_list')

# ====================================================================
# ELIMINACIÓN DE CUENTA
# ====================================================================

class SolicitarEliminacionCuentaView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'taxis/eliminar_cuenta_paso1.html')

    def post(self, request):
        codigo = str(random.randint(100000, 999999))
        EmailVerificationCode.objects.create(
            user=request.user, code=codigo, email_type='delete_account',
            created_at=timezone.now(), expires_at=timezone.now() + timedelta(minutes=10)
        )
        asunto = "CÓDIGO DE SEGURIDAD: Eliminar Cuenta"
        mensaje = (
            f"Hola {request.user.first_name}.\n\n"
            f"Has solicitado eliminar tu cuenta.\n"
            f"TU CÓDIGO DE SEGURIDAD ES: {codigo}\n\n"
            f"Este código expirará en 10 minutos.\n"
            f"Si no fuiste tú, cambia tu contraseña inmediatamente."
        )
        try:
            send_mail(asunto, mensaje, 'sistema@cooperativa.com', [request.user.email], fail_silently=True)
            messages.info(request, f"Hemos enviado un código de 6 dígitos a {request.user.email}")
            return redirect('taxis:confirmar_eliminacion')
        except Exception:
            messages.error(request, "Error enviando el correo. Revisa la consola.")
            return redirect('taxis:solicitar_eliminacion')

class ConfirmarEliminacionCuentaView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'taxis/eliminar_cuenta_paso2.html')

    def post(self, request):
        codigo_ingresado = request.POST.get('codigo')
        verificacion = EmailVerificationCode.objects.filter(
            user=request.user, code=codigo_ingresado, email_type='delete_account',
            is_used=False, expires_at__gte=timezone.now()
        ).first()
        
        if verificacion:
            verificacion.is_used = True
            verificacion.save()
            user = request.user
            MovimientoAudit.objects.create(
                usuario=None,
                accion=f"El usuario {user.email} eliminó su cuenta permanentemente.",
                modulo="Seguridad"
            )
            logout(request)
            user.delete()
            messages.success(request, "Tu cuenta ha sido eliminada permanentemente.")
            return redirect('taxis:login')
        else:
            messages.error(request, "Código incorrecto o expirado.")
            return redirect('taxis:confirmar_eliminacion')

# ====================================================================
# CONDUCTORES Y VEHÍCULOS
# ====================================================================

class ConductorListView(LoginRequiredMixin, ListView):
    model = Conductor
    template_name = "taxis/conductor_list.html"
    context_object_name = "conductores"
    paginate_by = 10

    def get_queryset(self):
        qs = Conductor.objects.select_related('ubicacion').order_by('id')
    
        q = self.request.GET.get('q')
        if q:
           qs = qs.filter(
                Q(nombres__icontains=q) |
                Q(apellidos__icontains=q) |
                Q(cedula_identidad__icontains=q)
            )

        genero = self.request.GET.get('genero')
        if genero:
           qs = qs.filter(sexo=genero)

        edo_civil = self.request.GET.get('edo_civil')
        if edo_civil:
           qs = qs.filter(estadocivil=edo_civil)

        return qs

class ConductorDetailView(LoginRequiredMixin, DetailView):
    model = Conductor
    template_name = "taxis/conductor_detail.html"
    context_object_name = "conductor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = timezone.now().date()
        return context

class ConductorCreateView(LoginRequiredMixin, CreateView):
    model = Conductor
    form_class = ConductorForm
    template_name = "taxis/conductor_form.html"
    success_url = reverse_lazy("taxis:conductor_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['ubicacion_form'] = UbicacionGeograficaForm(self.request.POST)
        else:
            context['ubicacion_form'] = UbicacionGeograficaForm()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        ubicacion_form = context['ubicacion_form']

        if form.is_valid() and ubicacion_form.is_valid():
            with transaction.atomic():
                ubicacion = ubicacion_form.save()
                self.object = form.save(commit=False)
                self.object.ubicacion = ubicacion
                self.object.save()
                MovimientoAudit.objects.create(
                    usuario=self.request.user,
                    accion=f"Creó afiliado: {self.object.nombres}",
                    modulo="Afiliados"
                )
            messages.success(self.request, "Afiliado registrado exitosamente.")
            return redirect(self.success_url)

        return self.render_to_response(self.get_context_data(form=form))

class ConductorUpdateView(LoginRequiredMixin, UpdateView):
    model = Conductor
    form_class = ConductorForm
    template_name = "taxis/conductor_form.html"

    def get_success_url(self):
        return reverse('taxis:conductor_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['ubicacion_form'] = UbicacionGeograficaForm(self.request.POST, instance=self.object.ubicacion)
        else:
            context['ubicacion_form'] = UbicacionGeograficaForm(instance=self.object.ubicacion)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        ubicacion_form = context['ubicacion_form']

        if form.is_valid() and ubicacion_form.is_valid():
            with transaction.atomic():
                ubicacion_form.save()
                self.object = form.save()
                MovimientoAudit.objects.create(
                    usuario=self.request.user,
                    accion=f"Actualizó afiliado: {self.object.nombres}",
                    modulo="Afiliados"
                )
            messages.success(self.request, "Afiliado actualizado.")
            return redirect(self.get_success_url())

        return self.render_to_response(self.get_context_data(form=form))

class ConductorDeleteView(LoginRequiredMixin, DeleteView):
    model = Conductor
    template_name = "taxis/conductor_confirm_delete.html"
    success_url = reverse_lazy("taxis:conductor_list")

class VehiculoListView(LoginRequiredMixin, ListView):
    model = Vehiculo
    template_name = "taxis/vehiculo_list.html"
    context_object_name = "vehiculos"
    paginate_by = 10

    def get_queryset(self):
        qs = Vehiculo.objects.select_related('conductor').order_by('id')

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(numero_casco__icontains=q) |
                Q(placa__icontains=q) |
                Q(marca__icontains=q) |
                Q(modelo__icontains=q) |
                Q(conductor__nombres__icontains=q) |
                Q(conductor__apellidos__icontains=q) |
                Q(conductor__cedula_identidad__icontains=q)
            )

        estado = self.request.GET.get('estado')
        if estado in ['operativo', 'inoperativo']:
            qs = qs.filter(condicion=estado)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estado_actual'] = self.request.GET.get('estado', 'todos')
        return context

class VehiculoDetailView(LoginRequiredMixin, DetailView):
    model = Vehiculo
    template_name = "taxis/vehiculo_detail.html"
    context_object_name = "vehiculo"

class VehiculoCreateView(LoginRequiredMixin, CreateView):
    model = Vehiculo
    form_class = VehiculoForm
    template_name = "taxis/vehiculo_form.html"
    success_url = reverse_lazy("taxis:vehiculo_list")

    def get_initial(self):
        initial = super().get_initial()
        conductor_id = self.request.GET.get('conductor')
        if conductor_id:
            initial['conductor'] = conductor_id
        return initial

    def form_valid(self, form):
        self.object = form.save()
        
        MovimientoAudit.objects.create(
            usuario=self.request.user,
            accion=f"Vehículo creado: {self.object.placa}",
            modulo="Vehículos"
        )
        messages.success(self.request, "Vehículo registrado exitosamente.")
        
        return HttpResponseRedirect(self.success_url)

class VehiculoUpdateView(LoginRequiredMixin, UpdateView):
    model = Vehiculo
    form_class = VehiculoForm
    template_name = "taxis/vehiculo_form.html"

    def get_success_url(self):
        return reverse_lazy("taxis:vehiculo_detail", kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        self.object = form.save()
        
        MovimientoAudit.objects.create(
            usuario=self.request.user,
            accion=f"Vehículo actualizado: {self.object.placa}",
            modulo="Vehículos"
        )
        messages.success(self.request, "Vehículo actualizado exitosamente.")
        
        return HttpResponseRedirect(self.get_success_url())

class VehiculoDeleteView(LoginRequiredMixin, DeleteView):
    model = Vehiculo
    template_name = "taxis/vehiculo_confirm_delete.html"
    success_url = reverse_lazy("taxis:vehiculo_list")

# ====================================================================
# DT5 - DATOS DE TRANSPORTISTAS (Consolidado Conductor + Vehículo)
# ====================================================================

class DT5ListView(LoginRequiredMixin, ListView):
    """Vista de Datos de Transportistas (Conductores + Vehículos)"""
    model = Vehiculo
    template_name = "taxis/dt5_list.html"
    context_object_name = "transportistas"
    paginate_by = 15

    def get_queryset(self):
        qs = Vehiculo.objects.select_related('conductor').order_by('numero_casco')
        
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(numero_casco__icontains=q) |
                Q(placa__icontains=q) |
                Q(conductor__nombres__icontains=q) |
                Q(conductor__apellidos__icontains=q) |
                Q(conductor__cedula_identidad__icontains=q)
            )
        
        estado = self.request.GET.get('estado')
        if estado in ['operativo', 'inoperativo']:
            qs = qs.filter(condicion=estado)
        
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estado_actual'] = self.request.GET.get('estado', 'todos')
        return context

class DT5DetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Vista de detalle completo de un transportista (Conductor + Vehículo)
    Solo lectura, sin opción de editar o eliminar
    """
    model = Vehiculo
    template_name = 'taxis/dt5_detail.html'
    context_object_name = 'vehiculo'

    def test_func(self):
        return self.request.user.is_authenticated

    def get_queryset(self):
        return Vehiculo.objects.select_related('conductor')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehiculo = self.get_object()
        conductor = vehiculo.conductor
        
        # Calcular edad del conductor
        if conductor.fechanacimiento:
            hoy = timezone.now().date()
            edad = hoy.year - conductor.fechanacimiento.year
            if hoy.month < conductor.fechanacimiento.month or \
               (hoy.month == conductor.fechanacimiento.month and hoy.day < conductor.fechanacimiento.day):
                edad -= 1
            context['edad'] = edad
        
        # Verificar vencimientos (NOMBRES CORREGIDOS SEGÚN TU MODELO)
        hoy = timezone.now().date()
        context['cert_medico_vencido'] = vehiculo.medico_vencimiento and vehiculo.medico_vencimiento < hoy
        context['patente_vencida'] = vehiculo.patente_vencimiento and vehiculo.patente_vencimiento < hoy
        context['lic_circulacion_vencida'] = vehiculo.licencia_vencimiento and vehiculo.licencia_vencimiento < hoy
        context['seguro_vencido'] = vehiculo.rcv_vencimiento and vehiculo.rcv_vencimiento < hoy
        
        return context

# ====================================================================
# REPORTES DT5 (PDF y EXCEL)
# ====================================================================

def obtener_transportistas_filtrados(request):
    """
    Filtra transportistas (SOLO conductores CON vehículos) aplicando los mismos filtros que DT5ListView
    Respeta: búsqueda, estado y MANTIENE el ID del conductor en orden
    """
    # IMPORTANTE: Solo vehículos (excluye conductores sin vehículo)
    qs = Vehiculo.objects.select_related('conductor').order_by('conductor__id', 'numero_casco')
    
    # Filtro de búsqueda (mismo que en la lista)
    q = request.GET.get('q')
    if q:
        qs = qs.filter(
            Q(numero_casco__icontains=q) |
            Q(placa__icontains=q) |
            Q(conductor__nombres__icontains=q) |
            Q(conductor__apellidos__icontains=q) |
            Q(conductor__cedula_identidad__icontains=q)
        )
    
    # Filtro de estado operativo/inoperativo (mismo que en la lista)
    estado = request.GET.get('estado')
    if estado in ['operativo', 'inoperativo']:
        qs = qs.filter(condicion=estado)
    
    return qs

@login_required
def reporte_dt5_pdf(request):
    """
    Genera reporte DT5 oficial en PDF con filtros idénticos a la lista
    SOLO muestra conductores QUE TIENEN vehículo registrado
    """
    transportistas = obtener_transportistas_filtrados(request)

    # 🔥 RUTAS DE LOS LOGOS - CORREGIDAS
    logo_transporte, logo_mision = obtener_rutas_logos()

    context = {
        'transportistas': transportistas,
        'coop': DATOS_COOP,
        'fecha_hoy': timezone.now(),
        'logo_transporte': logo_transporte,
        'logo_mision': logo_mision,
        'filtros': {
            'q': request.GET.get('q'),
            'estado': request.GET.get('estado')
        }
    }

    template = get_template('taxis/reportes/pdf_dt5.html')
    html = template.render(context)

    result = BytesIO()

    pdf = pisa.pisaDocument(
        BytesIO(html.encode("UTF-8")),
        result,
        encoding='UTF-8'
    )

    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"DT5_Transportistas_{timezone.now().strftime('%d-%m-%Y')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        # AUDITORÍA (AQUÍ)
        from taxis.utils import texto_filtros
        MovimientoAudit.objects.create(
            usuario=request.user,
            accion="Generó reporte DT5 PDF",
            modulo="DT5",
            descripcion=texto_filtros(
            q=request.GET.get("q") or None,
            estado=request.GET.get("estado") or "todos",
        ),
           fecha=timezone.localtime(),
    )
        
        return response

    return HttpResponse("Error generando PDF", status=500)


@login_required
def reporte_dt5_excel(request):
    """Genera reporte DT5 en Excel con estructura completa"""
    transportistas = obtener_transportistas_filtrados(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DT5 Transportistas"

    # TÍTULO PRINCIPAL
    ws.merge_cells('A1:T1')
    titulo = f"DT5 - DATOS DE TRANSPORTISTAS - {DATOS_COOP['nombre']}"
    
    estado_filtro = request.GET.get('estado')
    if estado_filtro == 'operativo':
        titulo += " (SOLO OPERATIVOS)"
    elif estado_filtro == 'inoperativo':
        titulo += " (SOLO INOPERATIVOS)"
    elif request.GET.get('q'):
        titulo += " (FILTRADO)"

    ws['A1'] = titulo
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    # ENCABEZADOS PRINCIPALES (Fila 3)
    headers_main = [
        "N°", "NOMBRES", "APELLIDOS", "CÉDULA", "TELÉFONO",
        "MARCA", "MODELO", "AÑO", "COLOR", "PLACA", "CASCO", "CAPACIDAD",
        "BATERÍA", "ACEITE", "COMBUSTIBLE", "CANTIDAD", 
        "CAUCHOS", "RÍN", "OPERATIVO", "INOPERATIVO"
    ]
    ws.append([])  # Fila 2 vacía
    ws.append(headers_main)

    # ESTILOS DE ENCABEZADO
    header_fill = PatternFill(start_color="00b300", end_color="00b300", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=10)

    for cell in ws[3]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')

    # DATOS DE TRANSPORTISTAS
    for i, t in enumerate(transportistas, start=1):
        cedula_full = f"{t.conductor.cedula_prefijo}-{t.conductor.cedula_identidad}"
        
        # Checkmarks para campos booleanos
        bateria = t.bateria_amperaje or "—"
        aceite = t.aceite_viscosidad or "—"
        operativo = "✓" if t.condicion == 'operativo' else "—"
        inoperativo = "✓" if t.condicion == 'inoperativo' else "—"

        row = [
            i,
            t.conductor.nombres,
            t.conductor.apellidos,
            cedula_full,
            t.conductor.telefono_principal or "—",
            t.marca or "—",
            t.modelo or "—",
            t.anio or "—",
            t.color or "—",
            t.placa or "—",
            t.numero_casco or "—",
            t.capacidad or "—",
            bateria,
            aceite,
            t.combustible_tipo or "—",
            t.combustible_litros or "—",
            t.cauchos_medida or "—",
            t.diametro_rin or "—",
            operativo,
            inoperativo
        ]
        ws.append(row)

    # AJUSTAR ANCHOS DE COLUMNA
    dims = {
        'A': 5, 'B': 18, 'C': 18, 'D': 12, 'E': 14, 
        'F': 12, 'G': 12, 'H': 6, 'I': 10, 'J': 12, 
        'K': 10, 'L': 10, 'M': 10, 'N': 10, 'O': 12, 
        'P': 10, 'Q': 10, 'R': 8, 'S': 10, 'T': 12
    }
    for col, width in dims.items():
        ws.column_dimensions[col].width = width

    # GENERAR RESPUESTA EXCEL
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"DT5_Transportistas_{timezone.now().strftime('%d-%m-%Y')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)
    # ========== AUDITORÍA AQUÍ ==========
    from taxis.utils import texto_filtros
    MovimientoAudit.objects.create(
      usuario=request.user,
      accion="Generó reporte DT5 Excel",
      modulo="DT5",
      descripcion=texto_filtros(
        q=request.GET.get("q") or None,
        estado=request.GET.get("estado") or "todos",
    ),
      fecha=timezone.localtime(),
)
    return response

# ====================================================================
# FINANZAS
# ====================================================================

class DeudaListView(LoginRequiredMixin, ListView):
    model = Deuda
    template_name = "taxis/finanzas/deuda_list.html"
    context_object_name = "deudas"
    paginate_by = 20
    ordering = ['-anio', '-mes']


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = "taxis/finanzas/pago_list.html"
    context_object_name = "pagos"
    ordering = ['-fecha_pago']


# --- VISTAS DEL MÓDULO DE FINANZAS SIMPLIFICADO ---


@login_required
def finanzas_principal(request):
    """Vista principal: Muestra afiliados Pendientes (Deuda Acumulada) vs Solvencias del Mes"""
    hoy = timezone.localtime().date()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    config = ConfiguracionFinanzas.get_solo()
    
    # Búsqueda
    q = request.GET.get('q', '')
    
    # 1. Filtrar solo conductores ACTIVOS con VEHÍCULO OPERATIVO
    conductores = Conductor.objects.filter(
        estado='activo', 
        vehiculos__condicion='operativo'
    ).distinct().select_related('ubicacion')
    
    if q:
        conductores = conductores.filter(
            Q(cedula_identidad__icontains=q) | 
            Q(nombres__icontains=q) | 
            Q(apellidos__icontains=q) |
            Q(vehiculos__numero_casco__icontains=q)
        ).distinct()

    # Pre-fetch de pagos para el año actual
    pagos_anio = PagoMensual.objects.filter(
        anio=anio_actual,
        conductor__in=conductores,
        archivado=False  # ✅ FILTRAR NO ARCHIVADOS
    ).values('conductor_id', 'mes')

    # Diccionario de pagos por conductor
    mapa_pagos = {}
    for p in pagos_anio:
        cid = p['conductor_id']
        if cid not in mapa_pagos: 
            mapa_pagos[cid] = set()
        mapa_pagos[cid].add(p['mes'])
    
    pendientes = []
    pagados_completo = []
    
    conductores = conductores.prefetch_related('vehiculos')
    
    # Meses a verificar (Desde Enero hasta el mes actual)
    meses_a_verificar = list(range(1, mes_actual + 1))
    
    for c in conductores:
        pagos_c = mapa_pagos.get(c.id, set())
        
        # Verificar Solvencia del Mes Actual
        if mes_actual in pagos_c:
            pago_obj = PagoMensual.objects.filter(
                conductor=c, 
                mes=mes_actual, 
                anio=anio_actual,
                archivado=False
            ).first()
            pagados_completo.append({'conductor': c, 'pago': pago_obj})
        
        # Calcular Deuda Acumulada
        deuda_meses = []
        for m in meses_a_verificar:
            if m not in pagos_c:
                deuda_meses.append(m)
        
        if deuda_meses:
            if mes_actual not in pagos_c:
                total_deuda = len(deuda_meses) * config.monto_cuota_usd
                pendientes.append({
                    'conductor': c, 
                    'meses_deuda': deuda_meses,
                    'total_deuda': total_deuda,
                    'cant_meses': len(deuda_meses)
                })
    
    # Convertir números de mes a nombres
    MESES_NOMBRES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    
    for item in pendientes:
        item['meses_nombres'] = [MESES_NOMBRES[m-1] for m in item['meses_deuda']]
    
    # Ordenar listas
    pendientes.sort(key=lambda x: x['conductor'].id)
    pagados_completo.sort(key=lambda x: x['conductor'].id)
    
    # Limitar pagados visibles
    LIMITE_INICIAL = 5
    pagados_visibles = pagados_completo[:LIMITE_INICIAL]
    pagados_ocultos = pagados_completo[LIMITE_INICIAL:]
    total_ocultos = len(pagados_ocultos)
    
    context = {
        'pendientes': pendientes,
        'pagados': pagados_visibles,
        'pagados_ocultos': pagados_ocultos,
        'total_ocultos': total_ocultos,
        'config': config,
        'mes_actual': mes_actual,
        'anio_actual': anio_actual,
        'hoy': hoy,
        'query': q,
        'mes_nombre': PagoMensual(mes=mes_actual).get_nombre_mes()
    }
    return render(request, 'taxis/finanzas/principal.html', context)


@login_required
def finanzas_registrar_pago(request, conductor_id):
    """Registrar pago mensual para un conductor"""
    conductor = get_object_or_404(Conductor, pk=conductor_id)
    
    vehiculo = conductor.vehiculos.filter(condicion='operativo').first()
    
    if not vehiculo:
        messages.error(request, 'El conductor no tiene un vehículo operativo asignado.')
        return redirect('taxis:finanzas_principal')
    
    config = ConfiguracionFinanzas.get_solo()
    hoy = timezone.localtime().date()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    # Obtener pagos realizados
    pagos_realizados = PagoMensual.objects.filter(
        conductor=conductor,
        anio=anio_actual,
        archivado=False
    ).values_list('mes', flat=True)
    
    meses_pagados = set(pagos_realizados)
    
    MESES_NOMBRES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    
    # Meses adeudados
    meses_adeudados = []
    for m in range(1, mes_actual + 1):
        if m not in meses_pagados:
            meses_adeudados.append({
                'mes': m,
                'anio': anio_actual,
                'nombre': MESES_NOMBRES[m-1],
                'tipo': 'adeudado',
                'es_actual': (m == mes_actual)
            })
    
    # Meses futuros
    meses_futuros = []
    for m in range(mes_actual + 1, 13):
        if m not in meses_pagados:
            meses_futuros.append({
                'mes': m,
                'anio': anio_actual,
                'nombre': MESES_NOMBRES[m-1],
                'tipo': 'futuro'
            })
    
    esta_al_dia = len(meses_adeudados) == 0
    deuda_total = len(meses_adeudados) * config.monto_cuota_usd
    
    import calendar
    from datetime import date
    # Día de vencimiento (por defecto 5)
    dia_venc = getattr(config, 'dia_vencimiento', 5) or 5

# Mes de referencia: el primer mes adeudado; si no hay deuda, mes actual
    mes_ref = meses_adeudados[0]['mes'] if meses_adeudados else mes_actual
    anio_ref = anio_actual

# Ajuste para meses con menos días (ej: febrero)
    ultimo_dia = calendar.monthrange(anio_ref, mes_ref)[1]
    dia_venc = min(dia_venc, ultimo_dia)

    fecha_vencimiento = date(anio_ref, mes_ref, dia_venc)
    mes_vencimiento_nombre = MESES_NOMBRES[mes_ref - 1]
    # PROCESAR POST
    if request.method == 'POST':
        meses_pagar = request.POST.getlist('meses_pagar[]')
        
        if not meses_pagar:
            messages.error(request, 'Debes seleccionar al menos un mes para pagar.')
            return redirect('taxis:finanzas_registrar_pago', conductor_id=conductor_id)
        
        form = PagoMensualForm(request.POST, request.FILES)
        
        if form.is_valid():
            pagos_registrados = []
            meses_duplicados = []
            
            for mes_str in meses_pagar:
                mes, anio = map(int, mes_str.split('-'))
                
                # Verificar duplicados
                if PagoMensual.objects.filter(
                    conductor=conductor, 
                    mes=mes, 
                    anio=anio,
                    archivado=False
                ).exists():
                    meses_duplicados.append(MESES_NOMBRES[mes-1])
                    continue
                
                # Crear el pago
                PagoMensual.objects.create(
                    conductor=conductor,
                    vehiculo=vehiculo,
                    mes=mes,
                    anio=anio,
                    monto_usd=config.monto_cuota_usd,
                    fecha_pago=form.cleaned_data['fecha_pago'],
                    comprobante=form.cleaned_data.get('comprobante'),
                    notas=form.cleaned_data.get('notas', ''),
                    registrado_por=request.user,
                    conductor_nombre_cache=f"{conductor.nombres} {conductor.apellidos}",
                    conductor_cedula_cache=f"{conductor.cedula_prefijo}-{conductor.cedula_identidad}"
                )
                pagos_registrados.append(MESES_NOMBRES[mes-1])

                # LOG AUDITORÍA - Pago registrado
                from taxis.utils import log_pago
                log_pago(
                    conductor=conductor, 
                    monto=config.monto_cuota_usd, 
                    mes=mes, 
                    anio=anio, 
                    request=request
                )
            
            # Mensajes
            if meses_duplicados and not pagos_registrados:
                messages.warning(
                    request, 
                    f'⚠️ Los meses seleccionados ya están registrados: {", ".join(meses_duplicados)}'
                )
                return redirect('taxis:finanzas_principal')
            
            if meses_duplicados and pagos_registrados:
                messages.warning(
                    request, 
                    f'⚠️ Ya registrados: {", ".join(meses_duplicados)}'
                )
            
            if pagos_registrados:
                MovimientoAudit.objects.create(
                    usuario=request.user,
                    accion=f'Registró pagos de {conductor}: {", ".join(pagos_registrados)}',
                    modulo='Finanzas'
                )
                messages.success(request, f'✅ Pagos registrados: {", ".join(pagos_registrados)}')
            
            return redirect('taxis:finanzas_principal')
        
        else:
            # Mostrar errores del formulario
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    
    else:
        # GET: Formulario vacío
        form = PagoMensualForm()
    
    context = {
        'conductor': conductor,
        'vehiculo': vehiculo,
        'form': form,
        'config': config,
        'hoy': hoy,
        'fecha_vencimiento': fecha_vencimiento,
        'mes_vencimiento_nombre': mes_vencimiento_nombre,
        'meses_adeudados': meses_adeudados,
        'meses_futuros': meses_futuros,
        'esta_al_dia': esta_al_dia,
        'deuda_total': deuda_total,
        'anio_actual': anio_actual,
    }
    return render(request, 'taxis/finanzas/registrar_pago_v2.html', context)


@login_required
def finanzas_historial(request):
    """Historial financiero con estadísticas y paginación"""
    from datetime import date
    
    # Verificación de permisos
    if not hasattr(request.user, 'role'):
        messages.error(request, '⚠️ Tu usuario no tiene un rol asignado.')
        return redirect('taxis:panel_general')
    
    if request.user.role.upper() != 'PRESIDENTE':
        messages.warning(request, '⚠️ Solo el presidente puede acceder al historial financiero.')
        return redirect('taxis:finanzas_principal')
    
    hoy = date.today()
    anio_seleccionado = int(request.GET.get('anio', hoy.year))
    mes_seleccionado = request.GET.get('mes', '')
    query = request.GET.get('q', '').strip()
    orden = request.GET.get('orden', '-anio,-mes,-fecha_pago')
    
    # Consulta base - FILTRAR NO ARCHIVADOS
    pagos_qs = PagoMensual.objects.filter(
        archivado=False
    ).select_related('conductor', 'vehiculo').filter(anio=anio_seleccionado)
    
    # Filtro por mes
    if mes_seleccionado:
        pagos_qs = pagos_qs.filter(mes=int(mes_seleccionado))
    
    # Búsqueda
    if query:
        pagos_qs = pagos_qs.filter(
            Q(conductor__nombres__icontains=query) |
            Q(conductor__apellidos__icontains=query) |
            Q(conductor__cedula_identidad__icontains=query) |
            Q(vehiculo__numero_casco__icontains=query)
        ).distinct()
    
    # Ordenamiento
    orden = request.GET.get("orden", "-anio,-mes,-fecha_pago")
    
    # Estadísticas globales
    stats_globales = pagos_qs.aggregate(
        total_recaudado=Sum('monto_usd'),
        total_pagos=Count('id'),
        afiliados_pagaron=Count('conductor', distinct=True)
    )
    
    # Calcular promedio
    if stats_globales['total_pagos'] and stats_globales['total_pagos'] > 0:
        stats_globales['promedio_pago'] = stats_globales['total_recaudado'] / stats_globales['total_pagos']
    else:
        stats_globales['promedio_pago'] = 0
    
    # Manejar valores None
    stats_globales['total_recaudado'] = stats_globales['total_recaudado'] or 0
    stats_globales['total_pagos'] = stats_globales['total_pagos'] or 0
    stats_globales['afiliados_pagaron'] = stats_globales['afiliados_pagaron'] or 0
    
    # Paginación
    paginator = Paginator(pagos_qs, 20)
    page = request.GET.get('page', 1)
    
    try:
        pagos_paginados = paginator.page(page)
    except PageNotAnInteger:
        pagos_paginados = paginator.page(1)
    except EmptyPage:
        pagos_paginados = paginator.page(paginator.num_pages)
    
    # Enriquecer pagos con estados
    for pago in pagos_paginados:
        if pago.anio > hoy.year:
            pago.es_adelantado = True
            pago.es_puntual = False
        elif pago.anio == hoy.year and pago.mes > hoy.month:
            pago.es_adelantado = True
            pago.es_puntual = False
        elif pago.anio == hoy.year and pago.mes == hoy.month and pago.fecha_pago.day <= 5:
            pago.es_puntual = True
            pago.es_adelantado = False
        else:
            pago.es_adelantado = False
            pago.es_puntual = False
    
    # Estadísticas del filtro actual
    total_filtrado = pagos_qs.aggregate(total=Sum('monto_usd'))['total'] or 0
    
    stats_filtradas = {
        'total_pagos_filtrados': pagos_paginados.paginator.count,
        'total_filtrado': total_filtrado,
        'afiliados_unicos': pagos_qs.values('conductor').distinct().count()
    }
    
    # Años disponibles
    anios_disponibles = list(range(hoy.year, hoy.year - 5, -1))
    
    # Meses
    meses_lista = [
        {'num': 1, 'nombre': 'Enero'},
        {'num': 2, 'nombre': 'Febrero'},
        {'num': 3, 'nombre': 'Marzo'},
        {'num': 4, 'nombre': 'Abril'},
        {'num': 5, 'nombre': 'Mayo'},
        {'num': 6, 'nombre': 'Junio'},
        {'num': 7, 'nombre': 'Julio'},
        {'num': 8, 'nombre': 'Agosto'},
        {'num': 9, 'nombre': 'Septiembre'},
        {'num': 10, 'nombre': 'Octubre'},
        {'num': 11, 'nombre': 'Noviembre'},
        {'num': 12, 'nombre': 'Diciembre'},
    ]
    
    context = {
        'pagos': pagos_paginados,
        'stats': {**stats_globales, **stats_filtradas},
        'anio_seleccionado': anio_seleccionado,
        'mes_seleccionado': int(mes_seleccionado) if mes_seleccionado else '',
        'query': query,
        'orden': orden,
        'anios_disponibles': anios_disponibles,
        'meses_lista': meses_lista,
    }
    
    return render(request, 'taxis/finanzas/historial.html', context)


@login_required
def finanzas_ver_pago(request, pago_id):
    """Detalle de un pago mensual con agrupación inteligente"""
    pago = get_object_or_404(
        PagoMensual.objects.select_related('conductor', 'vehiculo', 'registrado_por'), 
        id=pago_id
    )
    
    # Detectar pagos relacionados (misma transacción)
    pagos_agrupados = PagoMensual.objects.filter(
        conductor=pago.conductor,
        fecha_pago=pago.fecha_pago,
        archivado=False
    ).order_by('anio', 'mes')
    
    # Si hay comprobante, filtrar por mismo comprobante
    if pago.comprobante:
        pagos_agrupados = pagos_agrupados.filter(comprobante=pago.comprobante.name)
    
    # Calcular total acumulado
    total_acumulado = sum(p.monto_usd for p in pagos_agrupados)
    
    # Generar string de meses
    MESES_NOMBRES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    
    meses_str = ', '.join([MESES_NOMBRES[p.mes - 1] for p in pagos_agrupados])
    
    # Determinar si es pago múltiple
    es_pago_multiple = pagos_agrupados.count() > 1
    
    context = {
        'pago': pago,
        'pagos_agrupados': pagos_agrupados,
        'total_acumulado': total_acumulado,
        'meses_str': meses_str,
        'es_pago_multiple': es_pago_multiple,
        'coop': DATOS_COOP,
    }
    # AUDITORÍA (AQUÍ)
    MovimientoAudit.objects.create(
       usuario=request.user,
       accion="Imprimió ticket de pago",
       modulo="Finanzas",
       descripcion=f"Pago ID: {pago_id}"
   )

    return render(request, 'taxis/finanzas/ver_pago.html', context)


# Sistema antiguo de deudas (compatibilidad)
class RegistrarPagoView(LoginRequiredMixin, CreateView):
    model = Pago
    form_class = PagoForm
    template_name = "taxis/finanzas/pago_form.html"
    success_url = reverse_lazy("taxis:deuda_list")

    def dispatch(self, request, *args, **kwargs):
        self.deuda = get_object_or_404(Deuda, pk=self.kwargs['pk'])
        if self.deuda.pagada:
            messages.warning(request, "Deuda ya pagada.")
            return redirect("taxis:deuda_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        pago = form.save(commit=False)
        pago.deuda = self.deuda
        pago.save()
        self.deuda.pagada = True
        self.deuda.save()

        MovimientoAudit.objects.create(
            usuario=self.request.user,
            accion=f"Registró pago de {self.deuda.conductor.nombres}",
            modulo="Finanzas"
        )
        messages.success(self.request, "Pago registrado correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deuda'] = self.deuda
        return context

# ====================================================================
# REPORTES AFILIADOS (PDF y EXCEL)
# ====================================================================

def obtener_conductores_filtrados(request):
    qs = Conductor.objects.all().order_by('id')
    q = request.GET.get('q')
    if q:
        qs = qs.filter(Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(cedula_identidad__icontains=q))
    genero = request.GET.get('genero')
    if genero:
        qs = qs.filter(sexo=genero)
    edo_civil = request.GET.get('edo_civil')
    if edo_civil:
        qs = qs.filter(estadocivil=edo_civil)
    return qs

@login_required
def reporte_afiliados_pdf(request):
    conductores = obtener_conductores_filtrados(request)

    # 🔥 RUTAS DE LOS LOGOS - CORREGIDAS
    logo_transporte, logo_mision = obtener_rutas_logos()

    context = {
        'conductores': conductores,
        'coop': DATOS_COOP,
        'fecha_hoy': timezone.now(),
        'logo_transporte': logo_transporte,
        'logo_mision': logo_mision,
        'filtros': {
            'q': request.GET.get('q'),
            'genero': request.GET.get('genero'),
            'edo_civil': request.GET.get('edo_civil')
        }
    }

    template = get_template('taxis/reportes/pdf_afiliados.html')
    html = template.render(context)

    result = BytesIO()

    pdf = pisa.pisaDocument(
        BytesIO(html.encode("UTF-8")),
        result,
        encoding='UTF-8'
    )

    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"Afiliados_{timezone.now().strftime('%d-%m-%Y')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        from taxis.utils import texto_filtros
        MovimientoAudit.objects.create(
          usuario=request.user,
          accion="Generó reporte afiliados PDF",
          modulo="Afiliados",
          descripcion=texto_filtros(
          q=request.GET.get("q") or None,
          genero=request.GET.get("genero") or "todos",
          edocivil=request.GET.get("edocivil") or "todos",
          ),
         fecha=timezone.localtime(),
      )

        return response

    return HttpResponse("Error generando PDF", status=500)

@login_required
def reporte_afiliados_excel(request):
    conductores = obtener_conductores_filtrados(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Afiliados"

    ws.merge_cells('A1:J1')
    titulo = f"AFILIADOS DE LA COOPERATIVA {DATOS_COOP['nombre']}"
    if request.GET.get('q') or request.GET.get('genero') or request.GET.get('edo_civil'):
        titulo += " (REPORTE FILTRADO)"

    ws['A1'] = titulo
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    headers = ["N°", "NOMBRES", "APELLIDOS", "FECHA NAC.", "GÉNERO", "ESTADO CIVIL", "CÉDULA", "RIF", "CORREO", "TELÉFONO"]
    ws.append([])
    ws.append(headers)

    header_fill = PatternFill(start_color="CC0000", end_color="CC0000", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for cell in ws[3]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for i, c in enumerate(conductores, start=1):
        fecha_nac = c.fechanacimiento.strftime('%d/%m/%Y') if c.fechanacimiento else "-"
        cedula_full = f"{c.cedula_prefijo}-{c.cedula_identidad}"
        rif_full = f"{c.rif_prefijo}-{c.rif}"

        row = [
            i, c.nombres, c.apellidos, fecha_nac,
            c.get_sexo_display(), c.get_estadocivil_display(),
            cedula_full, rif_full, c.email, c.telefono_principal
        ]
        ws.append(row)

    dims = {'A': 5, 'B': 20, 'C': 20, 'D': 12, 'E': 10, 'F': 12, 'G': 12, 'H': 15, 'I': 25, 'J': 15}
    for col, width in dims.items():
        ws.column_dimensions[col].width = width

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Afiliados_{timezone.now().strftime('%d-%m-%Y')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)
    # ========== AUDITORÍA AQUÍ ==========
    from taxis.utils import texto_filtros
    MovimientoAudit.objects.create(
     usuario=request.user,
     accion="Generó reporte afiliados Excel",
     modulo="Afiliados",
     descripcion=texto_filtros(
        q=request.GET.get("q") or None,
        genero=request.GET.get("genero") or "todos",
        edocivil=request.GET.get("edocivil") or "todos",
      ),
       fecha=timezone.localtime(),
   )

    return response

# ====================================================================
# REPORTES VEHÍCULOS (PDF y EXCEL)
# ====================================================================

def obtener_vehiculos_filtrados(request):
    """Filtra vehículos por estado (operativo/inoperativo) y búsqueda."""
    qs = Vehiculo.objects.select_related('conductor').order_by('numero_casco')
    
    q = request.GET.get('q')
    if q:
        qs = qs.filter(
            Q(numero_casco__icontains=q) |
            Q(placa__icontains=q) |
            Q(conductor__nombres__icontains=q) |
            Q(conductor__apellidos__icontains=q) |
            Q(conductor__cedula_identidad__icontains=q)
        )
    
    estado = request.GET.get('estado')
    if estado in ['operativo', 'inoperativo']:
        qs = qs.filter(condicion=estado)
    
    return qs

@login_required
def reporte_vehiculos_pdf(request):
    """Genera reporte PDF de vehículos con filtros activos."""
    vehiculos = obtener_vehiculos_filtrados(request)

    # 🔥 RUTAS DE LOS LOGOS - CORREGIDAS
    logo_transporte, logo_mision = obtener_rutas_logos()

    context = {
        'vehiculos': vehiculos,
        'coop': DATOS_COOP,
        'fecha_hoy': timezone.now(),
        'logo_transporte': logo_transporte,
        'logo_mision': logo_mision,
        'filtros': {
            'q': request.GET.get('q'),
            'estado': request.GET.get('estado')
        }
    }

    template = get_template('taxis/reportes/pdf_vehiculos.html')
    html = template.render(context)

    result = BytesIO()

    pdf = pisa.pisaDocument(
        BytesIO(html.encode("UTF-8")),
        result,
        encoding='UTF-8'
    )

    if not pdf.err:
       response = HttpResponse(result.getvalue(), content_type='application/pdf')
       filename = f"Vehiculos_Flota_{timezone.now().strftime('%d-%m-%Y')}.pdf"
       response['Content-Disposition'] = f'inline; filename="{filename}"'

    # AUDITORÍA (AQUÍ)
    from taxis.utils import texto_filtros
    MovimientoAudit.objects.create(
        usuario=request.user,
        accion="Generó reporte vehículos PDF",
        modulo="Vehículos",
        descripcion=texto_filtros(
            q=request.GET.get('q') or None,
            estado=request.GET.get('estado') or "todos"
        ),
        fecha=timezone.localtime(),
    )

    return response
    return HttpResponse("Error generando PDF", status=500)

@login_required
def reporte_vehiculos_excel(request):
    """Genera reporte Excel de vehículos con filtros activos."""
    vehiculos = obtener_vehiculos_filtrados(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Flota Vehicular"

    ws.merge_cells('A1:J1')
    titulo = f"FLOTA VEHICULAR - {DATOS_COOP['nombre']}"
    
    estado_filtro = request.GET.get('estado')
    if estado_filtro == 'operativo':
        titulo += " (SOLO OPERATIVOS)"
    elif estado_filtro == 'inoperativo':
        titulo += " (SOLO INOPERATIVOS)"
    elif request.GET.get('q'):
        titulo += " (REPORTE FILTRADO)"

    ws['A1'] = titulo
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    headers = ["N°", "AFILIADO", "CÉDULA", "MARCA", "MODELO", "AÑO", "COLOR", "PLACA", "SERIAL NIV", "CAPACIDAD"]
    ws.append([])
    ws.append(headers)

    header_fill = PatternFill(start_color="CC0000", end_color="CC0000", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for cell in ws[3]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for i, v in enumerate(vehiculos, start=1):
        conductor_nombre = f"{v.conductor.nombres} {v.conductor.apellidos}"
        cedula_full = f"{v.conductor.cedula_prefijo}-{v.conductor.cedula_identidad}"

        row = [
            i,
            conductor_nombre,
            cedula_full,
            v.marca,
            v.modelo,
            v.anio,
            v.color,
            v.placa,
            v.serial_niv,
            v.capacidad
        ]
        ws.append(row)

    dims = {
        'A': 5,
        'B': 25,
        'C': 12,
        'D': 12,
        'E': 12,
        'F': 6,
        'G': 10,
        'H': 12,
        'I': 20,
        'J': 10
    }
    for col, width in dims.items():
        ws.column_dimensions[col].width = width

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Vehiculos_Flota_{timezone.now().strftime('%d-%m-%Y')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)

    from taxis.utils import texto_filtros
    MovimientoAudit.objects.create(
        usuario=request.user,
        accion="Generar reporte vehículos Excel",
        modulo="Vehículos",
        descripcion=texto_filtros(
            q=request.GET.get('q') or None,
            estado=request.GET.get('estado') or "todos",
            fecha=timezone.localtime()
        )
    )
    
    return response
    # ========== AUDITORÍA AQUÍ ==========
    from taxis.utils import texto_filtros
    MovimientoAudit.objects.create(
      usuario=request.user,
      accion="Generó reporte vehículos Excel",
      modulo="Vehículos",
      descripcion=texto_filtros(
        q=request.GET.get("q") or None,
        estado=request.GET.get("estado") or "todos",
     ),
      fecha=timezone.localtime(),
   )
    return response



# ====================================================================
# AUDITORÍA Y NOTIFICACIONES
# ====================================================================

class MovimientoAuditListView(LoginRequiredMixin, ListView):
    model = MovimientoAudit
    template_name = "taxis/movimientoaudit_list.html"
    context_object_name = "movimientos"
    paginate_by = 30

    MODULO_MAP = {
        "autenticacion": "Autenticación",
        "afiliados": "Afiliados",
        "vehiculos": "Vehículos",
        "finanzas": "Finanzas",
        "dt5": "DT5",
        "configuracion": "Configuración",
    }

    ACCION_KEYWORDS = {
        "login": ["login", "inicio de sesión", "inició sesión"],
        "logout": ["logout", "cierre de sesión"],
        "crear": ["creó", "creado", "registró"],
        "editar": ["editó", "actualizó", "modificó"],
        "eliminar": ["eliminó", "eliminado"],
        "reporte": ["generó reporte", "reporte", "pdf", "excel"],
    }

    ORDERING_MAP = {
        "recientes": "-fecha",
        "antiguos": "fecha",
        "modulo_az": "modulo",
        "modulo_za": "-modulo",
    }

    def get_ordering(self):
        orden = self.request.GET.get("orden", "").strip()
        return self.ORDERING_MAP.get(orden, "-fecha")

    def get_queryset(self):
        qs = MovimientoAudit.objects.select_related("usuario").all()

        # Búsqueda general
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(usuario__first_name__icontains=q) |
                Q(usuario__last_name__icontains=q) |
                Q(usuario__email__icontains=q) |
                Q(accion__icontains=q) |
                Q(modulo__icontains=q)
            )

        # Acción
        accion = self.request.GET.get("accion", "").strip().lower()
        if accion:
            keys = self.ACCION_KEYWORDS.get(accion)
            if keys:
                q_acc = Q()
                for k in keys:
                    q_acc |= Q(accion__icontains=k)
                qs = qs.filter(q_acc)

        # Módulo
        modulo = self.request.GET.get("modulo", "").strip()
        if modulo:
            modulo_real = self.MODULO_MAP.get(modulo.lower(), modulo)
            qs = qs.filter(modulo__icontains=modulo_real)

        # Año/Mes
        anio = self.request.GET.get("anio", "").strip()
        mes = self.request.GET.get("mes", "").strip()
        if anio.isdigit():
            qs = qs.filter(fecha__year=int(anio))
        if mes.isdigit():
            m = int(mes)
            if 1 <= m <= 12:
                qs = qs.filter(fecha__month=m)

        return qs.order_by(self.get_ordering())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["accion_filtro"] = self.request.GET.get("accion", "")
        context["modulo_filtro"] = self.request.GET.get("modulo", "")
        context["anio_filtro"] = self.request.GET.get("anio", "")
        context["mes_filtro"] = self.request.GET.get("mes", "")
        context["orden_filtro"] = self.request.GET.get("orden", "")
        context["modulos_choices"] = list(self.MODULO_MAP.items())

        params = self.request.GET.copy()
        params.pop("page", None)
        context["query_params"] = params.urlencode()
        return context


@login_required
def panel_general(request):
    # ====================================================================
    # LOG AUDITORÍA - Login/Acceso al Panel
    # ====================================================================
    from datetime import date
    from taxis.utils import log_login
    
    today = date.today()
    last_login_date = request.session.get('last_login_date')
    
    if last_login_date != str(today):
        log_login(request)
        request.session['last_login_date'] = str(today)
    
    # ====================================================================
    # PANEL GENERAL - Código Original
    # ====================================================================
    
    hoy = timezone.now().date()
    # Solo mostramos alertas de documentos YA VENCIDOS
    
    alertas_documentos = []

    # Alertas de Conductores (Cédula y RIF)
    conductores = Conductor.objects.filter(estado='activo')
    for c in conductores:
        if c.cedula_vencimiento and c.cedula_vencimiento < hoy:
            tipo_doc = 'Cédula'
            alertas_documentos.append({
                'tipo': 'conductor',
                'conductor_id': c.id,
                'conductor_nombre': f"{c.nombres} {c.apellidos}",
                'titulo': f'{tipo_doc} vencida',
                'descripcion': f"El documento {tipo_doc} venció el {c.cedula_vencimiento.strftime('%d/%m/%Y')}",
                'documento_tipo': tipo_doc,
                'fecha_vencimiento': c.cedula_vencimiento
            })
        if c.rif_vencimiento and c.rif_vencimiento < hoy:
            tipo_doc = 'RIF'
            alertas_documentos.append({
                'tipo': 'conductor',
                'conductor_id': c.id,
                'conductor_nombre': f"{c.nombres} {c.apellidos}",
                'titulo': f'{tipo_doc} vencido',
                'descripcion': f"El documento {tipo_doc} venció el {c.rif_vencimiento.strftime('%d/%m/%Y')}",
                'documento_tipo': tipo_doc,
                'fecha_vencimiento': c.rif_vencimiento
            })

    # Alertas de Vehículos (Patente, Licencia, RCV, Médico)
    vehiculos = Vehiculo.objects.select_related('conductor').all()
    for v in vehiculos:
        checks = [
            ('Patente', v.patente_vencimiento),
            ('Licencia', v.licencia_vencimiento),
            ('RCV', v.rcv_vencimiento),
            ('Médico', v.medico_vencimiento)
        ]
        for tipo_doc, fecha in checks:
            if fecha and fecha < hoy:
                alertas_documentos.append({
                    'tipo': 'vehiculo',
                    'vehiculo_id': v.id,
                    'conductor_nombre': f"{v.conductor.nombres} {v.conductor.apellidos}",
                    'titulo': f'{tipo_doc} vencida' if tipo_doc != 'RCV' and tipo_doc != 'Médico' else f'{tipo_doc} vencido',
                    'descripcion': f"El documento {tipo_doc} del vehículo {v.placa} venció el {fecha.strftime('%d/%m/%Y')}",
                    'documento_tipo': tipo_doc,
                    'fecha_vencimiento': fecha
                })

    alertas_documentos.sort(key=lambda x: x['fecha_vencimiento'])

    # ✅ CORREGIDO: Misma lógica que finanzas_principal
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    # Obtener conductores activos con vehículo operativo (minúscula)
    conductores_con_vehiculo = Conductor.objects.filter(
        estado='activo',
        vehiculos__condicion='operativo'  # ✅ Con minúscula
    ).distinct()
    
    # Pre-fetch de pagos del mes actual
    pagos_mes_actual = PagoMensual.objects.filter(
        mes=mes_actual,
        anio=anio_actual,
        conductor__in=conductores_con_vehiculo
    ).values_list('conductor_id', flat=True)
    
    # Contar conductores con vehículo operativo que NO pagaron el mes actual
    pagos_pendientes_count = conductores_con_vehiculo.exclude(
        id__in=pagos_mes_actual
    ).count()

    context = {
        'total_afiliados': Conductor.objects.count(),
        'total_vehiculos': Vehiculo.objects.count(),
        'pagos_pendientes': pagos_pendientes_count,
        'alertas_documentos': alertas_documentos,
        'tasa_actual': ConfiguracionGlobal.get_tasa(),
        'coop': DATOS_COOP
    }
    return render(request, 'taxis/panel_general.html', context)


@login_required
def ayuda_sistema(request):
    return render(request, 'taxis/ayuda.html')


@login_required
@require_POST
def actualizar_avatar_presidente(request):
    if 'avatar' in request.FILES:
        request.user.avatar = request.FILES['avatar']
        request.user.save()
        MovimientoAudit.objects.create(
          usuario=request.user,
          accion="Actualizó foto de perfil",
          modulo="Configuración",
      )
        return JsonResponse({'status': 'ok', 'url': request.user.avatar.url})
    return JsonResponse({'status': 'error'}, status=400)

# ====================================================================
# AUTH Y REGISTRO
# ====================================================================

class CustomLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailOrUsernameAuthenticationForm

    def get_success_url(self):
        return reverse_lazy("taxis:panel_general")


def login_redirect_view(request):
    return redirect("taxis:panel_general")


def select_role(request):
    presidente_activo_existe = CustomUser.objects.filter(role='presidente', is_active=True).exists()

    if request.method == "POST":
        rol_seleccionado = request.POST.get('role')
        if rol_seleccionado == 'presidente':
            if presidente_activo_existe:
                messages.error(request, "Ya existe un presidente activo en el sistema.")
                return redirect('taxis:login')
            return redirect('taxis:register_presidente')

    return render(request, 'taxis/select_role.html', {'presidente_existente': presidente_activo_existe})


def register_presidente(request):
    """
    Registro de Presidente:
    - Crea PendingPresidentRegistration en BD (token UUID del modelo).
    - Envía correo con /confirmar-presidente/<uuid:token>/
    """
    # Si ya hay un pending en sesión, mostrar la pantalla de verificación
    if request.session.get('pending_president_token') and request.session.get('pending_email'):
        return render(request, 'taxis/verification_pending.html', {
            'pending_email': request.session.get('pending_email')
        })

    if request.method == 'POST':
        form = PresidenteRegisterForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            # 1) No permitir presidente activo
            if CustomUser.objects.filter(role='presidente', is_active=True).exists():
                messages.error(request, 'Ya existe un presidente activo.')
                return render(request, 'registration/register_presidente.html', {'form': form})

            # 2) No email duplicado
            if CustomUser.objects.filter(email__iexact=cd['email']).exists():
                messages.error(request, 'Email ya registrado.')
                return render(request, 'registration/register_presidente.html', {'form': form})
            
            phone_number = (cd.get("phone_number") or "").strip()
            phone_country = (cd.get("phone_country") or "").strip()

            if not phone_number:
                messages.error(request, "El número de teléfono es obligatorio.")
                return render(request, 'registration/register_presidente.html', {'form': form})

            # 3) Crear registro pendiente en BD (token UUIDField del modelo)
            pending = PendingPresidentRegistration.objects.create(
                username=cd['username'],
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                email=cd['email'],
                phone_country=cd.get('phone_country', ''),
                phone_number=cd['phone_number'],
                fecha_nacimiento=cd['fecha_nacimiento'],
                sexo=cd['sexo'],
                password_hash=make_password(cd['password1']),
                expires_at=timezone.now() + timedelta(hours=24),
            )

            # Guardar datos mínimos en sesión para: pantalla "pendiente", reenviar, cancelar
            request.session['pending_email'] = pending.email
            request.session['pending_president_token'] = str(pending.token)
            request.session.modified = True

            # Enviar correo inicial
            send_president_activation_email_initial(request, pending.email, pending.token)

            messages.success(request, f'¡Registrado! Revisa {pending.email}')
            return render(request, 'taxis/verification_pending.html', {'pending_email': pending.email})

        # Form inválido
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
        return render(request, 'registration/register_presidente.html', {'form': form})

    # GET
    form = PresidenteRegisterForm()
    return render(request, 'registration/register_presidente.html', {'form': form})


@require_POST
@csrf_protect
def cancel_registration(request):
    """Cancelar registro pendiente (borra pending en BD si existe) y limpiar sesión."""
    try:
        token = request.session.get('pending_president_token')

        if token:
            PendingPresidentRegistration.objects.filter(token=token).delete()

        request.session.pop('pending_president_token', None)
        request.session.pop('pending_email', None)
        request.session.modified = True

        return JsonResponse({
            'message': 'Registro cancelado. Redirigiendo...',
            'success': True
        }, status=200)

    except Exception as e:
        print(f"❌ ERROR CANCELANDO REGISTRO: {str(e)}")
        return JsonResponse({
            'error': 'Error al cancelar registro.',
            'success': False
        }, status=500)


def confirm_president_registration(request, token):
    """
    Confirma token (UUID) → valida expiración → crea usuario → login → activation_success
    NOTA: Esta vista debe estar en urls.py como: <uuid:token>
    """
    pending = get_object_or_404(PendingPresidentRegistration, token=token)

    # Expirado
    if timezone.now() > pending.expires_at:
        pending.delete()
        messages.error(request, 'Token expirado. Regístrate de nuevo.')
        return redirect('taxis:register_presidente')

    # Presidente ya existe
    if CustomUser.objects.filter(role='presidente', is_active=True).exists():
        pending.delete()
        messages.error(request, 'Ya existe presidente activo.')
        return redirect('taxis:login')

    # Seguridad: evitar colisiones por email
    if CustomUser.objects.filter(email__iexact=pending.email).exists():
        pending.delete()
        messages.error(request, 'Email ya registrado.')
        return redirect('taxis:register_presidente')

    # Validación teléfono (misma lógica que venías usando)
    phone_raw = (pending.phone_number or '').strip()
    if not phone_raw:
        pending.delete()
        messages.error(request, "Tu registro no tiene teléfono. Regístrate de nuevo.")
        return redirect('taxis:register_presidente')

    telefono_limpio = ''.join(filter(str.isdigit, phone_raw))
    telefono_comparar = telefono_limpio[-10:] if len(telefono_limpio) >= 10 else telefono_limpio

    for u in CustomUser.objects.all():
        tlf_user = getattr(u, 'phone_number', '')
        if tlf_user:
            db_limpio = ''.join(filter(str.isdigit, str(tlf_user)))
            db_comparar = db_limpio[-10:] if len(db_limpio) >= 10 else db_limpio
            if db_comparar == telefono_comparar:
                messages.error(request, 'Teléfono ya registrado.')
                return redirect('taxis:register_presidente')

    for conductor in Conductor.objects.all():
        if conductor.telefono_principal:
            db_limpio = ''.join(filter(str.isdigit, conductor.telefono_principal))
            db_comparar = db_limpio[-10:] if len(db_limpio) >= 10 else db_limpio
            if db_comparar == telefono_comparar:
                messages.error(request, 'Teléfono usado por conductor.')
                return redirect('taxis:register_presidente')

    # Crear usuario FINAL (usa el hash guardado en pending.password_hash)
    user = CustomUser.objects.create(
        username=pending.username,
        first_name=pending.first_name,
        last_name=pending.last_name,
        email=pending.email,
        phone_country=pending.phone_country,
        phone_number=pending.phone_number,
        fecha_nacimiento=pending.fecha_nacimiento,
        sexo=pending.sexo,
        role='presidente',
        is_active=True,
        is_email_verified=True
    )
    user.password = pending.password_hash
    user.save()

    pending.delete()

    request.session.pop('pending_president_token', None)
    request.session.pop('pending_email', None)

    login(request, user)
    messages.success(request, f'¡Bienvenido {user.first_name}!')
    return redirect('taxis:activation_success')


def send_president_activation_email_initial(request, email, token):
    """Envío inicial (token UUID)."""
    url = request.build_absolute_uri(
        reverse('taxis:confirm_president_registration', kwargs={'token': str(token)})
    )

    mensaje_html = format_html("""
        <div style="font-family: Nunito, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #00b300;">¡Activa tu cuenta de Presidente!</h2>
            <p>Haz clic para confirmar:</p>
            <a href="{}" style="display: inline-block; background: #00b300; color: white;
                padding: 15px 30px; text-decoration: none; border-radius: 50px;
                font-weight: 800; font-size: 16px;">Confirmar Cuenta</a>
            <p style="margin-top: 20px; font-size: 14px; color: #666;">
                Expira en 24h. Ignora si no solicitaste.
            </p>
        </div>
    """, url)

    send_mail(
        'Confirma cuenta Presidente - WILSON TORRES 33',
        f'Activa aquí: {url}',
        settings.DEFAULT_FROM_EMAIL or 'no-reply@cooperativa.com',
        [email],
        html_message=mensaje_html,
        fail_silently=False,
    )
    print(f"✅ CORREO INICIAL ENVIADO A: {email}")


def send_president_activation_email(request, email, token):
    """Envío para reenvío (token UUID)."""
    url = request.build_absolute_uri(
        reverse('taxis:confirm_president_registration', kwargs={'token': str(token)})
    )

    mensaje_html = format_html("""
        <div style="font-family: Nunito, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #00b300;">¡Activa tu cuenta de Presidente!</h2>
            <p>Haz clic para confirmar:</p>
            <a href="{}" style="display: inline-block; background: #00b300; color: white;
                padding: 15px 30px; text-decoration: none; border-radius: 50px;
                font-weight: 800; font-size: 16px;">Confirmar Cuenta</a>
            <p style="margin-top: 20px; font-size: 14px; color: #666;">
                Expira en 24h. Ignora si no solicitaste.
            </p>
        </div>
    """, url)

    send_mail(
        'Confirma cuenta Presidente - WILSON TORRES 33',
        f'Activa aquí: {url}',
        settings.DEFAULT_FROM_EMAIL or 'no-reply@cooperativa.com',
        [email],
        html_message=mensaje_html,
        fail_silently=False,
    )
    print(f"✅ CORREO REENVIADO A: {email}")


@require_POST
@csrf_protect
def activation_resend(request):
    """
    Reenvío con límite (cache):
    - Máximo 3 reenvíos
    - Bloqueo 30 min si se agotan
    El token sale de BD (PendingPresidentRegistration), no de sesión.
    """
    email = (request.session.get('pending_email') or '').strip()
    if not email:
        return JsonResponse({'error': 'Sesión expirada. Por favor, regístrate de nuevo.'}, status=400)

    pending = (PendingPresidentRegistration.objects
               .filter(email__iexact=email)
               .order_by('-created_at')
               .first())

    if not pending:
        return JsonResponse({'error': 'No hay registro pendiente.'}, status=404)

    if timezone.now() > pending.expires_at:
        pending.delete()
        request.session.pop('pending_president_token', None)
        request.session.pop('pending_email', None)
        return JsonResponse({'error': 'Token expirado. Por favor, regístrate de nuevo.'}, status=410)

    cache_key_count = f"activation_resend_count_{email.lower()}"
    cache_key_locked = f"activation_resend_locked_{email.lower()}"

    locked_until = cache.get(cache_key_locked)
    if locked_until:
        remaining_seconds = int((locked_until - timezone.now()).total_seconds())
        if remaining_seconds > 0:
            return JsonResponse({
                'locked': True,
                'retry_after': remaining_seconds,
                'error': f'Demasiados intentos. Intenta en {remaining_seconds // 60}:{remaining_seconds % 60:02d}.'
            }, status=429)
        cache.delete(cache_key_locked)
        cache.delete(cache_key_count)

    resend_count = cache.get(cache_key_count, 0)
    if resend_count >= 3:
        locked_until = timezone.now() + timedelta(minutes=30)
        cache.set(cache_key_locked, locked_until, 1800)
        return JsonResponse({
            'locked': True,
            'retry_after': 1800,
            'error': 'Demasiados intentos. Intenta en 30 minutos.'
        }, status=429)

    try:
        send_president_activation_email(request, pending.email, pending.token)
        cache.set(cache_key_count, resend_count + 1, 86400)  # contador dura 24h

        remaining = max(0, 3 - resend_count - 1)
        return JsonResponse({'message': 'Correo reenviado correctamente.', 'remaining': remaining}, status=200)

    except Exception as e:
        print(f"❌ ERROR ENVIANDO CORREO: {str(e)}")
        return JsonResponse({'error': 'No se pudo enviar el correo. Intenta más tarde.'}, status=500)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class VerificationPendingView(TemplateView):
    template_name = 'taxis/verification_pending.html'


class ActivationSuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'taxis/activation_success.html'
    login_url = 'taxis:login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'presidente':
            messages.error(request, 'Acceso denegado.')
            return redirect('taxis:login')
        return super().dispatch(request, *args, **kwargs)

    # ====================================================================
# AUTENTICACIÓN - LOGOUT CON AUDITORÍA
# ====================================================================

def logout_view(request):
    """
    Cierra sesión del usuario y registra en auditoría.
    Llamada por: /logout/
    """
    from django.contrib.auth import logout
    from django.contrib import messages
    from taxis.utils import log_logout
    
    # Registrar logout ANTES de cerrar sesión
    log_logout(request)
    
    # Cerrar sesión oficial
    logout(request)
    
    # Mensaje de confirmación
    messages.success(request, '✅ Sesión cerrada correctamente.')
    
    # Redirigir a login
    return redirect('taxis:login')

MAX_RESENDS = 3
LOCK_SECONDS = 60 * 30  # 30 minutos

def _pwreset_count_key(email: str) -> str:
    return f"pwreset:count:{email.lower()}"

def _pwreset_lock_key(email: str) -> str:
    return f"pwreset:lock:{email.lower()}"

@require_POST
@csrf_protect
def password_reset_resend(request):
    """
    Reenviar correo de reset de contraseña con límite de 3 intentos.
    Usa CACHE para persistencia (igual que con email de verificación)
    """
    from django.core.cache import cache
    import time
    
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"ok": False, "error": "email_required"}, status=400)

    now = int(time.time())

    # ⭐ CONSTANTES
    MAX_RESENDS = 3
    LOCK_SECONDS = 60 * 30  # 30 minutos
    
    # ⭐ CLAVES CACHE
    count_key = f"pwreset:count:{email}"
    lock_key = f"pwreset:lock:{email}"

    # 1) ¿Está bloqueado?
    locked_until = cache.get(lock_key)
    if locked_until:
        remaining = int(locked_until - time.time())
        if remaining > 0:
            return JsonResponse({
                "ok": False,
                "locked": True,
                "retry_after": remaining,
                "error": f"Demasiados intentos. Intenta en {remaining // 60}:{remaining % 60:02d}."
            }, status=429)
        else:
            # Ya pasó el bloqueo, limpiar
            cache.delete(lock_key)
            cache.delete(count_key)

    # 2) ¿Cuántos reenvíos lleva?
    count = cache.get(count_key, 0)
    if count >= MAX_RESENDS:
        # Bloquear por 30 minutos
        locked_until_time = time.time() + LOCK_SECONDS
        cache.set(lock_key, locked_until_time, timeout=LOCK_SECONDS)
        return JsonResponse({
            "ok": False,
            "locked": True,
            "retry_after": LOCK_SECONDS,
            "error": "Demasiados intentos. Intenta en 30 minutos."
        }, status=429)

    # 3) Reenviar correo (Django password reset estándar)
    form = PasswordResetForm({"email": email})
    if form.is_valid():
        form.save(request=request)
    else:
        return JsonResponse({
            "ok": False,
            "error": "Email no válido o no registrado."
        }, status=400)

    # 4) Incrementar contador en CACHE (persiste 30 minutos)
    new_count = count + 1
    cache.set(count_key, new_count, timeout=LOCK_SECONDS)

    remaining = MAX_RESENDS - new_count
    
    return JsonResponse({
        "ok": True,
        "sent": True,
        "remaining": remaining,
        "message": f"Correo reenviado. Te quedan {remaining} intentos."
    }, status=200)
