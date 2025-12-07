"""
utils.py
Funciones de utilidad para verificación por correo electrónico en la app 'taxis':
- generación y gestión de códigos de verificación,
- límites de intentos y reenvíos,
- registro de intentos y envíos por email.
"""

import random
from datetime import timedelta

from django.conf import settings                    # Configuración global del proyecto.
from django.core.mail import send_mail              # Función para enviar correos.
from django.utils import timezone                   # Manejo de fechas/horas con zona.

from .models import (
    EmailVerificationCode,                          # Modelo de códigos de verificación por email.
    CustomUser,                                     # Modelo de usuario personalizado.
    VerificationAttemptLog,                         # Log de intentos de verificación.
    EmailSendLog,                                   # Log de envíos diarios por email.
)

# Parámetros de seguridad (usados también en vistas).
MAX_CODE_ATTEMPTS = 5           # Intentos máximos de verificación por código.
MAX_RESENDS_PER_CODE = 5        # Reenvíos máximos permitidos para el mismo código.
RESEND_COOLDOWN_SECONDS = 60    # Segundos mínimos entre reenvíos para un mismo código.
MAX_DAILY_RESENDS = 5           # Máximo de códigos enviados por día a un mismo email.


# -------------------------------------------------------------------
# Utilidades comunes (IP, User-Agent, logging)
# -------------------------------------------------------------------


def get_client_ip(request):
    """
    Obtiene la IP del cliente desde el objeto request.
    Intenta leer primero X-Forwarded-For (si hay proxy) y luego REMOTE_ADDR.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_user_agent(request):
    """
    Obtiene el User-Agent del cliente (navegador/dispositivo).
    """
    return request.META.get("HTTP_USER_AGENT", "")


def log_verification_attempt(
    request,
    user: CustomUser,
    method: str,
    code: str,
    result: str,
    reason: str = "",
):
    """
    Registra un intento de verificación (éxito o fallo) en VerificationAttemptLog.
    Guarda:
    - usuario,
    - método usado (por ejemplo 'email_primary'),
    - código ingresado,
    - resultado,
    - IP y User-Agent del cliente.
    """
    ip = get_client_ip(request)
    ua = get_user_agent(request)

    VerificationAttemptLog.objects.create(
        user=user,
        method=method,
        code=code or "",
        result=result,
        reason=reason,
        ip_address=ip,
        user_agent=ua,
    )


def generate_6_digit_code():
    """
    Genera un código numérico de 6 dígitos como cadena (str).
    Ejemplo: '034271'.
    """
    return f"{random.randint(0, 999999):06d}"


# -------------------------------------------------------------------
# EMAIL: conteo por destino (límite diario)
# -------------------------------------------------------------------


def _email_sends_today(email: str, email_type: str) -> int:
    """
    Devuelve cuántos códigos se han enviado hoy a ESTE email concreto
    y para ESTE TIPO de email (primary / password_reset).
    Se apoya en el modelo EmailSendLog.
    """
    if not email:
        return 0
    today = timezone.now().date()
    log, _ = EmailSendLog.objects.get_or_create(
        email=email.lower(),
        date=today,
        email_type=email_type,
    )
    return log.count


def register_email_send(email: str, email_type: str):
    """
    Incrementa el conteo de envíos de código a ESTE email y TIPO en la fecha actual.
    Se llama cada vez que se envía un correo con código de verificación.
    """
    if not email:
        return
    today = timezone.now().date()
    log, _ = EmailSendLog.objects.get_or_create(
        email=email.lower(),
        date=today,
        email_type=email_type,
    )
    log.count += 1
    log.save(update_fields=["count"])


# -------------------------------------------------------------------
# EMAIL: creación y gestión de códigos
# -------------------------------------------------------------------


def create_email_verification_code(user, email_type="primary", validity_minutes=15):
    """
    Crea y guarda un código de verificación de email para el usuario.
    - email_type:
        - 'primary': verificación de registro
        - 'password_reset': restablecimiento de contraseña
    - validity_minutes: minutos que el código será válido.
    Invalida (marca como usados) códigos anteriores activos del mismo tipo.
    """
    now = timezone.now()

    # Invalida códigos anteriores aún activos del mismo tipo.
    EmailVerificationCode.objects.filter(
        user=user,
        email_type=email_type,
        is_used=False,
        expires_at__gte=now,
    ).update(is_used=True, used_at=now)

    # Genera un nuevo código de 6 dígitos.
    code = generate_6_digit_code()

    # Crea el registro de código de verificación.
    EmailVerificationCode.objects.create(
        user=user,
        code=code,
        email_type=email_type,
        created_at=now,
        expires_at=now + timedelta(minutes=validity_minutes),
        is_used=False,
        attempt_count=0,
        resend_count=0,
        last_resend_at=None,
    )
    return code


def _email_daily_resends(user: CustomUser, email_type="primary"):
    """
    Función de compatibilidad que cuenta códigos por usuario y tipo.
    Aunque el límite real se controla por EMAIL en can_resend_email_code,
    se mantiene para no romper llamadas que esperen este valor.
    """
    today = timezone.now().date()
    return EmailVerificationCode.objects.filter(
        user=user,
        email_type=email_type,
        created_at__date=today,
    ).count()


def can_resend_email_code(user: CustomUser, email_type="primary"):
    """
    Determina si se puede enviar o reenviar un código de verificación por correo.

    Devuelve:
        (puede_enviar: bool, mensaje_error: str|None, usados_hoy: int, max_diario: int)

    Lógica:
    - El límite diario se calcula por email Y tipo (primary / password_reset).
    - También respeta:
        - número máximo de reenvíos por código,
        - cooldown mínimo entre reenvíos para el mismo código.
    """
    now = timezone.now()

    # Determina el email de destino según el tipo.
    if email_type in ("primary", "password_reset"):
        email = (user.email or "").lower()
    else:
        # Si se agregan otros tipos (secundario, etc.), se ajustarían aquí.
        email = (user.email or "").lower()

    # Cuenta cuántos códigos se han enviado hoy a este email para ESTE TIPO.
    today_used = _email_sends_today(email, email_type=email_type)

    # Límite diario de códigos enviados a este email y tipo.
    if today_used >= MAX_DAILY_RESENDS:
        return (
            False,
            f"Has alcanzado el límite diario de {MAX_DAILY_RESENDS} envíos de código por correo.",
            today_used,
            MAX_DAILY_RESENDS,
        )

    # Busca un código activo (no usado, no expirado) para este usuario y tipo.
    code_obj = (
        EmailVerificationCode.objects.filter(
            user=user,
            email_type=email_type,
            is_used=False,
            expires_at__gte=now,
        )
        .order_by("-created_at")
        .first()
    )

    # Si no hay código activo, se puede enviar uno nuevo (ya se revisó el límite diario).
    if not code_obj:
        return True, None, today_used, MAX_DAILY_RESENDS

    # Comprueba límite de reenvíos por este código concreto.
    if code_obj.resend_count >= MAX_RESENDS_PER_CODE:
        return (
            False,
            "Has alcanzado el número máximo de reenvíos para este código.",
            today_used,
            MAX_DAILY_RESENDS,
        )

    # Comprueba cooldown entre reenvíos del mismo código.
    if code_obj.last_resend_at:
        elapsed = (now - code_obj.last_resend_at).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            espera = int(RESEND_COOLDOWN_SECONDS - elapsed)
            return (
                False,
                f"Debes esperar {espera} segundos antes de reenviar el código.",
                today_used,
                MAX_DAILY_RESENDS,
            )

    # Si pasa todas las validaciones, se puede enviar/reenviar.
    return True, None, today_used, MAX_DAILY_RESENDS


def register_email_resend(user: CustomUser, email_type="primary"):
    """
    Registra que se ha reenviado (o enviado) un código:
    - Actualiza el contador de reenvíos del código activo más reciente.
    - Registra el envío por email de destino para el límite diario (email + tipo).
    """
    now = timezone.now()
    # Obtiene el código activo más reciente.
    code_obj = (
        EmailVerificationCode.objects.filter(
            user=user,
            email_type=email_type,
            is_used=False,
            expires_at__gte=now,
        )
        .order_by("-created_at")
        .first()
    )
    if code_obj:
        # Incrementa contadores de reenvío en el código.
        code_obj.resend_count += 1
        code_obj.last_resend_at = now
        code_obj.save(update_fields=["resend_count", "last_resend_at"])

    # Registra también el envío por email (para control diario por tipo).
    email = (user.email or "").lower()
    if email:
        register_email_send(email, email_type=email_type)


def send_verification_email(user, code, email_type="primary"):
    """
    Envía el código de verificación por correo electrónico al usuario.
    El contenido del correo es el mismo tanto para registro como para reset
    (lo diferencia el flujo que llame a esta función).
    """
    subject = "Verificación de correo - Cooperativa de Taxis"

    message = (
        f"Hola {user.first_name} {user.last_name},\n\n"
        "Gracias por registrarte en la plataforma de la Asociación Cooperativa "
        "WILSON TORRES 33 RL.\n\n"
        f"Tu código de verificación es: {code}\n\n"
        "Ingresa este código en la pantalla de verificación dentro de los "
        "próximos 15 minutos para activar tu cuenta.\n\n"
        "Si no realizaste esta solicitud, puedes ignorar este mensaje y tu "
        "correo no será asociado a ninguna cuenta.\n\n"
        "Atentamente,\n"
        "Equipo de la Cooperativa WILSON TORRES 33 RL"
    )

    # En tu flujo actual solo usas el correo principal (user.email).
    recipient = user.email

    if recipient:
        # Envía el correo usando la configuración de email del proyecto.
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )

# -------------------------------------------------------------------
# MARCAR / VERIFICAR CÓDIGOS DE EMAIL
# -------------------------------------------------------------------


def mark_email_code_as_used(code_obj: EmailVerificationCode):
    """
    Marca un código de verificación de email como usado.
    Actualiza:
    - is_used = True
    - used_at = ahora
    """
    code_obj.is_used = True
    code_obj.used_at = timezone.now()
    code_obj.save(update_fields=["is_used", "used_at"])


def verify_email_code(user: CustomUser, code: str, email_type="primary"):
    """
    Verifica si un código de email es válido para el usuario y tipo dados.

    Reglas:
    - Debe existir un código activo (no usado, no expirado) que coincida.
    - Si no coincide, se incrementa el contador de intentos del último código activo.
    - Si se excede MAX_CODE_ATTEMPTS, el código se marca como usado (invalidado).
    """
    now = timezone.now()

    # Intenta encontrar un código que coincida con el valor ingresado.
    code_obj = (
        EmailVerificationCode.objects.filter(
            user=user,
            code=code,
            email_type=email_type,
            is_used=False,
            expires_at__gte=now,
        )
        .order_by("-created_at")
        .first()
    )

    if not code_obj:
        # No se encontró un código coincidente: se considera intento fallido.
        # Se incrementa attempt_count en el último código activo (si existe).
        last_code = (
            EmailVerificationCode.objects.filter(
                user=user,
                email_type=email_type,
                is_used=False,
                expires_at__gte=now,
            )
            .order_by("-created_at")
            .first()
        )
        if last_code:
            last_code.attempt_count += 1
            # Si se alcanza el máximo de intentos, se invalida el código.
            if last_code.attempt_count >= MAX_CODE_ATTEMPTS:
                last_code.is_used = True
                last_code.used_at = now
            last_code.save(update_fields=["attempt_count", "is_used", "used_at"])
        return None

    # Si el código ya superó el límite de intentos, se trata como inválido.
    if code_obj.attempt_count >= MAX_CODE_ATTEMPTS:
        return None

    # Código válido (el flujo que lo llama debe marcarlo luego como usado).
    return code_obj
