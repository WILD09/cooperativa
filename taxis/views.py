import random
import os  # Necesario para rutas de archivos
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import timedelta, date
from io import BytesIO


from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import send_mail
from django.contrib.auth import logout, login
from django.template.loader import get_template


# xhtml2pdf para PDFs
from xhtml2pdf import pisa


# Tokens y Encoders
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site


# FORMULARIOS
from .forms import (
    ConductorForm, VehiculoForm, PresidenteRegisterForm,
    EmailOrUsernameAuthenticationForm, PagoForm, UbicacionGeograficaForm
)


# MODELOS
from .models import (
    Conductor, Vehiculo, CustomUser, UbicacionGeografica, Parroquia,
    Deuda, Pago, MovimientoAudit, Notificacion, ConfiguracionCooperativa,
    ConfiguracionGlobal, DocumentoLegal, EmailVerificationCode, Municipio
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


# ====================================================================
# CONFIGURACIÓN Y SISTEMA (AJAX)
# ====================================================================


def load_parroquias(request):
    """Vista AJAX para cargar parroquias dinámicamente."""
    municipio_id = request.GET.get('municipio')
    data = []
    if municipio_id:
        parroquias = Parroquia.objects.filter(municipio_id=municipio_id).order_by('nombre')
        data = list(parroquias.values('id', 'nombre'))
    return JsonResponse(data, safe=False)


def check_duplicado(request):
    """Vista AJAX para validar unicidad (Conductores/Usuarios)."""
    campo = request.GET.get('campo')
    valor = request.GET.get('valor')
    exclude_id = request.GET.get('exclude_id')


    if not valor:
        return JsonResponse({'existe': False})


    valor = valor.strip()
    existe = False


    qs_cond = Conductor.objects.all()
    if exclude_id and exclude_id not in ['None', '']:
        qs_cond = qs_cond.exclude(pk=exclude_id)


    qs_users = CustomUser.objects.all()


    if campo == 'cedula':
        existe = qs_cond.filter(cedula_identidad=valor).exists()


    elif campo == 'rif':
        existe = qs_cond.filter(rif=valor).exists()


    elif campo == 'email':
        existe_cond = qs_cond.filter(email__iexact=valor).exists()
        existe_user = qs_users.filter(email__iexact=valor).exists()
        existe = existe_cond or existe_user


    elif campo == 'telefono':
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


        # B. Revisar en Usuarios
        if not existe:
            for u in qs_users:
                tlf_user = getattr(u, 'phone_number', getattr(u, 'telefono', ''))
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
    campo = request.GET.get('campo') # 'placa', 'serial_niv', 'numero_casco'
    valor = request.GET.get('valor', '').strip().upper()
    exclude_id = request.GET.get('exclude_id') # ID del vehículo si se está editando


    if not campo or not valor:
        return JsonResponse({'existe': False})


    existe = False
    mensaje = ""
    qs = Vehiculo.objects.all()
    
    # Si estamos editando, excluimos el vehículo actual de la búsqueda
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
def guardar_configuracion(request):
    if request.user.role != 'presidente':
        messages.error(request, "Acceso no autorizado.")
        return redirect('taxis:panel_general')


    if request.method == 'POST':
        nueva_tasa = request.POST.get('tasa_bcv')
        try:
            config, _ = ConfiguracionGlobal.objects.get_or_create(id=1)
            config.tasa_bcv = float(nueva_tasa)
            config.save()
            messages.success(request, f"Tasa BCV actualizada a {nueva_tasa} Bs.")
            MovimientoAudit.objects.create(
                usuario=request.user,
                accion=f"Actualizó Tasa BCV a {nueva_tasa}",
                modulo="Finanzas"
            )
        except ValueError:
            messages.error(request, "Valor de tasa inválido.")
    return redirect('taxis:panel_general')


@login_required
def ejecutar_cierre_mensual(request):
    if request.user.role != 'presidente':
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
        # ORDENAR POR ID (Orden de llegada: 1, 2, 3...)
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
            qs = qs.filter(estado_civil=edo_civil)


        return qs


class ConductorDetailView(LoginRequiredMixin, DetailView):
    model = Conductor
    template_name = "taxis/conductor_detail.html"
    context_object_name = "conductor"


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
        # ORDENAR POR ID (Orden de llegada: 1, 2, 3...)
        qs = Vehiculo.objects.select_related('conductor').order_by('id')


        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(numero_casco__icontains=q) |             # <--- NUEVO: Buscar por Casco
                Q(placa__icontains=q) |
                Q(marca__icontains=q) |
                Q(modelo__icontains=q) |
                Q(conductor__nombres__icontains=q) |
                Q(conductor__apellidos__icontains=q) |
                Q(conductor__cedula_identidad__icontains=q) # <--- NUEVO: Buscar por Cédula del chofer
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


# --- CREACIÓN DE VEHÍCULO ---
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
        
        # FORZAMOS LA REDIRECCIÓN EXPLÍCITA
        return HttpResponseRedirect(self.success_url)


class VehiculoUpdateView(LoginRequiredMixin, UpdateView):
    model = Vehiculo
    form_class = VehiculoForm
    template_name = "taxis/vehiculo_form.html"


    def get_success_url(self):
        # Redirige al perfil del vehículo que acabas de editar
        return reverse_lazy("taxis:vehiculo_detail", kwargs={'pk': self.object.pk})


    def form_valid(self, form):
        self.object = form.save()
        
        MovimientoAudit.objects.create(
            usuario=self.request.user,
            accion=f"Vehículo actualizado: {self.object.placa}",
            modulo="Vehículos"
        )
        messages.success(self.request, "Vehículo actualizado exitosamente.")
        
        # Usa get_success_url() para obtener la URL correcta
        return HttpResponseRedirect(self.get_success_url())



class VehiculoDeleteView(LoginRequiredMixin, DeleteView):
    model = Vehiculo
    template_name = "taxis/vehiculo_confirm_delete.html"
    success_url = reverse_lazy("taxis:vehiculo_list")


# ====================================================================
# FINANZAS
# ====================================================================


class DeudaListView(LoginRequiredMixin, ListView):
    model = Deuda
    template_name = "taxis/deuda_list.html"
    context_object_name = "deudas"
    paginate_by = 20
    ordering = ['-anio', '-mes']


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = "taxis/pago_list.html"
    context_object_name = "pagos"
    ordering = ['-fecha_pago']


class RegistrarPagoView(LoginRequiredMixin, CreateView):
    model = Pago
    form_class = PagoForm
    template_name = "taxis/pago_form.html"
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


        Notificacion.objects.create(
            titulo="Pago Recibido",
            mensaje=f"Se registró pago de {self.deuda.conductor.nombres}",
            leida=False
        )
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
# REPORTES (PDF y EXCEL)
# ====================================================================


def obtener_conductores_filtrados(request):
    # Se ordena por apellidos en reportes para facilitar búsqueda visual
    qs = Conductor.objects.all().order_by('apellidos')
    q = request.GET.get('q')
    if q:
        qs = qs.filter(Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(cedula_identidad__icontains=q))
    genero = request.GET.get('genero')
    if genero:
        qs = qs.filter(sexo=genero)
    edo_civil = request.GET.get('edo_civil')
    if edo_civil:
        qs = qs.filter(estado_civil=edo_civil)
    return qs


@login_required
def reporte_afiliados_pdf(request):
    conductores = obtener_conductores_filtrados(request)


    # Rutas absolutas para imágenes
    logo_transporte = os.path.join(settings.STATIC_ROOT, 'img', 'logo_transporte.png')
    logo_mision = os.path.join(settings.STATIC_ROOT, 'img', 'logo_gran_mision.png')


    # Fallback en desarrollo
    if settings.DEBUG:
        logo_transporte = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_transporte.png')
        logo_mision = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_gran_mision.png')


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
        fecha_nac = c.fecha_nacimiento.strftime('%d/%m/%Y') if c.fecha_nacimiento else "-"
        cedula_full = f"{c.cedula_prefijo}-{c.cedula_identidad}"
        rif_full = f"{c.rif_prefijo}-{c.rif}"


        row = [
            i, c.nombres, c.apellidos, fecha_nac,
            c.get_sexo_display(), c.get_estado_civil_display(),
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
    return response


# ====================================================================
# REPORTES VEHÍCULOS (PDF y EXCEL)
# ====================================================================

def obtener_vehiculos_filtrados(request):
    """Filtra vehículos por estado (operativo/inoperativo) y búsqueda."""
    qs = Vehiculo.objects.select_related('conductor').order_by('numero_casco')
    
    # Filtro por búsqueda: CASCO, CHOFER, PLACA, CÉDULA
    q = request.GET.get('q')
    if q:
        qs = qs.filter(
            Q(numero_casco__icontains=q) |                      # Número de casco
            Q(placa__icontains=q) |                             # Placa
            Q(conductor__nombres__icontains=q) |                # Nombre del chofer
            Q(conductor__apellidos__icontains=q) |              # Apellido del chofer
            Q(conductor__cedula_identidad__icontains=q)         # Cédula del chofer
        )
    
    # Filtro por estado (operativo/inoperativo)
    estado = request.GET.get('estado')
    if estado in ['operativo', 'inoperativo']:
        qs = qs.filter(condicion=estado)
    
    return qs


@login_required
def reporte_vehiculos_pdf(request):
    """Genera reporte PDF de vehículos con filtros activos."""
    vehiculos = obtener_vehiculos_filtrados(request)

    # Rutas absolutas para imágenes
    logo_transporte = os.path.join(settings.STATIC_ROOT, 'img', 'logo_transporte.png')
    logo_mision = os.path.join(settings.STATIC_ROOT, 'img', 'logo_gran_mision.png')

    # Fallback en desarrollo
    if settings.DEBUG:
        logo_transporte = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_transporte.png')
        logo_mision = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_gran_mision.png')

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
        return response

    return HttpResponse("Error generando PDF", status=500)


@login_required
def reporte_vehiculos_excel(request):
    """Genera reporte Excel de vehículos con filtros activos."""
    vehiculos = obtener_vehiculos_filtrados(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Flota Vehicular"

    # TÍTULO
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

    # ENCABEZADOS
    headers = ["N°", "AFILIADO", "CÉDULA", "MARCA", "MODELO", "AÑO", "COLOR", "PLACA", "SERIAL NIV", "CAPACIDAD"]
    ws.append([])
    ws.append(headers)

    header_fill = PatternFill(start_color="CC0000", end_color="CC0000", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for cell in ws[3]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    # DATOS
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

    # AJUSTAR ANCHOS
    dims = {
        'A': 5,   # N°
        'B': 25,  # Afiliado
        'C': 12,  # Cédula
        'D': 12,  # Marca
        'E': 12,  # Modelo
        'F': 6,   # Año
        'G': 10,  # Color
        'H': 12,  # Placa
        'I': 20,  # Serial
        'J': 10   # Capacidad
    }
    for col, width in dims.items():
        ws.column_dimensions[col].width = width

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Vehiculos_Flota_{timezone.now().strftime('%d-%m-%Y')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response


class ReporteFichaPDF(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        conductor = get_object_or_404(Conductor, pk=pk)
        data = {
            'conductor': conductor,
            'vehiculos': conductor.vehiculos.all(),
            'hoy': date.today(),
            'config': ConfiguracionCooperativa.objects.first(),
        }
        return render_to_pdf('taxis/reportes/ficha_afiliado.html', data)


# ====================================================================
# AUDITORÍA Y NOTIFICACIONES
# ====================================================================


class MovimientoAuditListView(LoginRequiredMixin, ListView):
    model = MovimientoAudit
    template_name = "taxis/audit_list.html"
    context_object_name = "movimientos"
    paginate_by = 30
    ordering = ['-fecha']


class NotificacionListView(LoginRequiredMixin, ListView):
    model = Notificacion
    template_name = "taxis/notificacion_list.html"
    context_object_name = "notificaciones"
    ordering = ['-fecha']


@login_required
def panel_general(request):
    hoy = date.today()
    limite = hoy + timedelta(days=15)
    context = {
        'total_afiliados': Conductor.objects.count(),
        'total_vehiculos': Vehiculo.objects.count(),
        'pagos_pendientes': Deuda.objects.filter(pagada=False).count(),
        'notificaciones': Notificacion.objects.filter(leida=False),
        'alertas': Vehiculo.objects.filter(Q(patente_vencimiento__lte=limite) | Q(licencia_vencimiento__lte=limite))[:5],
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
    if request.user.is_authenticated:
        logout(request)


    if CustomUser.objects.filter(role='presidente', is_active=True).exists():
        messages.error(request, "Ya existe un presidente registrado y activo.")
        return redirect('taxis:login')


    if request.method == 'POST':
        form = PresidenteRegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            CustomUser.objects.filter(role='presidente', is_active=False).delete()
            CustomUser.objects.filter(email=email, is_active=False).delete()


            user = form.save(commit=False)
            user.role = 'presidente'
            user.is_active = False
            user.save()


            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))


            current_site = get_current_site(request)
            domain = current_site.domain
            protocol = 'https' if request.is_secure() else 'http'
            activation_link = f"{protocol}://{domain}{reverse('taxis:activate_account', kwargs={'uidb64': uid, 'token': token})}"


            subject = 'Activación de Cuenta - Cooperativa de Transporte'
            message = f"Hola {user.first_name}. Activa tu cuenta aquí: {activation_link}"


            try:
                send_mail(subject, message, 'sistema@cooperativa.com', [user.email], fail_silently=False)
                return redirect('taxis:verification_pending')


            except Exception:
                messages.error(request, "Error enviando el correo. Intente nuevamente.")
                user.delete()
                return redirect('taxis:register_presidente')
    else:
        form = PresidenteRegisterForm()


    return render(request, 'taxis/register_presidente.html', {'form': form})


class VerificationPendingView(TemplateView):
    template_name = 'taxis/verification_pending.html'


class ActivateAccountView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            user = None


        if user is not None and default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            return redirect('taxis:activation_success')
        else:
            messages.error(request, "El enlace de activación no es válido o ya fue usado.")
            return redirect('taxis:login')


class ActivationSuccessView(TemplateView):
    template_name = 'taxis/activation_success.html'
