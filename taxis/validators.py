"""
validators.py
Validador personalizado de contraseñas:
- Controla longitud mínima.
- Integra con el sistema de validadores de Django.
"""

from django.core.exceptions import ValidationError          # Excepción estándar de validación.
from django.utils.translation import gettext as _           # Soporte para mensajes traducibles.


class CustomMinLengthValidator:
    """
    Validador de longitud mínima para contraseñas.

    Uso típico (en settings.AUTH_PASSWORD_VALIDATORS):
    {
        'NAME': 'taxis.validators.CustomMinLengthValidator',
        'OPTIONS': {'min_length': 6},
    }
    """

    def __init__(self, min_length=6):
        """
        Inicializa el validador con una longitud mínima dada.
        Por defecto, 6 caracteres.
        """
        self.min_length = min_length

    def validate(self, password, user=None):
        """
        Método que Django llama al validar una contraseña.

        - password: contraseña en texto plano.
        - user: instancia de usuario (puede ser None).

        Si la longitud de la contraseña es menor al mínimo,
        lanza ValidationError con un mensaje corto.
        """
        if len(password or "") < self.min_length:
            # Mensaje corto, en una sola línea, traducible.
            raise ValidationError(
                _("Mínimo %(min_length)d caracteres."),
                code="password_too_short",
                params={"min_length": self.min_length},
            )

    def get_help_text(self):
        """
        Texto de ayuda que Django mostrará donde corresponda
        (por ejemplo, en formularios de cambio de contraseña).
        """
        return _("La contraseña debe tener al menos %(min_length)d caracteres.") % {
            "min_length": self.min_length
        }
