"""
views.py
Vistas de la aplicación 'taxis':
- CRUD de Conductores y Taxis
- Flujo de registro y verificación por correo
- Dashboards según rol
- Restablecimiento de contraseña por correo
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.db import transaction, models
from django.db.models import Prefetch, Count, F, Q
from django.core.exceptions import MultipleObjectsReturned
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.core.paginator import Paginator
from django.contrib.auth.views import LoginView
from django.http import JsonResponse, HttpResponseForbidden
from datetime import timedelta, date, datetime

from .forms import (                                        # Formularios de la app.
    ConductorForm,
    TaxiForm,
    PresidenteRegisterForm,
    VerificationCodeForm,
    EmailOrUsernameAuthenticationForm,
    PasswordResetRequestForm,
)
from .utils import (
    create_email_verification_code, 
    send_verification_email,
    can_resend_email_code,
)
from .login_attempts import (
    is_locked_out,
    record_failed_attempt,
    clear_attempts,
    get_remaining_attempts,
)
from .models import (                                       # Modelos usados en las vistas.
    Conductor,
    Taxi,
    CustomUser,
    EmailVerificationCode,
    UbicacionGeografica,
)
from .utils import (                                        # Funciones de utilidades (solo email).
    create_email_verification_code,
    send_verification_email,
    verify_email_code,
    mark_email_code_as_used,
    can_resend_email_code,
    register_email_resend,
    MAX_DAILY_RESENDS,
)

# -------------------------------------------------------------------
# CRUD CONDUCTORES / TAXIS
# -------------------------------------------------------------------


class ConductorListView(ListView):
    """Lista todos los conductores registrados."""
    model = Conductor
    template_name = "taxis/conductor_list.html"
    context_object_name = "conductores"


class ConductorDetailView(DetailView):
    """Muestra el detalle de un conductor específico."""
    model = Conductor
    template_name = "taxis/conductor_detail.html"
    context_object_name = "conductor"


class TaxiListView(ListView):
    """Lista todos los taxis registrados."""
    model = Taxi
    template_name = "taxis/taxi_list.html"
    context_object_name = "taxis"


class TaxiDetailView(DetailView):
    """Muestra el detalle de un taxi específico."""
    model = Taxi
    template_name = "taxis/taxi_detail.html"
    context_object_name = "taxi"


class ConductorCreateView(CreateView):
    """Crea un nuevo conductor usando ConductorForm."""
    model = Conductor
    form_class = ConductorForm
    template_name = "taxis/conductor_form.html"
    success_url = reverse_lazy("taxis:conductor-list")


class ConductorUpdateView(UpdateView):
    """Edita un conductor existente."""
    model = Conductor
    form_class = ConductorForm
    template_name = "taxis/conductor_form.html"
    success_url = reverse_lazy("taxis:conductor-list")


class ConductorDeleteView(DeleteView):
    """Elimina un conductor."""
    model = Conductor
    template_name = "taxis/conductor_confirm_delete.html"
    success_url = reverse_lazy("taxis:conductor-list")


class TaxiCreateView(CreateView):
    """Crea un nuevo taxi."""
    model = Taxi
    form_class = TaxiForm
    template_name = "taxis/taxi_form.html"
    success_url = reverse_lazy("taxis:taxi-list")


class TaxiUpdateView(UpdateView):
    """Edita un taxi existente."""
    model = Taxi
    form_class = TaxiForm
    template_name = "taxis/taxi_form.html"
    success_url = reverse_lazy("taxis:taxi-list")


class TaxiDeleteView(DeleteView):
    """Elimina un taxi."""
    model = Taxi
    template_name = "taxis/taxi_confirm_delete.html"
    success_url = reverse_lazy("taxis:taxi-list")


# -------------------------------------------------------------------
# AUTH / LOGIN CUSTOMIZADO
# -------------------------------------------------------------------

class CustomLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailOrUsernameAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        
        # Verificar bloqueo antes de procesar el POST
        if request.method == "POST":
            username = request.POST.get("username", "").strip()
            locked, until = is_locked_out(username)
            if locked:
                wait_time = int((until - datetime.now()).total_seconds() / 60)
                if wait_time < 0: wait_time = 0
                messages.error(
                    request,
                    f"Tu cuenta ha sido bloqueada temporalmente por demasiados intentos fallidos. "
                    f"Vuelve a intentarlo en {wait_time} minutos o contacta a soporte."
                )
                return self.render_to_response(self.get_context_data())
                
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Limpiar intentos al tener éxito
        username = form.cleaned_data.get("username")
        clear_attempts(username)
        return super().form_valid(form)

    def form_invalid(self, form):
        # Registrar intento fallido
        username = form.data.get("username", "").strip()
        if username:
            locked = record_failed_attempt(username)
            if locked:
                messages.error(
                    self.request,
                    "Has alcanzado el máximo de intentos permitidos. Tu cuenta ha sido bloqueada por 24 horas."
                )
            else:
                remaining = get_remaining_attempts(username)
                messages.warning(
                    self.request,
                    f"Usuario o contraseña incorrectos. Te quedan {remaining} intentos antes de bloquear la cuenta."
                )
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy("taxis:login-redirect")


# -------------------------------------------------------------------
# FLUJO REGISTRO / VERIFICACIÓN POR CORREO
# -------------------------------------------------------------------


def select_role(request):
    """
    Vista para registro de Presidente.
    La tarjeta se deshabilita si ya existe un superusuario verificado.
    """
    # Verificar si existe presidente verificado
    presidente_existente = CustomUser.objects.filter(
        role='presidente',
        is_email_verified=True,
        is_superuser=True
    ).exists()
    
    if request.method == 'POST':
        role = request.POST.get('role', 'presidente')
        
        # Solo aceptar rol de presidente
        if role != 'presidente':
            messages.error(request, "Rol no válido.")
            return redirect('taxis:select_role')
        
        # Bloquear registro de presidente si ya existe
        if presidente_existente:
            messages.error(request, "Ya existe un administrador registrado en el sistema.")
            return redirect('taxis:select_role')
        
        return redirect(f"{reverse('taxis:register')}?role=presidente")
    
    return render(request, 'taxis/select_role.html', {
        'presidente_existente': presidente_existente
    })



def register_presidente(request):
    """
    Maneja el registro del PRESIDENTE de la cooperativa.
    Bloquea el acceso si ya existe un presidente verificado.
    Si entra por POST, crea el usuario y envía código de verificación.
    """
    # 1. Verificar si ya existe un Presidente verificado (Single-Tenant)
    presidente_existente = CustomUser.objects.filter(
        role='presidente',
        is_email_verified=True,
        is_superuser=True
    ).exists()

    if presidente_existente:
        messages.error(request, "El registro de administrador ya no está disponible.")
        return redirect('login')

    # 2. Solo permitimos rol 'presidente'
    role = request.GET.get('role', 'presidente')
    if role != 'presidente':
        return redirect('taxis:select_role')

    if request.method == 'POST':
        form = PresidenteRegisterForm(request.POST)
        if form.is_valid():
            # Crear usuario transaccional
            user = form.save(commit=False)
            user.role = 'presidente'
            user.is_superuser = True
            user.is_staff = True
            user.is_active = False  # Inactivo hasta verificar correo
            user.save()

            # Generar código y enviar correo
            code = create_email_verification_code(
                user, email_type="primary", validity_minutes=15
            )
            # Intentar envío de correo (simplificado, asume éxito o logs en utils)
            send_verification_email(user, code, email_type="primary")
            
            messages.success(
                request, 
                f"Cuenta creada. Se ha enviado un código de verificación a {user.email}"
            )
            return redirect('taxis:verify_email', user_id=user.pk)
        else:
            messages.error(request, "Por favor corrige los errores indicados.")
    else:
        form = PresidenteRegisterForm()

    return render(request, 'taxis/register_presidente.html', {
        'form': form,
        'role': 'presidente'
    })



def verify_email_view(request, user_id):
    """
    Vista para verificar el correo electrónico de un usuario.
    """
    user = get_object_or_404(CustomUser, pk=user_id)
    form = VerificationCodeForm(request.POST or None)

    cooldown_seconds = 0
    last_code = (
        EmailVerificationCode.objects.filter(
            user=user,
            email_type="primary",
            is_used=False,
        )
        .order_by("-created_at")
        .first()
    )
    if last_code:
        cooldown_total = 60
        elapsed = (timezone.now() - last_code.created_at).total_seconds()
        remaining = int(cooldown_total - elapsed)
        if remaining > 0:
            cooldown_seconds = remaining

    puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
        user, email_type="primary"
    )

    if request.method == "POST":
        if "resend_code" in request.POST:
            form = VerificationCodeForm()
            if not puede_env:
                messages.error(request, error_msg)
            else:
                code = create_email_verification_code(
                    user, email_type="primary", validity_minutes=15
                )
                send_verification_email(user, code, email_type="primary")
                register_email_resend(user, email_type="primary")
                messages.info(
                    request,
                    "Se ha reenviado un nuevo código a tu correo.",
                )
                cooldown_seconds = 60
                puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
                    user, email_type="primary"
                )
        else:
            form = VerificationCodeForm(request.POST)
            if form.is_valid():
                code = form.cleaned_data["code"]
                if code:
                    code_obj = verify_email_code(user, code, email_type="primary")
                    if code_obj:
                        mark_email_code_as_used(code_obj)
                        user.is_email_verified = True
                        if not user.is_active:
                            user.is_active = True
                        user.save()
                        return redirect("taxis:verification_success")
                    else:
                        form.add_error(
                            "code",
                            "El código ingresado es incorrecto, ha expirado "
                            "o se alcanzó el número máximo de intentos.",
                        )

    context = {
        "user": user,
        "form": form,
        "cooldown_seconds": cooldown_seconds,
        "email_used_today": used_today,
        "email_max_per_day": max_per_day,
    }
    return render(request, "taxis/verification_email.html", context)


def verification_success_view(request):
    """
    Vista que muestra una página de éxito tras verificar el correo.
    """
    return render(request, "taxis/verification_success.html")


# -------------------------------------------------------------------
# OTRAS VISTAS (INDEX, DASHBOARDS, REDIRECCIÓN)
# -------------------------------------------------------------------


def index(request):
    """Página de inicio de la app 'taxis'."""
    return render(request, "taxis/index.html")


@login_required
def panel_general(request):
    """
    Panel General - Dashboard administrativo principal para el Presidente.
    Muestra resumen de métricas, alertas críticas y accesos rápidos.
    """
    # Verificar que sea presidente
    if request.user.role != 'presidente':
        messages.error(request, "No tienes permisos para acceder al Panel General.")
        return redirect('taxis:login-redirect')
    
    from datetime import date
    
    # Contadores dinámicos
    total_afiliados = Conductor.objects.count()
    total_vehiculos = Taxi.objects.count()
    pagos_pendientes = Conductor.objects.filter(pago_patente_realizado=False).count()
    notificaciones_count = 0  # Placeholder para sistema futuro
    
    # Alertas críticas (vencimiento de documentos en próximos 15 días)
    # Solo mostrar si realmente hay un problema (pago_patente_realizado=False o fecha vencida)
    hoy = date.today()
    fecha_limite = hoy + timedelta(days=15)
    
    alertas = Conductor.objects.filter(
        fecha_pago_patente__isnull=False,
        fecha_pago_patente__lte=fecha_limite
    ).select_related('user').order_by('fecha_pago_patente')
    
    # Filtrar solo los que NO han realizado el pago o cuya fecha es <= hoy
    # (Ya que si lo hicieron, la alerta debería desaparecer según el plan)
    alertas_activas = []
    for conductor in alertas:
        if not conductor.pago_patente_realizado or conductor.fecha_pago_patente <= hoy:
            alertas_activas.append(conductor)
    
    context = {
        'total_afiliados': total_afiliados,
        'total_vehiculos': total_vehiculos,
        'pagos_pendientes': pagos_pendientes,
        'notificaciones_count': notificaciones_count,
        'alertas': alertas_activas,
    }
    return render(request, 'taxis/panel_general.html', context)


@login_required
def dashboard_admin(request):
    """
    Dashboard principal para usuarios con rol 'presidente'.
    """
    if request.user.role != "presidente":
        messages.error(
            request,
            "No tienes permisos para acceder al dashboard administrativo.",
        )
        return redirect("taxis:index")

    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)

    total_conductores = Conductor.objects.count()
    total_vehiculos = Taxi.objects.count()

    pagos_realizados = Conductor.objects.filter(
        pago_patente_realizado=True,
        fecha_pago_patente__gte=inicio_mes,
    ).count()

    pagos_pendientes = Conductor.objects.filter(
        pago_patente_realizado=False
    ).count()

    fecha_limite_inferior = hoy - timedelta(days=30)
    fecha_limite_superior = hoy - timedelta(days=15)

    patentes_por_vencer = Conductor.objects.filter(
        pago_patente_realizado=True,
        fecha_pago_patente__isnull=False,
        fecha_pago_patente__gte=fecha_limite_inferior,
        fecha_pago_patente__lte=fecha_limite_superior,
    )[:10]

    context = {
        "total_conductores": total_conductores,
        "total_vehiculos": total_vehiculos,
        "pagos_realizados": pagos_realizados,
        "pagos_pendientes": pagos_pendientes,
        "patentes_por_vencer": patentes_por_vencer,
    }
    return render(request, "taxis/dashboard_admin.html", context)






def login_redirect_view(request):
    """
    Redirige al usuario autenticado al dashboard correspondiente según su rol.
    """
    user = request.user
    if not user.is_authenticated:
        return redirect("login")

    if user.role == "presidente":
        return redirect("taxis:panel-general")
    return redirect("taxis:index")


# -------------------------------------------------------------------
# VISTA: ELIMINAR CUENTA PRESIDENTE (AUTOSERVICIO)
# -------------------------------------------------------------------


@login_required
def eliminar_cuenta_presidente(request):
    """
    Permite que un usuario con rol 'presidente' (que NO sea superusuario)
    elimine su propia cuenta desde el dashboard.
    """
    user = request.user

    if request.method == "POST":
        if isinstance(user, CustomUser) and user.role == "presidente" and not user.is_superuser:
            user.delete()
            logout(request)
            return redirect("login")
        return redirect("taxis:dashboard-admin")

    return render(request, "taxis/eliminar_cuenta_presidente.html")


# -------------------------------------------------------------------
# RESET CONTRASEÑA (Paso 1: solicitar código por correo)
# -------------------------------------------------------------------


def password_reset_request_view(request):
    """
    Paso 1 del flujo de restablecimiento de contraseña.
    """
    form = PasswordResetRequestForm(request.POST or None)

    user = None
    used_today = 0
    max_per_day = MAX_DAILY_RESENDS

    if request.method == "POST" and form.is_valid():
        email = (form.cleaned_data["email"] or "").lower()
        user = CustomUser.objects.filter(email=email).first()

        if not user:
            messages.info(
                request,
                "Si el correo está registrado, te hemos enviado un código de recuperación.",
            )
            return redirect("taxis:password_reset")

        puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
            user, email_type="password_reset"
        )
        if not puede_env:
            messages.error(request, error_msg)
            return render(
                request,
                "taxis/password_reset_request.html",
                {
                    "form": form,
                    "email_used_today": used_today,
                    "email_max_per_day": max_per_day,
                },
            )

        now = timezone.now()
        existing_code = (
            EmailVerificationCode.objects.filter(
                user=user,
                email_type="password_reset",
                is_used=False,
                expires_at__gte=now,
            )
            .order_by("-created_at")
            .first()
        )

        if existing_code:
            code = existing_code.code
        else:
            code = create_email_verification_code(
                user,
                email_type="password_reset",
                validity_minutes=15,
            )

        send_verification_email(user, code, email_type="password_reset")
        register_email_resend(user, email_type="password_reset")

        request.session["password_reset_user_id"] = user.id

        messages.info(
            request,
            "Si el correo está registrado, te hemos enviado un código de 6 dígitos para restablecer tu contraseña.",
        )
        return redirect("taxis:password_reset_verify")

    if not user:
        user_id = request.session.get("password_reset_user_id")
        if user_id:
            try:
                user = CustomUser.objects.get(pk=user_id)
            except CustomUser.DoesNotExist:
                user = None

    if user:
        _, _, used_today, max_per_day = can_resend_email_code(
            user, email_type="password_reset"
        )

    context = {
        "form": form,
        "email_used_today": used_today,
        "email_max_per_day": max_per_day,
    }
    return render(request, "taxis/password_reset_request.html", context)


# -------------------------------------------------------------------
# RESET CONTRASEÑA (Paso 2: verificar código)
# -------------------------------------------------------------------


def password_reset_verify_view(request):
    """
    Paso 2 del flujo de restablecimiento de contraseña.
    """
    user_id = request.session.get("password_reset_user_id")
    if not user_id:
        messages.error(request, "La sesión de recuperación ha expirado. Intenta de nuevo.")
        return redirect("taxis:password_reset")

    user = get_object_or_404(CustomUser, pk=user_id)
    form = VerificationCodeForm(request.POST or None)

    cooldown_seconds = 0
    last_code = (
        EmailVerificationCode.objects.filter(
            user=user,
            email_type="password_reset",
            is_used=False,
        )
        .order_by("-created_at")
        .first()
    )
    if last_code:
        cooldown_total = 60
        elapsed = (timezone.now() - last_code.created_at).total_seconds()
        remaining = int(cooldown_total - elapsed)
        if remaining > 0:
            cooldown_seconds = remaining

    puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
        user, email_type="password_reset"
    )

    if request.method == "POST":
        if "resend_code" in request.POST:
            form = VerificationCodeForm()
            if not puede_env:
                messages.error(request, error_msg)
            else:
                last_code = (
                    EmailVerificationCode.objects.filter(
                        user=user,
                        email_type="password_reset",
                        is_used=False,
                        expires_at__gte=timezone.now(),
                    )
                    .order_by("-created_at")
                    .first()
                )
                if last_code:
                    code = last_code.code
                else:
                    code = create_email_verification_code(
                        user,
                        email_type="password_reset",
                        validity_minutes=15,
                    )

                send_verification_email(user, code, email_type="primary")
                register_email_resend(user, email_type="password_reset")
                messages.info(request, "Se ha reenviado un nuevo código a tu correo.")
                cooldown_seconds = 60

            puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
                user, email_type="password_reset"
            )

        else:
            form = VerificationCodeForm(request.POST)
            if form.is_valid():
                code = form.cleaned_data["code"]
                if code:
                    code_obj = verify_email_code(
                        user, code, email_type="password_reset"
                    )
                    if code_obj:
                        mark_email_code_as_used(code_obj)
                        request.session["password_reset_code_ok"] = True
                        return redirect("taxis:password_reset_new_password")
                    else:
                        form.add_error(
                            "code",
                            "El código ingresado es incorrecto, ha expirado o se alcanzó el número máximo de intentos.",
                        )

    context = {
        "form": form,
        "cooldown_seconds": cooldown_seconds,
        "email_used_today": used_today,
        "email_max_per_day": max_per_day,
    }
    return render(request, "taxis/password_reset_verify.html", context)


# -------------------------------------------------------------------
# RESET CONTRASEÑA (Paso 3: nueva contraseña)
# -------------------------------------------------------------------


def password_reset_new_password_view(request):
    """
    Paso 3 del flujo de restablecimiento de contraseña.
    """
    user_id = request.session.get("password_reset_user_id")
    code_ok = request.session.get("password_reset_code_ok")

    if not user_id or not code_ok:
        messages.error(request, "La sesión de recuperación ha expirado. Intenta de nuevo.")
        return redirect("taxis:password_reset")

    user = get_object_or_404(CustomUser, pk=user_id)

    if request.method == "POST":
        password1 = (request.POST.get("password1") or "").strip()
        password2 = (request.POST.get("password2") or "").strip()

        if len(password1) < 6:
            messages.error(request, "La contraseña debe tener al menos 6 caracteres.")
        elif password1 != password2:
            messages.error(request, "Las contraseñas no coinciden.")
        else:
            user.set_password(password1)
            user.save()
            request.session.pop("password_reset_user_id", None)
            request.session.pop("password_reset_code_ok", None)
            messages.success(request, "Tu contraseña ha sido restablecida correctamente.")
            return redirect("taxis:password_reset_complete")

    return render(request, "taxis/password_reset_new_password.html")


@login_required
def actualizar_avatar_presidente(request):
    """
    Vista AJAX para actualizar la foto de perfil del Presidente.
    """
    if request.user.role != 'presidente':
        return JsonResponse({'success': False, 'error': 'No autorizado'})
    
    if request.method == 'POST' and request.FILES.get('avatar'):
        request.user.avatar = request.FILES['avatar']
        request.user.save()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido o sin archivo'})


def password_reset_complete_view(request):
    """
    Vista final que confirma que el restablecimiento de contraseña ha concluido.
    """
    return render(request, "taxis/password_reset_complete.html")
