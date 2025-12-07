"""
models.py
Modelos de la aplicación 'taxis':
- Ubicación geográfica
- Conductor y Taxi
- Usuario personalizado (CustomUser)
- Códigos de verificación por correo
- Log de intentos de verificación
- Log de envíos diarios de correo
"""

from datetime import date, timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager  # Base para usuario personalizado.
from django.db import models                                           # Clases base de modelos.


class UbicacionGeografica(models.Model):
    """
    Representa la dirección física de un conductor.
    Se guarda separada para poder reutilizar y normalizar datos de ubicación.
    """
    ciudad = models.CharField(max_length=100)       # Nombre de la ciudad.
    estado = models.CharField(max_length=100)       # Estado o provincia.
    municipio = models.CharField(max_length=100)    # Municipio.
    sector = models.CharField(max_length=100)       # Sector o barrio.
    nro_casa = models.CharField(max_length=20)      # Número de casa o lote.

    def __str__(self):
        """Devuelve la dirección leíble en una sola cadena."""
        return f"{self.ciudad}, {self.estado}, {self.municipio}, {self.sector}, {self.nro_casa}"


class Conductor(models.Model):
    """
    Representa a un conductor asociado a la cooperativa.
    Incluye datos personales, contacto y estado de pago de patente.
    """
    SEXO_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
    ]

    nombre = models.CharField(max_length=100)                    # Nombre del conductor.
    apellido = models.CharField(max_length=100)                  # Apellido del conductor.
    cedula_identidad = models.CharField(
        max_length=20,
        unique=True,                                             # No se permite cédulas repetidas.
    )
    fecha_nacimiento = models.DateField(null=True, blank=True)   # Fecha de nacimiento (opcional).
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)  # Sexo (M/F).
    ubicacion = models.OneToOneField(
        UbicacionGeografica,
        on_delete=models.CASCADE,                                # Si se borra la ubicación, se borra el conductor.
        null=True,
        blank=True,
    )
    telefono = models.CharField(max_length=20)                   # Teléfono de contacto.

    pago_patente_realizado = models.BooleanField(default=False)  # Indica si pagó la patente.
    fecha_pago_patente = models.DateField(null=True, blank=True) # Fecha del último pago de patente.

    def edad(self):
        """
        Calcula la edad actual del conductor a partir de su fecha de nacimiento.
        Devuelve None si no hay fecha registrada.
        """
        if self.fecha_nacimiento:
            hoy = date.today()
            edad = (
                hoy.year
                - self.fecha_nacimiento.year
                - (
                    (hoy.month, hoy.day)
                    < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
                )
            )
            return edad
        return None

    @property
    def patente_vigente(self):
        """
        Indica si la patente está vigente.
        Se considera vigente durante 30 días desde la fecha de pago.
        """
        if not self.pago_patente_realizado or not self.fecha_pago_patente:
            return False
        return date.today() <= self.fecha_pago_patente + timedelta(days=30)

    def __str__(self):
        """Representación de texto del conductor."""
        return f"{self.nombre} {self.apellido} - CI: {self.cedula_identidad}"


class Taxi(models.Model):
    """
    Representa un vehículo (taxi) asociado a un conductor.
    """
    placa = models.CharField(max_length=15, unique=True)  # Placa única del vehículo.
    modelo = models.CharField(max_length=100)             # Modelo del vehículo.
    nombre_vehiculo = models.CharField(max_length=100)    # Nombre o alias del vehículo.
    anio = models.PositiveIntegerField()                  # Año del vehículo.
    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.CASCADE,                         # Si se borra el conductor, se borran sus taxis.
        related_name="taxis",                             # Acceso inverso: conductor.taxis.all()
    )

    def __str__(self):
        """Representación de texto del taxi."""
        return f"{self.nombre_vehiculo} ({self.placa}) - Conductor: {self.conductor.nombre}"


class CustomUserManager(BaseUserManager):
    """
    Manager personalizado para el modelo de usuario.
    Define la creación de usuarios normales y superusuarios.
    """

    def create_user(self, username, email=None, password=None, **extra_fields):
        """
        Crea y guarda un usuario regular con nombre de usuario y correo.
        Por defecto, el usuario queda inactivo hasta verificar el correo.
        """
        if not username:
            raise ValueError("El nombre de usuario es obligatorio")
        email = self.normalize_email(email)
        # Crea la instancia de usuario con los campos extra.
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)  # Encripta la contraseña.
        if extra_fields.get("is_active") is None:
            # Por defecto, se crea inactivo (a la espera de verificación).
            user.is_active = False
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """
        Crea y guarda un superusuario con privilegios de staff y superusuario.
        """
        extra_fields.setdefault("is_staff", True)       # Marca como personal administrativo.
        extra_fields.setdefault("is_superuser", True)   # Marca como superusuario.
        extra_fields.setdefault("is_active", True)      # Activo desde el inicio.

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")

        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    Usuario personalizado para la app:
    - Extiende AbstractUser.
    - Agrega el rol (presidente / asociado).
    - Campos de verificación de correo y teléfono.
    """
    ROLE_CHOICES = [
        ("presidente", "Presidente"),
        ("asociado", "Asociado"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="asociado",         # Rol por defecto para nuevos usuarios.
    )

    # Estado de verificación.
    is_email_verified = models.BooleanField(default=False)      # Indica si el correo fue verificado.
    phone_number = models.CharField(max_length=20, blank=True, null=True)  # Número de teléfono (opcional).
    is_phone_verified = models.BooleanField(default=False)      # Estado de verificación telefónica (hoy no se usa).

    # Asocia el manager personalizado.
    objects = CustomUserManager()

    def __str__(self):
        """
        Representación de texto del usuario.
        Prioriza mostrar nombre/apellido y rol de presidente si aplica.
        """
        nombre = (self.first_name or "").strip()
        apellido = (self.last_name or "").strip()
        if self.role == "presidente":
            if nombre or apellido:
                return f"Presidente {nombre} {apellido}".strip()
            return f"Presidente ({self.email})".strip()
        if nombre or apellido:
            return f"{nombre} {apellido}".strip()
        return self.username or self.email or "Usuario"


class EmailVerificationCode(models.Model):
    """
    Almacena códigos de verificación enviados por correo electrónico.
    Se usa tanto para:
    - verificación de registro (email_type='primary'),
    - restablecimiento de contraseña (email_type='password_reset', aunque no esté en choices).
    """
    EMAIL_TYPE_CHOICES = [
        ("primary", "Correo principal"),  # Tipo principal usado en el registro.
        # Aunque no aparezca aquí, el sistema también usa 'password_reset' en email_type.
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,          # Si se borra el usuario, se borran sus códigos.
        related_name="email_codes",        # Acceso inverso: user.email_codes.all()
    )
    code = models.CharField(max_length=6)  # Código de 6 dígitos enviado al correo.
    email_type = models.CharField(
        max_length=30,
        choices=EMAIL_TYPE_CHOICES,        # Tipo de código (registro, etc.).
        default="primary",
    )

    created_at = models.DateTimeField()    # Fecha/hora en que se generó el código.
    expires_at = models.DateTimeField()    # Fecha/hora de expiración del código.
    is_used = models.BooleanField(default=False)  # Indica si el código ya fue usado.
    used_at = models.DateTimeField(blank=True, null=True)  # Momento en que se usó el código.

    attempt_count = models.PositiveIntegerField(default=0)  # Intentos de validación consumidos.
    resend_count = models.PositiveIntegerField(default=0)   # Reenvíos realizados de este código.
    last_resend_at = models.DateTimeField(blank=True, null=True)  # Última vez que se reenvió.

    def __str__(self):
        """Representación de texto del código de verificación."""
        return f"{self.user.username} - {self.email_type} - {self.code}"


class VerificationAttemptLog(models.Model):
    """
    Registra los intentos de verificación (principalmente de email).
    Permite auditar:
    - método usado,
    - resultado,
    - IP y User-Agent de quien hizo el intento.
    """
    METHOD_CHOICES = [
        ("email_primary", "Email principal"),
        # Antes se usaba también 'sms'; ya no se usa SMS.
    ]
    RESULT_CHOICES = [
        ("success", "Éxito"),
        ("invalid_code", "Código inválido"),
        ("expired", "Código expirado"),
        ("too_many_attempts", "Demasiados intentos"),
        ("resend_blocked", "Reenvío bloqueado"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,              # Si se borra el usuario, se borran sus logs.
        related_name="verification_attempts",  # Acceso inverso: user.verification_attempts.all()
    )
    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,                # Método de verificación usado.
    )
    code = models.CharField(
        max_length=6,
        blank=True,                            # Código que se intentó (si aplica).
    )
    result = models.CharField(
        max_length=30,
        choices=RESULT_CHOICES,                # Resultado del intento.
    )
    reason = models.TextField(
        blank=True,                            # Detalle adicional del resultado.
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,                            # IP desde donde se hizo el intento.
    )
    user_agent = models.TextField(
        blank=True,                            # User-Agent del cliente (navegador/dispositivo).
    )
    created_at = models.DateTimeField(
        auto_now_add=True,                     # Fecha/hora en que se registró el intento.
    )

    def __str__(self):
        """Representación de texto del log de verificación."""
        return f"{self.user.username} - {self.method} - {self.result} - {self.created_at}"


class EmailSendLog(models.Model):
    """
    Registra cuántos códigos se han enviado a un email en una fecha dada
    y para un TIPO de email (registro / reset).
    Permite tener límites diarios separados por tipo.
    """
    EMAIL_TYPE_CHOICES = [
        ("primary", "Correo principal / registro"),
        ("password_reset", "Restablecimiento de contraseña"),
    ]

    email = models.EmailField()                 # Correo de destino.
    date = models.DateField()                   # Día del registro.
    email_type = models.CharField(              # Tipo de código (registro o reset).
        max_length=30,
        choices=EMAIL_TYPE_CHOICES,
        default="primary",
    )
    count = models.PositiveIntegerField(default=0)  # Cantidad de códigos enviados ese día.

    class Meta:
        # Un registro por (email, fecha, tipo), no solo por email+fecha.
        unique_together = ("email", "date", "email_type")

    def __str__(self):
        """Representación de texto del log de envíos."""
        return f"{self.email} - {self.date} - {self.email_type} - {self.count}"
