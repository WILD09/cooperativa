from datetime import datetime, timedelta
from django.core.cache import cache

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_HOURS = 24

def get_attempt_key(username):
    """Genera key única para cache de intentos"""
    return f"login_attempts_{username}"

def get_lockout_key(username):
    """Genera key única para cache de bloqueo"""
    return f"login_lockout_{username}"

def record_failed_attempt(username):
    """Registra intento fallido"""
    key = get_attempt_key(username)
    attempts = cache.get(key, 0)
    attempts += 1
    
    # Guardar por 24 horas
    cache.set(key, attempts, 60 * 60 * 24)
    
    if attempts >= MAX_LOGIN_ATTEMPTS:
        lockout_key = get_lockout_key(username)
        lockout_until = datetime.now() + timedelta(hours=LOCKOUT_DURATION_HOURS)
        cache.set(lockout_key, lockout_until.isoformat(), 60 * 60 * 24)
        return True  # Usuario bloqueado
    
    return False

def is_locked_out(username):
    """Verifica si usuario está bloqueado"""
    lockout_key = get_lockout_key(username)
    lockout_until_str = cache.get(lockout_key)
    
    if not lockout_until_str:
        return False, None
    
    lockout_until = datetime.fromisoformat(lockout_until_str)
    
    # Auto-reset si pasaron 24 horas
    if datetime.now() >= lockout_until:
        clear_attempts(username)
        return False, None
    
    return True, lockout_until

def clear_attempts(username):
    """Limpia intentos y bloqueo"""
    cache.delete(get_attempt_key(username))
    cache.delete(get_lockout_key(username))

def get_remaining_attempts(username):
    """Obtiene intentos restantes"""
    attempts = cache.get(get_attempt_key(username), 0)
    return MAX_LOGIN_ATTEMPTS - attempts
