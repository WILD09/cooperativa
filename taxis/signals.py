from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .utils import registrar_movimiento

@receiver(user_logged_in, dispatch_uid="taxis.audit_login", weak=False)
def audit_login(sender, request, user, **kwargs):
    registrar_movimiento(
        request=request,
        accion="login",
        modulo="autenticacion",
        objeto_tipo=user.__class__.__name__,
        objeto_id=getattr(user, "id", None),
        objeto_nombre=getattr(user, "username", "") or "",
        descripcion=f"Inicio de sesión: {getattr(user, 'email', '') or ''}",
        usuario=user,
    )
