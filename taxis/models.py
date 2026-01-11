from datetime import date, timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UbicacionGeografica(models.Model):
    direccion = models.CharField(max_length=255, null=True, blank=True)
    calle_avenida = models.CharField(max_length=100, null=True, blank=True)
    sector = models.CharField(max_length=100, null=True, blank=True)
    numero_casa = models.CharField(max_length=20, null=True, blank=True)
    estado = models.CharField(max_length=100, null=True, blank=True)
    municipio = models.CharField(max_length=100, null=True, blank=True)
    parroquia = models.CharField(max_length=100, null=True, blank=True)
    zona_postal = models.CharField(max_length=10, null=True, blank=True)
    localidad = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return (
            f"{self.direccion}, {self.calle_avenida}, {self.sector}, "
            f"{self.numero_casa}, {self.parroquia}, {self.municipio}, "
            f"{self.estado}, {self.zona_postal}"
        )


class Conductor(models.Model):
    SEXO_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
    ]

    ESTADO_CIVIL_CHOICES = [
        ("soltero", "Soltero(a)"),
        ("casado", "Casado(a)"),
        ("divorciado", "Divorciado(a)"),
        ("viudo", "Viudo(a)"),
        ("union", "Unión estable de hecho"),
    ]

    user = models.OneToOneField(
        "CustomUser",
        on_delete=models.CASCADE,
        related_name="conductor",
        help_text="Usuario asociado al perfil de conductor.",
        null=True,
        blank=True,
    )

    cedula_identidad = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
    )
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    sexo = models.CharField(
        max_length=1,
        choices=SEXO_CHOICES,
        null=True,
        blank=True,
    )

    estado_civil = models.CharField(
        max_length=20,
        choices=ESTADO_CIVIL_CHOICES,
        null=True,
        blank=True,
    )

    # Número de RIF escrito (para búsquedas, reportes, etc.)
    rif = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Número de RIF tal cual aparece en el documento (Ej: V-12345678-0).",
    )

    # Documento digital del RIF (PDF o imagen)
    documento_rif = models.FileField(
        upload_to="documentos/rif/%Y/%m/",
        null=True,
        blank=True,
        help_text="Archivo PDF o imagen escaneada del RIF vigente.",
    )

    # Fecha de vencimiento exacta que aparece en el RIF
    fecha_vencimiento_rif = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha de vencimiento del RIF.",
    )

    # Teléfono del registro (principal). No se editará en Mi perfil.
    telefono_principal = models.CharField(max_length=20, null=True, blank=True)

    # Opcionales
    telefono_secundario = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Opcional.",
    )

    # Teléfono fijo (opcional)
    telefono_fijo = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Opcional.",
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        help_text="Foto de perfil del asociado.",
    )

    ubicacion = models.OneToOneField(
        UbicacionGeografica,
        on_delete=models.CASCADE,
        related_name="conductor",
        null=True,
        blank=True,
    )

    pago_patente_realizado = models.BooleanField(default=False)
    fecha_pago_patente = models.DateField(null=True, blank=True)

    def edad(self):
        if self.fecha_nacimiento:
            hoy = date.today()
            return (
                hoy.year
                - self.fecha_nacimiento.year
                - (
                    (hoy.month, hoy.day)
                    < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
                )
            )
        return None

    @property
    def patente_vigente(self):
        if not self.pago_patente_realizado or not self.fecha_pago_patente:
            return False
        return date.today() <= self.fecha_pago_patente + timedelta(days=30)

    def is_profile_complete(self):
        campos_obligatorios = [
            self.cedula_identidad,
            self.nombres,
            self.apellidos,
            self.fecha_nacimiento,
            self.sexo,
            self.estado_civil,
            self.rif,                  # debe existir número de RIF
            self.documento_rif,        # y el archivo cargado
            self.fecha_vencimiento_rif,# y su fecha de vencimiento
            self.telefono_principal,   # sigue siendo obligatorio (viene del registro)
        ]

        if not self.ubicacion:
            return False

        ubic = self.ubicacion
        campos_residencia = [
            ubic.direccion,
            ubic.calle_avenida,
            ubic.sector,
            ubic.numero_casa,
            ubic.estado,
            ubic.municipio,
            ubic.parroquia,
            ubic.zona_postal,
        ]

        return all(bool(campo) for campo in campos_obligatorios + campos_residencia)

    def __str__(self):
        return f"{self.nombres} {self.apellidos} - CI: {self.cedula_identidad}"


class Taxi(models.Model):
    placa = models.CharField(max_length=15, unique=True)
    modelo = models.CharField(max_length=100)
    nombre_vehiculo = models.CharField(max_length=100)
    anio = models.PositiveIntegerField()
    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.CASCADE,
        related_name="taxis",
    )

    def __str__(self):
        return f"{self.nombre_vehiculo} ({self.placa}) - Conductor: {self.conductor.nombres}"


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("El nombre de usuario es obligatorio")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        if extra_fields.get("is_active") is None:
            user.is_active = False
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")

        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("presidente", "Presidente"),
        ("asociado", "Asociado"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="asociado",
    )

    is_email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    is_phone_verified = models.BooleanField(default=False)

    # Campos nuevos para que el perfil pueda leerlos directo desde request.user
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(
        max_length=1,
        choices=Conductor.SEXO_CHOICES,
        null=True,
        blank=True,
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        help_text="Foto de perfil del usuario.",
    )

    objects = CustomUserManager()

    def __str__(self):
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
    EMAIL_TYPE_CHOICES = [
        ("primary", "Correo principal"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="email_codes",
    )
    code = models.CharField(max_length=6)
    email_type = models.CharField(
        max_length=30,
        choices=EMAIL_TYPE_CHOICES,
        default="primary",
    )

    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(blank=True, null=True)

    attempt_count = models.PositiveIntegerField(default=0)
    resend_count = models.PositiveIntegerField(default=0)
    last_resend_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.email_type} - {self.code}"


class VerificationAttemptLog(models.Model):
    METHOD_CHOICES = [
        ("email_primary", "Email principal"),
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
        on_delete=models.CASCADE,
        related_name="verification_attempts",
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    code = models.CharField(max_length=6, blank=True)
    result = models.CharField(max_length=30, choices=RESULT_CHOICES)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.method} - {self.result} - {self.created_at}"


class EmailSendLog(models.Model):
    EMAIL_TYPE_CHOICES = [
        ("primary", "Correo principal / registro"),
        ("password_reset", "Restablecimiento de contraseña"),
    ]

    email = models.EmailField()
    date = models.DateField()
    email_type = models.CharField(
        max_length=30,
        choices=EMAIL_TYPE_CHOICES,
        default="primary",
    )
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("email", "date", "email_type")

    def __str__(self):
        return f"{self.email} - {self.date} - {self.email_type} - {self.count}"
