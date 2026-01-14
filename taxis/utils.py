"""
utils.py
Funciones de utilidad unificadas para la app 'taxis':
1. Verificación por correo electrónico (códigos, límites, auditoría).
2. Generación de PDFs (xhtml2pdf).
"""

import random
from datetime import timedelta, date
from io import BytesIO

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import get_template

# Librería de PDF
from xhtml2pdf import pisa

# Importación diferida o directa de modelos.
from .models import (
    EmailVerificationCode,
    EmailSendLog,
    VerificationAttemptLog,
    MovimientoAudit,
    Notificacion
)

# ====================================================================
# PARÁMETROS DE SEGURIDAD
# ====================================================================
MAX_CODE_ATTEMPTS = 5           # Intentos máximos de verificación por código.
MAX_RESENDS_PER_CODE = 5        # Reenvíos máximos permitidos para el mismo código.
RESEND_COOLDOWN_SECONDS = 60    # Segundos mínimos entre reenvíos para un mismo código.
MAX_DAILY_RESENDS = 5           # Máximo de códigos enviados por día a un mismo email.

# ====================================================================
# GENERACIÓN DE PDF
# ====================================================================

def render_to_pdf(template_src, context_dict={}):
    """
    Convierte un template HTML a PDF usando xhtml2pdf.
    Soporta caracteres latinos (UTF-8).
    """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    
    # encoding='UTF-8' es crucial para acentos y ñ
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

# ====================================================================
# UTILIDADES COMUNES (IP, User-Agent)
# ====================================================================

def get_client_ip(request):
    """Obtiene la IP del cliente desde el objeto request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip

def get_user_agent(request):
    """Obtiene el User-Agent del cliente (navegador/dispositivo)."""
    return request.META.get("HTTP_USER_AGENT", "")

def log_verification_attempt(request, user, method, code, result, reason=""):
    """Registra un intento de verificación (éxito o fallo) en VerificationAttemptLog."""
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
    """Genera un código numérico de 6 dígitos como cadena."""
    return f"{random.randint(0, 999999):06d}"

# ====================================================================
# EMAIL: Lógica de conteo y límites
# ====================================================================

def _email_sends_today(email, email_type):
    """Devuelve cuántos códigos se han enviado hoy a ESTE email y TIPO."""
    if not email:
        return 0
    today = timezone.now().date()
    log, _ = EmailSendLog.objects.get_or_create(
        email=email.lower(),
        date=today,
        email_type=email_type,
    )
    return log.count

def register_email_send(email, email_type):
    """Incrementa el conteo de envíos en el log diario."""
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

def can_resend_email_code(user, email_type="primary"):
    """
    Verifica si se puede enviar/reenviar un código.
    Retorna: (puede_enviar, mensaje_error, usados_hoy, max_diario)
    """
    now = timezone.now()
    email = (user.email or "").lower()

    # 1. Verificar límite diario global
    today_used = _email_sends_today(email, email_type=email_type)
    if today_used >= MAX_DAILY_RESENDS:
        return (False, f"Límite diario de {MAX_DAILY_RESENDS} envíos alcanzado.", today_used, MAX_DAILY_RESENDS)

    # 2. Buscar código activo existente
    code_obj = EmailVerificationCode.objects.filter(
        user=user,
        email_type=email_type,
        is_used=False,
        expires_at__gte=now,
    ).order_by("-created_at").first()

    # Si no hay código activo, está limpio para enviar uno nuevo
    if not code_obj:
        return True, None, today_used, MAX_DAILY_RESENDS

    # 3. Verificar límite de reenvíos del código actual
    if code_obj.resend_count >= MAX_RESENDS_PER_CODE:
        return (False, "Máximo de reenvíos para este código alcanzado.", today_used, MAX_DAILY_RESENDS)

    # 4. Verificar Cooldown (tiempo de espera)
    if code_obj.last_resend_at:
        elapsed = (now - code_obj.last_resend_at).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            espera = int(RESEND_COOLDOWN_SECONDS - elapsed)
            return (False, f"Espera {espera} segundos antes de reenviar.", today_used, MAX_DAILY_RESENDS)

    return True, None, today_used, MAX_DAILY_RESENDS

def register_email_resend(user, email_type="primary"):
    """Registra el reenvío: actualiza el código actual y el log diario."""
    now = timezone.now()
    code_obj = EmailVerificationCode.objects.filter(
        user=user,
        email_type=email_type,
        is_used=False,
        expires_at__gte=now,
    ).order_by("-created_at").first()

    if code_obj:
        code_obj.resend_count += 1
        code_obj.last_resend_at = now
        code_obj.save(update_fields=["resend_count", "last_resend_at"])

    email = (user.email or "").lower()
    if email:
        register_email_send(email, email_type=email_type)

# ====================================================================
# EMAIL: Creación y Envío
# ====================================================================

def create_email_verification_code(user, email_type="primary", validity_minutes=15):
    """Crea un nuevo código y marca los anteriores como usados."""
    now = timezone.now()

    # Invalidar anteriores
    EmailVerificationCode.objects.filter(
        user=user,
        email_type=email_type,
        is_used=False,
        expires_at__gte=now,
    ).update(is_used=True, used_at=now)

    code = generate_6_digit_code()

    EmailVerificationCode.objects.create(
        user=user,
        code=code,
        email_type=email_type,
        created_at=now,
        expires_at=now + timedelta(minutes=validity_minutes),
        is_used=False
    )
    return code

def send_verification_email(user, code, email_type="primary"):
    """Envía el correo electrónico usando send_mail de Django."""
    subject = "Código de verificación - Cooperativa WILSON TORRES 33 RL"
    message = (
        f"Hola {user.first_name},\n\n"
        f"Tu código de verificación es: {code}\n\n"
        "Este código es válido por 15 minutos.\n"
        "Si no solicitaste este código, ignora este mensaje."
    )
    
    recipient = user.email
    if recipient:
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error enviando correo: {e}")

# ====================================================================
# VERIFICACIÓN
# ====================================================================

def mark_email_code_as_used(code_obj):
    """Marca el código como usado."""
    if code_obj:
        code_obj.is_used = True
        code_obj.used_at = timezone.now()
        code_obj.save(update_fields=["is_used", "used_at"])

def verify_email_code(user, code, email_type="primary"):
    """
    Verifica el código. Maneja conteo de intentos fallidos.
    Retorna el objeto código si es válido, o None.
    """
    now = timezone.now()

    # Buscar código exacto
    code_obj = EmailVerificationCode.objects.filter(
        user=user,
        code=code,
        email_type=email_type,
        is_used=False,
        expires_at__gte=now,
    ).order_by("-created_at").first()

    # Si no coincide, registrar intento fallido en el último código activo
    if not code_obj:
        last_code = EmailVerificationCode.objects.filter(
            user=user,
            email_type=email_type,
            is_used=False,
            expires_at__gte=now,
        ).order_by("-created_at").first()

        if last_code:
            last_code.attempt_count += 1
            if last_code.attempt_count >= MAX_CODE_ATTEMPTS:
                last_code.is_used = True
                last_code.used_at = now
            last_code.save()
        return None

    # Si coincide pero excedió intentos
    if code_obj.attempt_count >= MAX_CODE_ATTEMPTS:
        return None

    return code_obj

# ====================================================================
# AUDITORÍA Y NOTIFICACIONES (Helpers)
# ====================================================================

def log_movimiento(usuario, accion, modulo="General"):
    """Crea un registro en MovimientoAudit."""
    return MovimientoAudit.objects.create(
        usuario=usuario,
        accion=accion,
        modulo=modulo
    )

def crear_notificacion(titulo, mensaje):
    """Crea una notificación en el buzón."""
    return Notificacion.objects.create(
        titulo=titulo,
        mensaje=mensaje
    )
