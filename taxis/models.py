from django.db import models
from datetime import date, timedelta
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UbicacionGeografica(models.Model):
    ciudad = models.CharField(max_length=100)
    estado = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    sector = models.CharField(max_length=100)
    nro_casa = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.ciudad}, {self.estado}, {self.municipio}, {self.sector}, {self.nro_casa}"


class Conductor(models.Model):
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    cedula_identidad = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    ubicacion = models.OneToOneField(UbicacionGeografica, on_delete=models.CASCADE, null=True, blank=True)
    telefono = models.CharField(max_length=20)

    pago_patente_realizado = models.BooleanField(default=False)
    fecha_pago_patente = models.DateField(null=True, blank=True)

    def edad(self):
        if self.fecha_nacimiento:
            hoy = date.today()
            edad = hoy.year - self.fecha_nacimiento.year - ((hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
            return edad
        return None

    @property
    def patente_vigente(self):
        if not self.pago_patente_realizado or not self.fecha_pago_patente:
            return False
        return date.today() <= self.fecha_pago_patente + timedelta(days=30)

    def __str__(self):
        return f"{self.nombre} {self.apellido} - CI: {self.cedula_identidad}"


class Taxi(models.Model):
    placa = models.CharField(max_length=15, unique=True)
    modelo = models.CharField(max_length=100)
    nombre_vehiculo = models.CharField(max_length=100)
    anio = models.PositiveIntegerField()
    conductor = models.ForeignKey(Conductor, on_delete=models.CASCADE, related_name='taxis')

    def __str__(self):
        return f"{self.nombre_vehiculo} ({self.placa}) - Conductor: {self.conductor.nombre}"


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("El nombre de usuario es obligatorio")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")
        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('presidente', 'Presidente'),
        ('asociado', 'Asociado'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='asociado')

    objects = CustomUserManager()

    def __str__(self):
        return self.username
