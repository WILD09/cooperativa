"""
views.py
Vistas de la aplicación 'taxis':
- CRUD de Conductores y Taxis
- Flujo de registro y verificación por correo
- Dashboards según rol
- Restablecimiento de contraseña por correo
"""

from datetime import timedelta

from django.contrib import messages                              # Sistema de mensajes flash.
from django.contrib.auth.decorators import login_required        # Decorador para exigir login.
from django.shortcuts import render, redirect, get_object_or_404 # Atajos para vistas.
from django.urls import reverse_lazy, reverse                    # Utilidades para URLs reversas.
from django.utils import timezone                                # Manejo de fechas/horas con zona.
from django.views.generic import (                               # Vistas genéricas basadas en clase.
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .forms import (                                             # Formularios de la app.
    ConductorForm,
    TaxiForm,
    PresidenteRegisterForm,
    AsociadoRegisterForm,
    VerificationCodeForm,
    PasswordResetRequestForm,
)
from .models import (                                            # Modelos usados en las vistas.
    Conductor,
    Taxi,
    CustomUser,
    EmailVerificationCode,
)
from .utils import (                                             # Funciones de utilidades (solo email).
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
# FLUJO REGISTRO / VERIFICACIÓN POR CORREO
# -------------------------------------------------------------------


def select_role(request):
    """
    Vista para seleccionar el rol (presidente o asociado) antes de registrarse.
    Restringe que solo exista un presidente con correo verificado.
    """
    # Comprueba si ya existe un presidente con correo verificado.
    exists_presidente = CustomUser.objects.filter(
        role="presidente",
        is_email_verified=True,
    ).exists()

    if request.method == "POST":
        # Rol seleccionado por el usuario.
        role = request.POST.get("role")
        if role == "presidente" and exists_presidente:
            # Si ya hay un presidente, no permite registrar otro.
            messages.error(request, "Ya existe un presidente registrado en el sistema.")
        elif role in ("presidente", "asociado"):
            # Redirige al formulario de registro, pasando el rol en la querystring.
            return redirect(f"{reverse('taxis:register')}?role={role}")
        else:
            # Caso en que no se seleccionó un rol válido.
            messages.error(request, "Debes seleccionar un rol válido.")

    # Renderiza la plantilla con info de si existe o no un presidente.
    return render(
        request,
        "taxis/select_role.html",
        {"exists_presidente": exists_presidente},
    )


def register_presidente_asociado(request):
    """
    Vista de registro para presidente o asociado.
    - Usa un formulario distinto según el rol.
    - Crea o actualiza el usuario.
    - Envía un código de verificación por correo (respetando límite diario).
    """
    # Obtiene el rol seleccionado desde la querystring; por defecto 'asociado'.
    selected_role = request.GET.get("role", "asociado")
    if selected_role not in ("presidente", "asociado"):
        selected_role = "asociado"

    # Selecciona el formulario correspondiente al rol.
    FormClass = (
        PresidenteRegisterForm if selected_role == "presidente" else AsociadoRegisterForm
    )

    if request.method == "POST":
        form = FormClass(request.POST)
        if form.is_valid():
            # Normaliza el email a minúsculas.
            email = form.cleaned_data["email"].lower()
            # Busca si ya existe un usuario con ese correo.
            existing = CustomUser.objects.filter(email=email).first()

            if existing and existing.is_email_verified:
                # Si ya está verificado, no permite usar ese correo de nuevo.
                form.add_error("email", "Este correo ya está registrado.")
                template_name = (
                    "taxis/register_presidente.html"
                    if selected_role == "presidente"
                    else "taxis/register_asociado.html"
                )
                return render(
                    request,
                    template_name,
                    {"form": form, "selected_role": selected_role},
                )

            if existing and not existing.is_email_verified:
                # Si existe pero no está verificado, se reutiliza ese usuario.
                user = existing
                user.first_name = form.cleaned_data["first_name"]
                user.last_name = form.cleaned_data["last_name"]
                user.fecha_nacimiento = form.cleaned_data["fecha_nacimiento"]
                user.sexo = form.cleaned_data["sexo"]
                user.role = selected_role
                user.is_active = False
                user.is_email_verified = False

                # Construye el número de teléfono completo si se proporcionó.
                phone_country = form.cleaned_data.get("phone_country")
                phone_number = form.cleaned_data.get("phone_number")
                if phone_country and phone_number:
                    user.phone_number = f"{phone_country}{phone_number}"

                # Actualiza la contraseña con la nueva introducida.
                user.set_password(form.cleaned_data["password1"])
                user.save()
            else:
                # Caso en que es un nuevo usuario.
                user: CustomUser = form.save(commit=False)
                user.role = selected_role
                user.is_active = False
                user.is_email_verified = False

                # Construye el número de teléfono completo si se proporcionó.
                phone_country = form.cleaned_data.get("phone_country")
                phone_number = form.cleaned_data.get("phone_number")
                if phone_country and phone_number:
                    user.phone_number = f"{phone_country}{phone_number}"

                user.save()

            # ANTES de generar/enviar código, respetar límite diario por email
            puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
                user, email_type="primary"
            )
            if not puede_env:
                # Si ya alcanzó el límite, no generamos ni enviamos código
                messages.error(request, error_msg)
                template_name = (
                    "taxis/register_presidente.html"
                    if selected_role == "presidente"
                    else "taxis/register_asociado.html"
                )
                return render(
                    request,
                    template_name,
                    {"form": form, "selected_role": selected_role},
                )

            # Si puede_env es True, recién aquí creamos y enviamos el código
            code = create_email_verification_code(
                user, email_type="primary", validity_minutes=15
            )
            send_verification_email(user, code, email_type="primary")
            # Registramos este envío para el límite diario y por-código
            register_email_resend(user, email_type="primary")

            # Mensaje indicando que se envió el código al correo.
            messages.success(
                request,
                "Registro iniciado. Te hemos enviado un código de 6 dígitos a tu correo.",
            )
            # Redirige a la pantalla de verificación de correo.
            return redirect("taxis:verify_email", user_id=user.id)
    else:
        # Si es GET, se construye el formulario vacío.
        form = FormClass()

    # Selecciona la plantilla según el rol.
    template_name = (
        "taxis/register_presidente.html"
        if selected_role == "presidente"
        else "taxis/register_asociado.html"
    )

    # Renderiza la página de registro.
    return render(
        request,
        template_name,
        {"form": form, "selected_role": selected_role},
    )


def verify_email_view(request, user_id):
    """
    Vista para verificar el correo electrónico de un usuario:
    - Muestra el formulario para introducir el código.
    - Permite reenviar el código con límites de seguridad (diario y cooldown).
    """
    # Obtiene el usuario a partir del ID.
    user = get_object_or_404(CustomUser, pk=user_id)
    # Formulario para introducir el código (reutilizable en GET/POST).
    form = VerificationCodeForm(request.POST or None)

    # Cálculo del cooldown (tiempo de espera entre reenvíos).
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
        cooldown_total = 60  # segundos de cooldown.
        elapsed = (timezone.now() - last_code.created_at).total_seconds()
        remaining = int(cooldown_total - elapsed)
        if remaining > 0:
            cooldown_seconds = remaining

    # Comprueba si hoy se puede enviar/re-enviar otro código a este correo.
    puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
        user, email_type="primary"
    )

    if request.method == "POST":
        # Si el usuario pulsó el botón de "reenviar código".
        if "resend_code" in request.POST:
            form = VerificationCodeForm()  # formulario vacío, se limpia el campo.
            if not puede_env:
                # Si el límite diario se alcanzó, muestra el mensaje y NO envía
                messages.error(request, error_msg)
            else:
                # Genera un nuevo código (invalidando el anterior).
                code = create_email_verification_code(
                    user, email_type="primary", validity_minutes=15
                )
                # Envía el correo con el nuevo código.
                send_verification_email(user, code, email_type="password_reset")
                # Registra el reenvío (para el conteo diario y por código).
                register_email_resend(user, email_type="password_reset")
                messages.info(request, "Se ha reenviado un nuevo código a tu correo.")
                cooldown_seconds = 60

                # Recalcula el contador diario después del reenvío.
                puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
                    user, email_type="primary"
                )
        else:
            # Caso en el que el usuario envía el formulario con el código.
            form = VerificationCodeForm(request.POST)
            if form.is_valid():
                code = form.cleaned_data["code"]
                if code:
                    # Verifica si el código es válido, no usado y no vencido.
                    code_obj = verify_email_code(user, code, email_type="primary")
                    if code_obj:
                        # Marca el código como usado.
                        mark_email_code_as_used(code_obj)
                        # Marca el correo del usuario como verificado.
                        user.is_email_verified = True
                        # Activa la cuenta si no lo estaba.
                        if not user.is_active:
                            user.is_active = True
                        user.save()
                        # Redirige a la pantalla de verificación exitosa.
                        return redirect("taxis:verification_success")
                    else:
                        # Agrega error al formulario si el código no es válido.
                        form.add_error(
                            "code",
                            "El código ingresado es incorrecto, ha expirado o se alcanzó el número máximo de intentos.",
                        )

    # Contexto para la plantilla de verificación de correo.
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
    """
    Página de inicio de la app 'taxis'.
    """
    return render(request, "taxis/index.html")


@login_required
def dashboard_admin(request):
    """
    Dashboard principal para usuarios con rol 'presidente'.
    Muestra métricas generales sobre conductores y pagos.
    """
    # Si el usuario no es presidente, se le niega el acceso.
    if request.user.role != "presidente":
        messages.error(
            request,
            "No tienes permisos para acceder al dashboard administrativo.",
        )
        return redirect("taxis:index")

    # Fecha actual.
    hoy = timezone.now().date()
    # Primer día del mes actual.
    inicio_mes = hoy.replace(day=1)

    # Conteo de conductores y vehículos.
    total_conductores = Conductor.objects.count()
    total_vehiculos = Taxi.objects.count()

    # Pagos de patente realizados desde el inicio del mes.
    pagos_realizados = Conductor.objects.filter(
        pago_patente_realizado=True,
        fecha_pago_patente__gte=inicio_mes,
    ).count()

    # Conductores que aún no han pagado la patente.
    pagos_pendientes = Conductor.objects.filter(
        pago_patente_realizado=False
    ).count()

    # Rango de fechas para patentes por vencer (últimos 30 a 15 días).
    fecha_limite_inferior = hoy - timedelta(days=30)
    fecha_limite_superior = hoy - timedelta(days=15)

    # Lista de conductores cuyas patentes están próximas a vencer.
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


@login_required
def dashboard_asociado(request):
    """
    Dashboard para usuarios con rol 'asociado'.
    Muestra métricas generales similares al dashboard de presidente.
    """
    # Si el usuario no es asociado, se niega el acceso.
    if request.user.role != "asociado":
        messages.error(
            request,
            "No tienes permisos para acceder al dashboard de asociado.",
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
    return render(request, "taxis/dashboard_asociado.html", context)


def login_redirect_view(request):
    """
    Redirige al usuario autenticado al dashboard correspondiente según su rol.
    Si no está autenticado, lo envía a la pantalla de login.
    """
    user = request.user
    if not user.is_authenticated:
        return redirect("login")

    if user.role == "presidente":
        return redirect("taxis:dashboard-admin")
    elif user.role == "asociado":
        return redirect("taxis:dashboard-asociado")
    # Rol desconocido: se envía a la página de inicio.
    return redirect("taxis:index")


# -------------------------------------------------------------------
# RESET CONTRASEÑA (Paso 1: solicitar código por correo)
# -------------------------------------------------------------------


def password_reset_request_view(request):
    """
    Paso 1 del flujo de restablecimiento de contraseña:
    - El usuario introduce su correo.
    - Si existe un usuario con ese correo, se envía (o reutiliza) un código.
    - Si NO existe, se muestra un mensaje genérico (sin revelar nada).
    - Se aplica límite diario por email y reintentos.
    """
    form = PasswordResetRequestForm(request.POST or None)

    user = None
    used_today = 0
    # Valor máximo de envíos diarios (solo informativo para la plantilla)
    max_per_day = MAX_DAILY_RESENDS

    if request.method == "POST" and form.is_valid():
        # Normaliza el correo a minúsculas
        email = (form.cleaned_data["email"] or "").lower()

        # Busca el usuario por correo SIN lanzar excepción si no existe
        user = CustomUser.objects.filter(email=email).first()

        if not user:
            # No se revela si el correo existe o no
            messages.info(
                request,
                "Si el correo está registrado, te hemos enviado un código de recuperación.",
            )
            # Se redirige al mismo paso 1 para no dar pistas
            return redirect("taxis:password_reset")

        # 1) Comprueba límite diario de envíos de código para este email.
        puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
            user, email_type="password_reset"
        )
        if not puede_env:
            # Si no puede enviar, muestra error y renderiza la misma página.
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
        # Busca si ya existe un código activo de tipo 'password_reset' que no haya expirado.
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
            # Si hay un código activo, se reutiliza para no crear otro.
            code = existing_code.code
        else:
            # Si no hay código activo, se crea uno nuevo con validez de 15 minutos.
            code = create_email_verification_code(
                user,
                email_type="password_reset",
                validity_minutes=15,
            )

        # 2) Envía el código (nuevo o reutilizado) por correo.
        send_verification_email(user, code, email_type="password_reset")

        # 3) Registra el envío para el conteo diario y límite de reenvíos.
        register_email_resend(user, email_type="password_reset")

        # 4) Guarda el ID del usuario en sesión para el siguiente paso.
        request.session["password_reset_user_id"] = user.id

        # Mensaje informando que (si el correo es válido) se envió el código.
        messages.info(
            request,
            "Si el correo está registrado, te hemos enviado un código de 6 dígitos para restablecer tu contraseña.",
        )
        # Redirige al paso 2: verificación del código.
        return redirect("taxis:password_reset_verify")

    # Si ya hay usuario en sesión desde un intento anterior, lo recupera para mostrar el uso diario.
    if not user:
        user_id = request.session.get("password_reset_user_id")
        if user_id:
            try:
                user = CustomUser.objects.get(pk=user_id)
            except CustomUser.DoesNotExist:
                user = None

    # Si hay usuario asociado, recalcula el uso diario de email para la vista.
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
    Paso 2 del flujo de restablecimiento de contraseña:
    - El usuario introduce el código recibido por correo.
    - Puede solicitar reenviar el código dentro de los límites diarios.
    """
    # Recupera de sesión el usuario asociado al proceso de reset.
    user_id = request.session.get("password_reset_user_id")
    if not user_id:
        messages.error(request, "La sesión de recuperación ha expirado. Intenta de nuevo.")
        return redirect("taxis:password_reset")

    user = get_object_or_404(CustomUser, pk=user_id)
    form = VerificationCodeForm(request.POST or None)

    # Cooldown visual para deshabilitar el botón de reenvío durante un tiempo.
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

    # Protección diaria: controla cuántos códigos se han enviado a ese correo.
    puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
        user, email_type="password_reset"
    )

    if request.method == "POST":
        if "resend_code" in request.POST:
            # El usuario solicita reenviar el código.
            form = VerificationCodeForm()
            if not puede_env:
                messages.error(request, error_msg)
            else:
                # Reutiliza un código activo si existe.
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
                    # Si no hay código activo, crea uno nuevo.
                    code = create_email_verification_code(
                        user,
                        email_type="password_reset",
                        validity_minutes=15,
                    )

                # Envía el código por correo.
                send_verification_email(user, code, email_type="primary")
                # Registra el reenvío para el conteo diario.
                register_email_resend(user, email_type="password_reset")
                messages.info(request, "Se ha reenviado un nuevo código a tu correo.")
                cooldown_seconds = 60

            # Recalcula el contador diario tras el reenvío.
            puede_env, error_msg, used_today, max_per_day = can_resend_email_code(
                user, email_type="password_reset"
            )

        else:
            # El usuario intenta validar un código introducido.
            form = VerificationCodeForm(request.POST)
            if form.is_valid():
                code = form.cleaned_data["code"]
                if code:
                    # Verifica el código (vigencia, intentos, etc.).
                    code_obj = verify_email_code(
                        user, code, email_type="password_reset"
                    )
                    if code_obj:
                        # Marca el código como usado.
                        mark_email_code_as_used(code_obj)
                        # Marca en sesión que el código fue validado correctamente.
                        request.session["password_reset_code_ok"] = True
                        # Redirige al paso 3: nueva contraseña.
                        return redirect("taxis:password_reset_new_password")
                    else:
                        # Error cuando el código no es válido o ha expirado.
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
    Paso 3 del flujo de restablecimiento de contraseña:
    - Tras un código válido, el usuario define y confirma una nueva contraseña.
    """
    # Recupera de sesión el usuario y el estado de verificación de código.
    user_id = request.session.get("password_reset_user_id")
    code_ok = request.session.get("password_reset_code_ok")

    # Si falta cualquiera de los dos, la sesión de recuperación no es válida.
    if not user_id or not code_ok:
        messages.error(request, "La sesión de recuperación ha expirado. Intenta de nuevo.")
        return redirect("taxis:password_reset")

    user = get_object_or_404(CustomUser, pk=user_id)

    if request.method == "POST":
        # Obtiene las contraseñas introducidas, sin espacios extremos.
        password1 = (request.POST.get("password1") or "").strip()
        password2 = (request.POST.get("password2") or "").strip()

        # Valida longitud mínima.
        if len(password1) < 6:
            messages.error(request, "La contraseña debe tener al menos 6 caracteres.")
        # Valida que ambas coincidan.
        elif password1 != password2:
            messages.error(request, "Las contraseñas no coinciden.")
        else:
            # Asigna la nueva contraseña y guarda.
            user.set_password(password1)
            user.save()
            # Limpia la sesión relacionada con el flujo de reset.
            request.session.pop("password_reset_user_id", None)
            request.session.pop("password_reset_code_ok", None)
            messages.success(request, "Tu contraseña ha sido restablecida correctamente.")
            # Redirige a la pantalla final del flujo de recuperación.
            return redirect("taxis:password_reset_complete")

    # Si es GET o hubo errores, muestra la plantilla de nueva contraseña.
    return render(request, "taxis/password_reset_new_password.html")


def password_reset_complete_view(request):
    """
    Vista final que confirma que el restablecimiento de contraseña ha concluido.
    """
    return render(request, "taxis/password_reset_complete.html")
