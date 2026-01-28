"""
models.py
Modelos de la aplicación 'taxis' con validación de seguridad y soporte responsive.
ACTUALIZADO: Municipios, Parroquias y Códigos Postales como CharField con choices
"""


from datetime import date
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
import uuid, re
from datetime import timedelta


# IMPORTANTE: Importamos el validador de archivos (Asegúrate de que validators.py exista)
from .validators import validar_archivo_seguro

# ==================== CHOICES ====================
CEDULA_PREFIJO_CHOICES = [
    ('V', 'Venezolano'),
    ('E', 'Extranjero'),
]

RIF_PREFIJO_CHOICES = [
    ('V', 'Venezolano'),
    ('E', 'Extranjero'),
    ('J', 'Jurídica'),
    ('P', 'Personal'),
    ('G', 'Gobierno'),
]

SEXO_CHOICES = [
    ('M', 'Masculino'),
    ('F', 'Femenino'),
    ('O', 'Otro'),
]

ESTADO_CIVIL_CHOICES = [
    ('soltero', 'Soltero/a'),
    ('casado', 'Casado/a'),
    ('divorciado', 'Divorciado/a'),
    ('viudo', 'Viudo/a'),
    ('union_estable', 'Unión Estable de Hecho'),
]
# ====================================================
# Validadores Regex para Modelos
solo_numeros_regex = RegexValidator(r'^\d+$', 'Solo se permiten números.')
# ====================================================================
# USUARIOS (AUTH)
# ====================================================================


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
        return self.create_user(username, email, password, **extra_fields)



class CustomUser(AbstractUser):
    ROLE_CHOICES = [("presidente", "Presidente")]
    SEXO_CHOICES = [("M", "Masculino"), ("F", "Femenino")]


    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="asociado")
    is_email_verified = models.BooleanField(default=False)


    # Datos Personales
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, null=True, blank=True)


    # Teléfono
    phone_country = models.CharField(max_length=10, blank=True, null=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        validators=[solo_numeros_regex],
    )
    is_phone_verified = models.BooleanField(default=False)


    # Avatar
    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    
    objects = CustomUserManager()

    cedula_identidad = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        unique=True,
        help_text="Cédula única para presidentes"
    )
    
    # ✅ NUEVO
    rif = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        unique=True,
        help_text="RIF único para presidentes"
    )
# ====================================================================
# CONFIGURACIÓN Y LEGAL
# ====================================================================


class ConfiguracionGlobal(models.Model):
    tasa_bcv = models.DecimalField(
        max_digits=10, decimal_places=2, default=50.00, help_text="Tasa actual del BCV"
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)


    def save(self, *args, **kwargs):
        if not self.pk and ConfiguracionGlobal.objects.exists():
            return
        super(ConfiguracionGlobal, self).save(*args, **kwargs)


    def __str__(self):
        return f"Configuración (Tasa: {self.tasa_bcv})"


    @classmethod
    def get_tasa(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj.tasa_bcv



class DocumentoLegal(models.Model):
    titulo = models.CharField(max_length=100)
    archivo = models.FileField(
        upload_to="legal/repositorio/", validators=[validar_archivo_seguro]
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    descripcion = models.TextField(blank=True, null=True)


    def __str__(self):
        return self.titulo



class ConfiguracionCooperativa(models.Model):
    monto_cuota_usd = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    ultima_actualizacion = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name = "Configuración Legacy"
        verbose_name_plural = "Configuraciones Legacy"


# ====================================================================
# CORE: UBICACIÓN GEOGRÁFICA
# ====================================================================

# 📍 CONSTANTES PARA UBICACIÓN (15 Municipios, 39 Parroquias, 20 Códigos Postales)

# ✅ MUNICIPIOS (15 TOTAL)
MUNICIPIOS_CHOICES = [
    ("Juan Germán Roscio", "Juan Germán Roscio"),
    ("Francisco de Miranda", "Francisco de Miranda"),
    ("Leonardo Infante", "Leonardo Infante"),
    ("José Tadeo Monagas", "José Tadeo Monagas"),
    ("Julián Mellado", "Julián Mellado"),
    ("Ortiz", "Ortiz"),
    ("San Gerónimo de Guayabal", "San Gerónimo de Guayabal"),
    ("Juan José Rondón", "Juan José Rondón"),
    ("Pedro Zaraza", "Pedro Zaraza"),
    ("José Félix Ribas", "José Félix Ribas"),
    ("Santa María de Ipire", "Santa María de Ipire"),
    ("Camaguán", "Camaguán"),
    ("El Socorro", "El Socorro"),
    ("Chaguaramas", "Chaguaramas"),
    ("San José de Guaribe", "San José de Guaribe"),
]

# ✅ PARROQUIAS (39 TOTAL)
PARROQUIAS_CHOICES = [
    # Juan Germán Roscio (3)
    ("San Juan de los Morros (Capital)", "San Juan de los Morros (Capital)"),
    ("Parapara", "Parapara"),
    ("Cantagallo", "Cantagallo"),
    # Francisco de Miranda (4)
    ("Capital Urbana Calabozo", "Capital Urbana Calabozo"),
    ("El Calvario", "El Calvario"),
    ("El Rastro", "El Rastro"),
    ("Guardatinajas", "Guardatinajas"),
    # Leonardo Infante (2)
    ("Valle de la Pascua (Capital)", "Valle de la Pascua (Capital)"),
    ("Espino", "Espino"),
    # José Tadeo Monagas (7)
    ("Altagracia de Orituco (Capital)", "Altagracia de Orituco (Capital)"),
    ("San Rafael de Orituco", "San Rafael de Orituco"),
    ("San Francisco Javier de Lezama", "San Francisco Javier de Lezama"),
    ("Paso Real de Macaira", "Paso Real de Macaira"),
    ("Carlos Soublette", "Carlos Soublette"),
    ("San Francisco de Macaira", "San Francisco de Macaira"),
    ("Libertad de Orituco", "Libertad de Orituco"),
    # Julián Mellado (2)
    ("El Sombrero (Capital)", "El Sombrero (Capital)"),
    ("Sosa", "Sosa"),
    # Ortiz (4)
    ("Ortiz (Capital)", "Ortiz (Capital)"),
    ("San Francisco de Tiznados", "San Francisco de Tiznados"),
    ("San José de Tiznados", "San José de Tiznados"),
    ("San Lorenzo de Tiznados", "San Lorenzo de Tiznados"),
    # San Gerónimo de Guayabal (2)
    ("Guayabal (Capital)", "Guayabal (Capital)"),
    ("Cazorla", "Cazorla"),
    # Juan José Rondón (3)
    ("Las Mercedes del Llano (Capital)", "Las Mercedes del Llano (Capital)"),
    ("Cabruta", "Cabruta"),
    ("Santa Rita de Manapire", "Santa Rita de Manapire"),
    # Pedro Zaraza (2)
    ("Zaraza (Capital)", "Zaraza (Capital)"),
    ("San José de Unare", "San José de Unare"),
    # José Félix Ribas (2)
    ("Tucupido (Capital)", "Tucupido (Capital)"),
    ("San Rafael de Laya", "San Rafael de Laya"),
    # Santa María de Ipire (2)
    ("Santa María de Ipire (Capital)", "Santa María de Ipire (Capital)"),
    ("Altamira", "Altamira"),
    # Camaguán (3)
    ("Camaguán (Capital)", "Camaguán (Capital)"),
    ("Puerto Miranda", "Puerto Miranda"),
    ("Uverito", "Uverito"),
    # El Socorro (1)
    ("El Socorro (Capital)", "El Socorro (Capital)"),
    # Chaguaramas (1)
    ("Chaguaramas (Capital)", "Chaguaramas (Capital)"),
    # San José de Guaribe (1)
    ("San José de Guaribe (Capital)", "San José de Guaribe (Capital)"),
]

CODIGOS_POSTALES_CHOICES = [
    ("2301", "2301"),
    ("2302", "2302"),
    ("2303", "2303"),
    ("2304", "2304"),
    ("2305", "2305"),
    ("2306", "2306"),
    ("2311", "2311"),
    ("2312", "2312"),
    ("2313", "2313"),
    ("2314", "2314"),
    ("2315", "2315"),
    ("2316", "2316"),
    ("2317", "2317"),
    ("2319", "2319"),
    ("2320", "2320"),
    ("2322", "2322"),
    ("2323", "2323"),
    ("2324", "2324"),
    ("2327", "2327"),
    ("2328", "2328"),
    ("2330", "2330"),
    ("2332", "2332"),
    ("2350", "2350"),
    ("2354", "2354"),
    ("2355", "2355"),
    ("2356", "2356"),
    ("2358", "2358"),
]


class UbicacionGeografica(models.Model):
    """
    Ubicación geográfica del conductor. Utiliza CharField con choices
    para municipios, parroquias y códigos postales (data hardcodeada en constantes).
    """
    estado = models.CharField(max_length=100, default="Guárico")
    
    # Municipio: CharField con choices (15 opciones)
    municipio = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Municipio del estado Guárico"
    )
    
    # Parroquia: CharField con choices (39 opciones)
    parroquia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Parroquia del municipio seleccionado"
    )
    
    # Localidad: CharField libre (para búsquedas/filtros en JS)
    localidad = models.CharField(max_length=100, null=True, blank=True)
    
    # Dirección
    sector = models.CharField(max_length=30, null=True, blank=True)
    calle_avenida = models.CharField(max_length=30, null=True, blank=True)
    numero_casa = models.CharField(max_length=10, null=True, blank=True)
    
    # Zona Postal: CharField con choices (20 códigos únicos)
    zona_postal = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Código postal de la localidad"
    )


    def __str__(self):
        return f"{self.sector}, {self.municipio}"


# ====================================================================
# CONDUCTORES
# ====================================================================


class Conductor(models.Model):
    SEXO_CHOICES = [("M", "Masculino"), ("F", "Femenino")]
    ESTADO_CIVIL_CHOICES = [
        ("soltero", "Soltero(a)"),
        ("casado", "Casado(a)"),
        ("divorciado", "Divorciado(a)"),
        ("viudo", "Viudo(a)"),
        ("union", "Unión estable de hecho"),
    ]
    CEDULA_PREFIJO_CHOICES = [("V", "V"), ("E", "E")]
    RIF_PREFIJO_CHOICES = [("V", "V"), ("J", "J"), ("E", "E"), ("P", "P"), ("G", "G")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conductor",
        null=True,
        blank=True,
    )

    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fechanacimiento = models.DateField()
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    estadocivil = models.CharField(max_length=20, choices=ESTADO_CIVIL_CHOICES)

    cedula_prefijo = models.CharField(max_length=1, choices=CEDULA_PREFIJO_CHOICES, default="V")
    cedula_identidad = models.CharField(max_length=10, validators=[solo_numeros_regex])
    cedula_archivo_frente = models.FileField(
        upload_to="documentos/cedulas/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
        verbose_name="Cédula - Frente",
    )
    cedula_archivo_reverso = models.FileField(
        upload_to="documentos/cedulas/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
        verbose_name="Cédula - Reverso",
    )
    cedula_vencimiento = models.DateField(null=True, blank=True)

    rif_prefijo = models.CharField(max_length=1, choices=RIF_PREFIJO_CHOICES, default="V")
    rif = models.CharField(max_length=15, validators=[solo_numeros_regex])
    rif_archivo = models.FileField(
        upload_to="documentos/rif/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    rif_vencimiento = models.DateField(null=True, blank=True)

    email = models.EmailField(unique=True, max_length=30)

    # Principal obligatorio, los otros dos opcionales (blank=True ya lo garantiza en forms) [web:85]
    telefono_principal = models.CharField(max_length=20, unique=True, validators=[solo_numeros_regex])
    telefono_secundario = models.CharField(max_length=20, null=True, blank=True, validators=[solo_numeros_regex])
    telefono_fijo = models.CharField(max_length=20, null=True, blank=True, validators=[solo_numeros_regex])

    ubicacion = models.OneToOneField(
        UbicacionGeografica,
        on_delete=models.CASCADE,
        related_name="conductor",
        null=True,
        blank=True,
    )

    # Ya es opcional a nivel de modelo/form por blank=True [web:85]
    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )

    creado_en = models.DateTimeField(default=timezone.now)
    estado = models.CharField(
        max_length=10,
        default="activo",
        choices=[("activo", "Activo"), ("inactivo", "Inactivo")],
    )

    class Meta:
        ordering = ["apellidos", "nombres"]

    def _solo_digitos(self, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        return re.sub(r"\D", "", value)

    def clean(self):
        super().clean()
        # Normaliza para que el validador "solo números" no falle por espacios/guiones.
        self.telefono_principal = self._solo_digitos(self.telefono_principal)
        self.telefono_secundario = self._solo_digitos(self.telefono_secundario)
        self.telefono_fijo = self._solo_digitos(self.telefono_fijo)

    def save(self, *args, **kwargs):
        # Asegura normalización siempre, incluso si no pasan por un ModelForm.
        self.full_clean(exclude=None)
        return super().save(*args, **kwargs)

    @property
    def fecha_ingreso(self):
        return self.creado_en

    @property
    def activo(self):
        return self.estado == "activo"

    @property
    def tiene_deudas_pendientes(self):
        return self.deudas.filter(pagada=False).exists()

    def __str__(self):
        return f"{self.nombres} {self.apellidos} - {self.cedula_prefijo}-{self.cedula_identidad}"
# ====================================================================
# VEHÍCULOS (MODELO ACTUALIZADO CON NUEVOS CAMPOS)
# ====================================================================


class Vehiculo(models.Model):
    # FASE 1: BÁSICOS
    CONDICION_CHOICES = [("operativo", "Operativo"), ("inoperativo", "Inoperativo")]
    CASCO_CHOICES = [(str(i), str(i)) for i in range(1, 51)]


    conductor = models.ForeignKey(
        Conductor, on_delete=models.CASCADE, related_name="vehiculos"
    )
    marca = models.CharField(max_length=15)
    modelo = models.CharField(max_length=15)
    color = models.CharField(max_length=15)
    anio = models.PositiveIntegerField()
    placa = models.CharField(max_length=15, unique=True)
    serial_niv = models.CharField(max_length=20, unique=True)
    numero_casco = models.CharField(
        max_length=2, choices=CASCO_CHOICES, unique=True
    )
    condicion = models.CharField(
        max_length=12, choices=CONDICION_CHOICES, default="operativo"
    )
    foto = models.ImageField(
       upload_to="vehiculos/",
       validators=[validar_archivo_seguro],
    )



    # FASE 2: TÉCNICOS
    bateria_amperaje = models.CharField(max_length=10, verbose_name="Amperaje Batería")
    aceite_viscosidad = models.CharField(
        max_length=10, verbose_name="Viscosidad Aceite", default="15W40"
    )
    combustible_litros = models.CharField(
        max_length=10, verbose_name="Litros Tanque"
    )
    cauchos_medida = models.CharField(
        max_length=10, verbose_name="Medida Cauchos"
    )
    diametro_rin = models.CharField(
        max_length=5, verbose_name="Diámetro Rin", default="14"
    )


    aceite_ultimo_cambio = models.DateField(null=True, blank=True)
    kit_tiempo_cambio = models.DateField(null=True, blank=True)
    combustible_tipo = models.CharField(
        max_length=20,
        choices=[("Gasolina", "Gasolina"), ("Gasoil", "Gasoil"), ("Gas", "Gas GNV")],
        default="Gasolina",
    )
    kilometraje_actual = models.PositiveIntegerField(default=0)
    capacidad = models.PositiveIntegerField(default=5)
    tipo_unidad = models.CharField(max_length=20, default="Sedan")


    # FASE 3: LEGAL
    patente_archivo = models.FileField(
        upload_to="documentos/vehiculos/patente/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    patente_vencimiento = models.DateField(null=True, blank=True)


    licencia_archivo = models.FileField(
        upload_to="documentos/vehiculos/licencia/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    licencia_vencimiento = models.DateField(null=True, blank=True)


    rcv_archivo = models.FileField(
        upload_to="documentos/vehiculos/rcv/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    rcv_vencimiento = models.DateField(null=True, blank=True)


    medico_archivo = models.FileField(
        upload_to="documentos/vehiculos/medico/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    medico_vencimiento = models.DateField(null=True, blank=True)


    circulacion_archivo = models.FileField(
        upload_to="documentos/vehiculos/otros/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    registro_archivo = models.FileField(
        upload_to="documentos/vehiculos/otros/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )


    class Meta:
        ordering = ["numero_casco", "placa"]


    def __str__(self):
        return f"Unidad {self.numero_casco}: {self.marca} {self.modelo} ({self.placa})"


# ====================================================================
# FINANZAS Y AUDITORÍA
# ====================================================================


class Deuda(models.Model):
    conductor = models.ForeignKey(
        Conductor, on_delete=models.CASCADE, related_name="deudas"
    )
    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveIntegerField()
    monto_bs = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    concepto = models.CharField(max_length=100, default="Cuota Mensual")
    pagada = models.BooleanField(default=False)
    fecha_emision = models.DateField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True)


    class Meta:
        unique_together = ("conductor", "mes", "anio")


    def __str__(self):
        return f"Deuda {self.mes}/{self.anio} - {self.conductor.nombres}"



class Pago(models.Model):
    deuda = models.ForeignKey(
        Deuda, on_delete=models.CASCADE, related_name="pagos"
    )
    monto_bs = models.DecimalField(max_digits=20, decimal_places=2)
    tasa_bcv = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    fecha_pago = models.DateField(default=date.today)
    comprobante = models.FileField(
        upload_to="pagos/comprobantes/",
        null=True,
        blank=True,
        validators=[validar_archivo_seguro],
    )
    creado_el = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"Pago {self.deuda} - Bs. {self.monto_bs}"



class MovimientoAudit(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # ← USA ESTO
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='movimientos'
    )
    # Acción
    ACCION_CHOICES = [
        ('login', 'Inicio de Sesión'),
        ('logout', 'Cierre de Sesión'),
        ('crear', 'Crear'),
        ('editar', 'Editar'),
        ('eliminar', 'Eliminar'),
        ('ver', 'Ver Detalle'),
        ('listar', 'Listar'),
        ('pago_registrado', 'Registrar Pago'),
        ('masivo', 'Acción Masiva'),
        ('configurar', 'Configuración'),
        ('exportar', 'Exportar Reporte'),
    ]
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    
    # Contexto
    modulo = models.CharField(max_length=50)  # 'afiliados', 'finanzas', 'dt5'
    objeto_tipo = models.CharField(max_length=50)  # 'Conductor', 'Vehiculo', 'Pago'
    objeto_id = models.PositiveIntegerField(null=True, blank=True)
    objeto_nombre = models.CharField(max_length=200, blank=True)  # Cache nombre
    descripcion = models.TextField()  # Detalle completo
    
    # Cambios (JSON para diffs)
    cambios_antes = models.JSONField(default=dict, blank=True, null=True)
    cambios_despues = models.JSONField(default=dict, blank=True, null=True)
    
    # Fecha/Hora EXACTA
    fecha = models.DateTimeField(default=timezone.now)
    fecha_formato = models.CharField(max_length=50, blank=True)  # "21/01/2026 22:36"
    
    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['usuario', '-fecha']),
            models.Index(fields=['modulo', '-fecha']),
            models.Index(fields=['accion']),
        ]


    def __str__(self):
        return f"[{self.fecha}] {self.usuario} - {self.accion} en {self.modulo}"



class EmailVerificationCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_codes",
    )
    code = models.CharField(max_length=6)
    email_type = models.CharField(max_length=30, default="primary")
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(blank=True, null=True)
    attempt_count = models.PositiveIntegerField(default=0)
    resend_count = models.PositiveIntegerField(default=0)
    last_resend_at = models.DateTimeField(blank=True, null=True)



class EmailSendLog(models.Model):
    email = models.EmailField()
    date = models.DateField()
    email_type = models.CharField(max_length=30, default="primary")
    count = models.PositiveIntegerField(default=0)


    class Meta:
        unique_together = ("email", "date", "email_type")



class VerificationAttemptLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_attempts",
    )
    method = models.CharField(max_length=50)
    code = models.CharField(max_length=6, blank=True)
    result = models.CharField(max_length=20)
    reason = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)


# ====================================================================
# FINANZAS SIMPLIFICADAS (NUEVO MÓDULO)
# ====================================================================


class ConfiguracionFinanzas(models.Model):
    monto_cuota_usd = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    dia_vencimiento = models.IntegerField(default=5)
    descripcion = models.CharField(
        max_length=255, default="Cuota mensual cooperativa"
    )
    actualizado_en = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name = "Configuración de Finanzas"
        verbose_name_plural = "Configuraciones de Finanzas"


    def __str__(self):
        return f"Configuración: ${self.monto_cuota_usd} (Vence el {self.dia_vencimiento})"


    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj



class PagoMensual(models.Model):
    """
    Registra los pagos mensuales de cooperativa realizados por afiliados.
    Los pagos mayores a 5 años se archivan automáticamente.
    """


    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.PROTECT,
        related_name="pagos_mensuales",
        help_text="Afiliado que realizó el pago",
    )
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_vehiculo",
        help_text="Vehículo asociado al pago",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,           # ← aquí está la clave
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_registrados",
        help_text="Usuario que registró el pago",
    )


    # PERIODO
    mes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Mes del pago (1-12)",
    )
    anio = models.PositiveIntegerField(
        validators=[MinValueValidator(2020)],
        help_text="Año del pago",
    )


    # DATOS FINANCIEROS
    monto_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Monto en dólares (USD)",
    )
    fecha_pago = models.DateField(help_text="Fecha en que se realizó el pago")


    # COMPROBANTE
    comprobante = models.ImageField(
        upload_to="comprobantes/pagos/",
        blank=True,
        null=True,
        help_text="Captura de pago móvil, transferencia, etc.",
    )


    # METADATOS
    notas = models.TextField(blank=True, help_text="Observaciones adicionales")
    creado_en = models.DateTimeField(auto_now_add=True)


    # ARCHIVADO
    archivado = models.BooleanField(
        default=False, help_text="Pagos archivados (mayores a 5 años)"
    )
    fecha_archivado = models.DateTimeField(
        null=True, blank=True, help_text="Fecha en que se archivó el registro"
    )


    # CACHE
    conductor_nombre_cache = models.CharField(max_length=200, blank=True)
    conductor_cedula_cache = models.CharField(max_length=20, blank=True)


    class Meta:
        ordering = ["-anio", "-mes", "-fecha_pago"]
        verbose_name = "Pago Mensual"
        verbose_name_plural = "Pagos Mensuales"
        indexes = [
            models.Index(fields=["archivado", "anio", "mes"]),
            models.Index(fields=["conductor", "archivado"]),
            models.Index(fields=["fecha_pago"]),
        ]
        unique_together = [["conductor", "mes", "anio"]]


    def __str__(self):
        return f"{self.conductor_nombre_cache} - {self.get_nombre_mes()} {self.anio} (${self.monto_usd})"


    def save(self, *args, **kwargs):
        """Actualiza el caché de conductor al guardar"""
        if self.conductor:
            self.conductor_nombre_cache = (
                f"{self.conductor.nombres} {self.conductor.apellidos}"
            )
            self.conductor_cedula_cache = (
                f"{self.conductor.cedula_prefijo}-{self.conductor.cedula_identidad}"
            )
        super().save(*args, **kwargs)


    def get_nombre_mes(self):
        """Retorna el nombre del mes en español"""
        meses = [
            "",
            "Enero",
            "Febrero",
            "Marzo",
            "Abril",
            "Mayo",
            "Junio",
            "Julio",
            "Agosto",
            "Septiembre",
            "Octubre",
            "Noviembre",
            "Diciembre",
        ]
        return meses[self.mes] if 1 <= self.mes <= 12 else "Desconocido"


class PendingPresidentRegistration(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


    username = models.CharField(max_length=150)


    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)


    email = models.EmailField()
    phone_country = models.CharField(max_length=10, blank=True, default="")
    phone_number = models.CharField(max_length=20)


    fecha_nacimiento = models.DateField()
    sexo = models.CharField(max_length=1)


    password_hash = models.CharField(max_length=128)


    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["email"], name="uniq_pending_pres_email"),
            models.UniqueConstraint(fields=["phone_number"], name="uniq_pending_pres_phone"),
        ]


    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)


    def is_expired(self):
        return timezone.now() > self.expires_at