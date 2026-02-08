"""
utils.py
Funciones de utilidad unificadas para la app 'taxis':
1. Verificación por correo electrónico (códigos, límites, auditoría).
2. Generación de PDFs (xhtml2pdf).
3. Auditoría unificada (MovimientoAudit) con fecha/hora garantizada.
"""

import random
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils import timezone

# Librería de PDF
from xhtml2pdf import pisa

# Modelos
from .models import (
    EmailVerificationCode,
    EmailSendLog,
    VerificationAttemptLog,
    MovimientoAudit,
)

# ====================================================================
# PARÁMETROS DE SEGURIDAD (EMAIL CÓDIGOS)
# ====================================================================
MAX_CODE_ATTEMPTS = 5           # Intentos máximos de verificación por código.
MAX_RESENDS_PER_CODE = 5        # Reenvíos máximos permitidos para el mismo código.
RESEND_COOLDOWN_SECONDS = 60    # Segundos mínimos entre reenvíos para un mismo código.
MAX_DAILY_RESENDS = 5           # Máximo de códigos enviados por día a un mismo email.


# ====================================================================
# GENERACIÓN DE PDF
# ====================================================================

def render_to_pdf(template_src, context_dict=None):
    """
    Convierte un template HTML a PDF usando xhtml2pdf.
    Soporta caracteres latinos (UTF-8).
    """
    context_dict = context_dict or {}
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()

    # encoding='UTF-8' es crucial para acentos y ñ
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)

    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")
    return None


# Alias para compatibilidad si en views importas rendertopdf
rendertopdf = render_to_pdf


# ====================================================================
# UTILIDADES COMUNES (IP, User-Agent)
# ====================================================================

def get_client_ip(request):
    """Obtiene la IP del cliente desde el objeto request."""
    if not request:
        return ""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def get_user_agent(request):
    """Obtiene el User-Agent del cliente (navegador/dispositivo)."""
    if not request:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")


def log_verification_attempt(request, user, method, code, result, reason=""):
    """Registra un intento de verificación (éxito o fallo) en VerificationAttemptLog."""
    VerificationAttemptLog.objects.create(
        user=user,
        method=method,
        code=code or "",
        result=result,
        reason=reason,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        timestamp=timezone.now(),
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
    email = (getattr(user, "email", "") or "").lower()

    # 1. Verificar límite diario global
    today_used = _email_sends_today(email, email_type=email_type)
    if today_used >= MAX_DAILY_RESENDS:
        return (
            False,
            f"Límite diario de {MAX_DAILY_RESENDS} envíos alcanzado.",
            today_used,
            MAX_DAILY_RESENDS,
        )

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
        return (
            False,
            "Máximo de reenvíos para este código alcanzado.",
            today_used,
            MAX_DAILY_RESENDS,
        )

    # 4. Verificar Cooldown (tiempo de espera)
    if code_obj.last_resend_at:
        elapsed = (now - code_obj.last_resend_at).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            espera = int(RESEND_COOLDOWN_SECONDS - elapsed)
            return (
                False,
                f"Espera {espera} segundos antes de reenviar.",
                today_used,
                MAX_DAILY_RESENDS,
            )

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

    email = (getattr(user, "email", "") or "").lower()
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
        is_used=False,
    )
    return code


def send_verification_email(user, code, email_type="primary"):
    """Envía el correo electrónico usando send_mail de Django."""
    subject = "Código de verificación - Cooperativa WILSON TORRES 33 RL"
    message = (
        f"Hola {getattr(user, 'first_name', '')},\n\n"
        f"Tu código de verificación es: {code}\n\n"
        "Este código es válido por 15 minutos.\n"
        "Si no solicitaste este código, ignora este mensaje."
    )

    recipient = getattr(user, "email", None)
    if recipient:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )


# ====================================================================
# VERIFICACIÓN
# ====================================================================

def mark_email_code_as_used(code_obj):
    """Marca el código como usado."""
    if not code_obj:
        return
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
# AUDITORÍA - MOVIMIENTOS (UNIFICADO + FECHA/HORA GARANTIZADA)
# ====================================================================

# Normalización (NECESARIA para que no dé "_norm_modulo no está definido")
MODULOS_VALIDOS = {"autenticacion", "afiliados", "vehiculos", "finanzas", "perfiles", "auditoria"}

MODULO_ALIASES = {
    # finanzas
    "finanzas": "finanzas",
    "finanza": "finanzas",
    "modulofinanzas": "finanzas",
    "finanzas.": "finanzas",
    "finanzas ": "finanzas",
    "Finanzas": "finanzas",
    # vehiculos
    "vehiculos": "vehiculos",
    "vehículo": "vehiculos",
    "vehículos": "vehiculos",
    "modulovehiculos": "vehiculos",
    "Vehculos": "vehiculos",
    "Vehículos": "vehiculos",
    # afiliados
    "afiliados": "afiliados",
    "moduloafiliados": "afiliados",
    "Afiliados": "afiliados",
    # perfiles
    "perfiles": "perfiles",
    "perfil": "perfiles",
    "moduloperfiles": "perfiles",
    "Perfiles": "perfiles",
    # seguridad/configuración/auth
    "seguridad": "autenticacion",
    "moduloseguridad": "autenticacion",
    "configuracion": "perfiles",
    "configuración": "perfiles",
    "moduloconfiguracion": "perfiles",
    "Configuracin": "perfiles",
    # dt5 -> vehiculos (compatibilidad)
    "dt5": "vehiculos",
    "modulodt5": "vehiculos",
    #Auditoria
    "auditoria": "auditoria",
    "auditoría": "auditoria",     # por si llega con tilde
    "moduloauditoria": "auditoria",
    "Auditoría": "auditoria",
}


def _norm_value(v):
    if v is None:
        return ""
    return str(v).strip()


def _norm_modulo(modulo: str) -> str:
    m = _norm_value(modulo)
    if not m:
        return ""
    ml = m.lower()
    ml = MODULO_ALIASES.get(ml, MODULO_ALIASES.get(m, ml))
    return ml if ml in MODULOS_VALIDOS else ""


def texto_filtros(*args, **kwargs) -> str:
    """
    Genera un texto corto y consistente con los filtros usados en listados/reportes,
    para guardarlo en auditoría (descripcion).

    Uso típico:
        texto_filtros(q=..., estado=..., modo=..., periodo=..., anio=..., mes=..., orden=...)

    También acepta un dict como primer argumento:
        texto_filtros(request.GET)  # o un dict normal
    """
    data = {}

    if args:
        first = args[0]
        if isinstance(first, dict):
            data.update(first)

    data.update(kwargs)

    # Normaliza posibles estructuras tipo QueryDict (valores list/tuplas)
    def pick(v):
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return _norm_value(v[0]) if v else ""
        return _norm_value(v)

    # Etiquetas bonitas (opcional)
    labels = {
        "q": "Búsqueda",
        "accion": "Acción",
        "modulo": "Módulo",
        "periodo": "Período",
        "estado": "Estado",
        "estatus": "Estatus",
        "modo": "Modo",
        "anio": "Año",
        "mes": "Mes",
        "orden": "Orden",
        "genero": "Género",
    }

    partes = []
    for key in ["q", "accion", "modulo", "periodo", "estado", "estatus", "modo", "anio", "mes", "orden", "genero"]:
        if key in data:
            val = pick(data.get(key))
            if val != "":
                partes.append(f"{labels.get(key, key)}: {val}")

    # Si no coincide con esas keys, igual incluye lo demás (sin duplicar)
    for k, v in data.items():
        if k in ["q", "accion", "modulo", "periodo", "estado", "estatus", "modo", "anio", "mes", "orden", "genero"]:
            continue
        val = pick(v)
        if val != "":
            partes.append(f"{labels.get(k, k)}: {val}")

    return " | ".join(partes) if partes else "Sin filtros"


def registrar_movimiento(
    request,
    accion,
    modulo,
    objeto_tipo="Sistema",
    objeto_id=None,
    objeto_nombre="",
    descripcion="",
    cambios_antes=None,
    cambios_despues=None,
    usuario=None,
):
    """
    Reglas:
    - `accion` debe ser clave corta (choices / max_length=20).
    - Texto largo en `descripcion`.
    - `modulo` se guarda normalizado como clave: autenticacion/afiliados/vehiculos/finanzas/perfiles.
    - Se llena `fecha` y `fecha_formato` (hora local) para mostrar fecha+hora siempre.
    """
    user = usuario
    if user is None and request is not None:
        user = getattr(request, "user", None)

    if not getattr(user, "is_authenticated", False):
        user = None

    modulo_norm = _norm_modulo(modulo) or "autenticacion"
    accion_norm = _norm_value(accion)
    descripcion_norm = _norm_value(descripcion)

    fecha_local = timezone.localtime()
    fecha_fmt = fecha_local.strftime("%d/%m/%Y %H:%M")

    mov = MovimientoAudit.objects.create(
        usuario=user,
        accion=accion_norm,
        modulo=modulo_norm,
        objeto_tipo=objeto_tipo or "Sistema",
        objeto_id=objeto_id,
        objeto_nombre=_norm_value(objeto_nombre),
        descripcion=descripcion_norm,
        cambios_antes=cambios_antes or {},
        cambios_despues=cambios_despues or {},
        fecha=fecha_local,
        fecha_formato=fecha_fmt,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    return mov


# =========================
# ATAJOS ESPECÍFICOS
# =========================

def log_login(request):
    email = ""
    user = getattr(request, "user", None) if request else None
    if getattr(user, "is_authenticated", False):
        email = user.email or ""

    return registrar_movimiento(
        request,
        accion="login",
        modulo="autenticacion",
        objeto_tipo="CustomUser",
        objeto_id=getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
        objeto_nombre=getattr(user, "username", "") if getattr(user, "is_authenticated", False) else "",
        descripcion=f"Inicio de sesión: {email}",
    )


def log_logout(request):
    """
    Importante: llamar ANTES de logout(request), porque luego request.user será AnonymousUser.
    """
    email = ""
    user = getattr(request, "user", None) if request else None
    if getattr(user, "is_authenticated", False):
        email = user.email or ""

    return registrar_movimiento(
        request,
        accion="logout",
        modulo="autenticacion",
        objeto_tipo="CustomUser",
        objeto_id=getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
        objeto_nombre=getattr(user, "username", "") if getattr(user, "is_authenticated", False) else "",
        descripcion=f"Cierre de sesión: {email}",
    )


loglogin = log_login
loglogout = log_logout


def log_crear(obj, request, modulo, objeto_tipo=None, descripcion=None):
    tipo = objeto_tipo or obj.__class__.__name__
    return registrar_movimiento(
        request,
        accion="crear",
        modulo=modulo,
        objeto_tipo=tipo,
        objeto_id=getattr(obj, "id", None),
        objeto_nombre=str(obj),
        descripcion=descripcion or f"Creado {tipo}: {obj}",
    )


def _model_to_dict_simple(obj):
    data = {}
    for field in getattr(obj, "_meta", None).fields:
        name = field.name
        try:
            value = getattr(obj, name)
        except Exception:
            value = None
        data[name] = "" if value is None else str(value)
    return data


def log_editar(obj_original, obj_modificado, request, modulo, objeto_tipo=None, descripcion=None):
    tipo = objeto_tipo or obj_modificado.__class__.__name__

    cambios_antes = _model_to_dict_simple(obj_original)
    cambios_despues = _model_to_dict_simple(obj_modificado)

    cambios_reales = {}
    for key in cambios_antes.keys():
        if cambios_antes.get(key) != cambios_despues.get(key):
            cambios_reales[key] = {"antes": cambios_antes.get(key), "despues": cambios_despues.get(key)}

    return registrar_movimiento(
        request,
        accion="editar",
        modulo=modulo,
        objeto_tipo=tipo,
        objeto_id=getattr(obj_modificado, "id", None),
        objeto_nombre=str(obj_modificado),
        descripcion=descripcion or f"Editado {tipo}: {obj_modificado} ({len(cambios_reales)} cambios)",
        cambios_antes=cambios_antes,
        cambios_despues=cambios_despues,
    )


def log_eliminar(obj, request, modulo, objeto_tipo=None, descripcion=None):
    tipo = objeto_tipo or obj.__class__.__name__
    return registrar_movimiento(
        request,
        accion="eliminar",
        modulo=modulo,
        objeto_tipo=tipo,
        objeto_id=getattr(obj, "id", None),
        objeto_nombre=str(obj),
        descripcion=descripcion or f"Eliminado {tipo}: {obj}",
    )


def log_pago(conductor, monto, mes, anio, request, modulo="finanzas"):
    try:
        nombre = f"{conductor.nombres} {conductor.apellidos}"
    except Exception:
        nombre = str(conductor)

    return registrar_movimiento(
        request,
        accion="pago_registrado",
        modulo=modulo,
        objeto_tipo="PagoMensual",
        objeto_nombre=nombre,
        descripcion=f"Pago registrado: {nombre} - ${monto} ({mes}/{anio})",
    )


def log_accion_masiva(request, modulo, descripcion, cantidad=0):
    return registrar_movimiento(
        request,
        accion="masivo",
        modulo=modulo,
        objeto_tipo="Sistema",
        descripcion=f"{descripcion} ({cantidad} registros afectados)",
    )


def log_exportar(request, modulo, descripcion="", formato=None, **kwargs):
    fmt = (formato or kwargs.get("formato") or "").strip().lower()

    accion = "exportar"
    if fmt in ("pdf",):
        accion = "exportar_pdf"
    elif fmt in ("excel", "xlsx", "xls"):
        accion = "exportar_excel"

    # Descripción opcional (útil para mostrar filtros usados)
    if fmt:
        pref = f"Exportación {fmt.upper()}"
        descripcion = f"{pref} | {descripcion}" if descripcion else pref

    return registrar_movimiento(
        request=request,
        accion=accion,
        modulo=modulo,
        descripcion=descripcion,
    )

def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def log_password_change(request, usuario_objetivo, accion, descripcion):
    MovimientoAudit.objects.create(
        usuario=usuario_objetivo,
        accion=accion,
        modulo="autenticacion",
        objeto_tipo=usuario_objetivo.__class__.__name__,
        objeto_id=usuario_objetivo.id,
        objeto_nombre=getattr(usuario_objetivo, "username", "") or "",
        descripcion=descripcion,
        fecha=timezone.now(),
        ip_address=_get_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:900],
    )



# ====================================================================
# COMPATIBILIDAD (nombres viejos -> nuevos)
# ====================================================================

# Para código viejo que aún haga:
#   from taxis.utils import registrarmovimiento, textofiltros, logpago
registrarmovimiento = registrar_movimiento
textofiltros = texto_filtros
logpago = log_pago
