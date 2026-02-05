"""
validators.py
Validadores personalizados para la aplicación:
1. Seguridad de contraseñas.
2. Seguridad de archivos subidos (extensión y tamaño).
"""

import os
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db.models.fields.files import FieldFile


# ====================================================================
# 1. VALIDADOR DE CONTRASEÑAS
# ====================================================================

class CustomMinLengthValidator:
    """
    Validador de longitud mínima para contraseñas.
    """
    def __init__(self, min_length=6):
        self.min_length = min_length

    def validate(self, password, user=None):
        if len(password or "") < self.min_length:
            raise ValidationError(
                _("Mínimo %(min_length)d caracteres."),
                code="password_too_short",
                params={"min_length": self.min_length},
            )

    def get_help_text(self):
        return _("La contraseña debe tener al menos %(min_length)d caracteres.") % {
            "min_length": self.min_length
        }


# ====================================================================
# 2. VALIDADOR DE ARCHIVOS (SEGURIDAD)
# ====================================================================

def validar_archivo_seguro(value):
    """
    Valida que el archivo subido sea seguro:
    - Extensión permitida: .pdf, .jpg, .jpeg, .png
    - Tamaño máximo: 10 MB

    Nota importante:
    - Cuando estás editando un modelo y NO subes un archivo nuevo, Django puede
      pasar un FieldFile ya guardado (committed). En ese caso NO debemos intentar
      leer value.size, porque si el archivo ya no existe en el storage (p.ej. en
      Render sin Disk) revienta con FileNotFoundError.
    """
    if not value:
        return

    # ✅ Si es un archivo ya guardado (edición sin re-subir), no revalidar tamaño/extensión aquí.
    # Evita el FileNotFoundError al hacer value.size sobre archivos faltantes.
    if isinstance(value, FieldFile) and getattr(value, "_committed", False):
        return

    # 1. Validar Extensión
    filename = getattr(value, "name", "") or ""
    ext = os.path.splitext(filename)[1]  # Obtiene la extensión (ej: .pdf)

    valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.PDF', '.JPG', '.JPEG', '.PNG']

    if not ext or (ext not in valid_extensions):
        raise ValidationError('Tipo de archivo no soportado. Solo se permiten: PDF, JPG o PNG.')

    # 2. Validar Tamaño (Max 10MB)
    limit_mb = 10
    try:
        filesize = value.size
    except Exception:
        raise ValidationError('No se pudo leer el archivo. Intenta seleccionarlo y subirlo de nuevo.')

    if filesize > limit_mb * 1024 * 1024:
        raise ValidationError(f"El archivo es muy pesado. El límite es {limit_mb}MB.")
