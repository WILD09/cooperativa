"""
forms.py - Formularios de la aplicación 'taxis'

Incluye:
- Formularios CRUD para Conductor, UbicacionGeografica y Taxi
- Formularios de registro (Presidente/Asociado) con validación mejorada
- Formulario de verificación de código de 6 dígitos
- Formulario de autenticación por usuario/email
- Formulario de solicitud de restablecimiento de contraseña
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db import OperationalError, ProgrammingError
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from datetime import date

# Importamos los modelos desde models.py (NO se definen aquí)
from .models import Conductor, Taxi, CustomUser, UbicacionGeografica


# ====================================================================
# FORMULARIOS PARA CONDUCTOR, UBICACIÓN Y TAXI
# ====================================================================

class ConductorForm(forms.ModelForm):
    """
    Formulario perfil Conductor.
    Enfocado en la carga del documento RIF y su fecha de vencimiento.
    """

    solo_numeros = RegexValidator(r'^\d+$', 'Solo se permiten números.')

    # --- CÉDULA (visual) ---
    CEDULA_PREFIJO_CHOICES = [("V", "V"), ("E", "E")]
    cedula_prefijo = forms.ChoiceField(
        choices=CEDULA_PREFIJO_CHOICES,
        initial="V",
        label="Prefijo"
    )
    cedula_numero = forms.CharField(
        max_length=8,
        validators=[solo_numeros],
        label="Cédula"
    )

    # --- RIF (texto) ---
    rif = forms.CharField(
        label="Número de RIF",
        widget=forms.TextInput(attrs={"placeholder": "Ej: V-12345678-0"})
    )

    # --- FECHA (acepta dd/mm/aaaa y también yyyy-mm-dd) ---
    fecha_vencimiento_rif = forms.DateField(
        required=False,
        input_formats=["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"],
        widget=forms.TextInput(
            attrs={
                "class": "perfil-input js-editable date-mask",
                "placeholder": "dd/mm/aaaa",
                "autocomplete": "off",
            }
        ),
        label="Fecha de vencimiento",
    )

    class Meta:
        model = Conductor
        fields = [
            "cedula_identidad",      # oculto
            "estado_civil",
            "telefono_secundario",
            "telefono_fijo",
            "rif",
            "fecha_vencimiento_rif",
            "documento_rif",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ocultar campo real de cédula
        self.fields["cedula_identidad"].widget = forms.HiddenInput()

        # Estilos base
        for name, field in self.fields.items():
            if name != "documento_rif":
                field.widget.attrs.setdefault("class", "perfil-input js-editable")

        self.fields["cedula_prefijo"].widget.attrs["class"] = "perfil-select js-editable"

        # Input file
        self.fields["documento_rif"].widget.attrs.update({
            "class": "file-input-real",
            "accept": ".pdf, .jpg, .jpeg, .png",
        })

        # Bloqueo de cédula si ya existe
        if self.instance and self.instance.pk and getattr(self.instance, "cedula_identidad", None):
            self.fields["cedula_prefijo"].disabled = True
            self.fields["cedula_numero"].disabled = True

        # Precargar cédula visualmente
        ci = (getattr(self.instance, "cedula_identidad", "") or "").strip()
        if ci:
            ci_norm = ci.replace("-", "").replace(".", "").replace(" ", "").upper()
            if len(ci_norm) >= 2 and ci_norm[0].isalpha():
                self.initial["cedula_prefijo"] = ci_norm[0]
                self.initial["cedula_numero"] = ci_norm[1:]

    def clean(self):
        cleaned = super().clean()

        # Armar cédula real
        pref = cleaned.get("cedula_prefijo")
        num = cleaned.get("cedula_numero")
        if not (self.instance.pk and self.instance.cedula_identidad) and pref and num:
            cleaned["cedula_identidad"] = f"{pref}{num}"

        return cleaned

    def clean_rif(self):
        rif = (self.cleaned_data.get("rif") or "").upper().strip()

        if len(rif) < 10:
            raise forms.ValidationError(
                "El RIF parece incompleto. Debe tener al menos 10 caracteres (Ej: V-12345678-0)."
            )

        if rif and rif[0] not in ["V", "E", "J", "G", "P"]:
            raise forms.ValidationError("El RIF debe comenzar con V, E, J, G o P.")

        return rif

    def clean_fecha_vencimiento_rif(self):
        fecha = self.cleaned_data.get("fecha_vencimiento_rif")
        if fecha:
            if fecha < date.today():
                raise forms.ValidationError("El documento indicado ya está vencido. Por favor actualízalo.")

            if fecha.year > date.today().year + 10:
                raise forms.ValidationError("La fecha de vencimiento parece incorrecta (demasiado lejana).")

        return fecha


class UbicacionGeograficaForm(forms.ModelForm):
    """
    Formulario para la dirección/residencia del asociado.
    Se usa junto con ConductorForm en Mi perfil.
    """
    
    # Campo personalizado para localidad (no existe en el modelo, es solo para captura)
    localidad = forms.CharField(
        max_length=100, 
        required=True,
        label="Localidad",
        widget=forms.TextInput(attrs={'class': 'perfil-input js-editable'})
    )
    
    class Meta:
        model = UbicacionGeografica
        fields = [
            "direccion",
            "calle_avenida",
            "sector",
            "numero_casa",
            "estado",
            "municipio",
            "parroquia",
            "zona_postal",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # IMPORTANTE: Ocultamos los selects de Django para manejarlos manualmente con JS
        self.fields["estado"].widget = forms.HiddenInput()
        self.fields["municipio"].widget = forms.HiddenInput()
        self.fields["parroquia"].widget = forms.HiddenInput()
        
        # Estilos para el resto de campos
        for name, field in self.fields.items():
            if name not in ["estado", "municipio", "parroquia"]:  # Excepto los ocultos
                css = field.widget.attrs.get("class", "")
                extra = "perfil-input js-editable"
                field.widget.attrs["class"] = f"{css} {extra}".strip()


class TaxiForm(forms.ModelForm):
    """Formulario simple para crear/editar taxis."""
    class Meta:
        model = Taxi
        fields = ["placa", "modelo", "anio", "conductor"]


class AvatarForm(forms.ModelForm):
    """Formulario mínimo para actualizar solo la foto de perfil (avatar)."""
    class Meta:
        model = Conductor
        fields = ["avatar"]


# ====================================================================
# FORMULARIOS DE USUARIO (REGISTRO, LOGIN, RESET)
# ====================================================================

class BaseUserRegisterForm(UserCreationForm):
    """
    Formulario base de registro que extiende UserCreationForm.
    Campos agregados: email, nombre, apellido, fecha_nacimiento, sexo.
    """
    email = forms.EmailField(
        required=True,
        label="Correo electrónico"
    )
    first_name = forms.CharField(
        required=True,
        label="Nombre",
        max_length=150
    )
    last_name = forms.CharField(
        required=True,
        label="Apellido",
        max_length=150
    )
    fecha_nacimiento = forms.DateField(
        required=True,
        label="Fecha de nacimiento",
        widget=forms.TextInput(attrs={"placeholder": "dd/mm/aaaa"}),
        input_formats=["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"],
    )
    sexo = forms.ChoiceField(
        choices=[("", "Seleccionar género"), ("M", "Masculino"), ("F", "Femenino")],
        label="Género",
    )

    class Meta:
        model = CustomUser
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "fecha_nacimiento",
            "sexo",
            "role",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ocultar campos que se llenan automáticamente
        self.fields["username"].required = False
        self.fields["username"].widget = forms.HiddenInput()

        self.fields["role"].required = False
        self.fields["role"].widget = forms.HiddenInput()

        # Estilos Bootstrap
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            if field.required:
                field.widget.attrs["required"] = "required"

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower().strip()
        try:
            existing = CustomUser.objects.filter(email=email).first()
        except (OperationalError, ProgrammingError):
            existing = None

        if existing:
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        email = cleaned.get("email")

        # Generar username basado en email si no existe
        if not username and email:
            base = email.split("@")[0]
            candidate = base
            i = 1
            while CustomUser.objects.filter(username=candidate).exists():
                candidate = f"{base}{i}"
                i += 1
            cleaned["username"] = candidate
            self.cleaned_data["username"] = candidate
        return cleaned

    def clean_fecha_nacimiento(self):
        value = self.cleaned_data.get("fecha_nacimiento")
        if value is None:
            raise forms.ValidationError("Este campo es obligatorio.")
        if value > date.today():
            raise forms.ValidationError("La fecha no puede ser en el futuro.")
        
        # Validar mayor de edad (18)
        hoy = date.today()
        edad = hoy.year - value.year - ((hoy.month, hoy.day) < (value.month, value.day))
        if edad < 18:
            raise forms.ValidationError("Debes ser mayor de 18 años.")
        return value

    def clean_password1(self):
        pwd = self.cleaned_data.get("password1") or ""
        if len(pwd) < 6:
            raise forms.ValidationError("La contraseña debe tener al menos 6 caracteres.")
        if len(pwd) > 20:
            raise forms.ValidationError("La contraseña no puede tener más de 20 caracteres.")
        return pwd

    def clean_password2(self):
        pwd1 = self.cleaned_data.get("password1")
        pwd2 = self.cleaned_data.get("password2")
        if pwd1 and pwd2 and pwd1 != pwd2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return pwd2


# Opciones de países para teléfono
PHONE_COUNTRY_CHOICES = [
    ("+58", "(+58) Venezuela"),
    ("+57", "(+57) Colombia"),
    ("+593", "(+593) Ecuador"),
    ("+51", "(+51) Perú"),
    ("+52", "(+52) México"),
    ("+54", "(+54) Argentina"),
    ("+55", "(+55) Brasil"),
    ("+56", "(+56) Chile"),
    ("+505", "(+505) Nicaragua"),
    ("+506", "(+506) Costa Rica"),
    ("+591", "(+591) Bolivia"),
    ("+598", "(+598) Uruguay"),
    ("+595", "(+595) Paraguay"),
    ("+502", "(+502) Guatemala"),
    ("+503", "(+503) El Salvador"),
    ("+504", "(+504) Honduras"),
    ("+507", "(+507) Panamá"),
    ("+53", "(+53) Cuba"),
    ("+1809", "(+1-809) Rep. Dominicana"),
    ("+1787", "(+1-787) Puerto Rico"),
]


class PresidenteRegisterForm(BaseUserRegisterForm):
    phone_country = forms.ChoiceField(
        choices=PHONE_COUNTRY_CHOICES,
        label="País",
        required=True,
    )
    phone_number = forms.CharField(
        max_length=15,
        label="Número de teléfono",
        required=True,
    )

    class Meta(BaseUserRegisterForm.Meta):
        fields = BaseUserRegisterForm.Meta.fields + (
            "phone_country",
            "phone_number",
        )

    def clean_phone_number(self):
        num = self.cleaned_data.get("phone_number", "").replace("-", "").strip()
        if not num.isdigit():
            raise forms.ValidationError("Solo se permiten números.")
        if len(num) < 6:
            raise forms.ValidationError("Número demasiado corto.")

        phone_country = self.cleaned_data.get("phone_country")
        full = f"{phone_country}{num}" if phone_country else num

        if CustomUser.objects.filter(phone_number=full, is_phone_verified=True).exists():
            raise forms.ValidationError("Este número ya está registrado.")
        return num


class AsociadoRegisterForm(BaseUserRegisterForm):
    phone_country = forms.ChoiceField(
        choices=PHONE_COUNTRY_CHOICES,
        label="País",
        required=True,
    )
    phone_number = forms.CharField(
        max_length=15,
        label="Número de teléfono",
        required=True,
    )

    class Meta(BaseUserRegisterForm.Meta):
        fields = BaseUserRegisterForm.Meta.fields + (
            "phone_country",
            "phone_number",
        )

    def clean_phone_number(self):
        raw = self.cleaned_data.get("phone_number", "") or ""
        num = raw.replace("-", "").replace(" ", "").strip()
        if not num.isdigit():
            raise forms.ValidationError("Solo se permiten números.")
        if len(num) < 6:
            raise forms.ValidationError("Número demasiado corto.")

        phone_country = self.cleaned_data.get("phone_country")
        full = f"{phone_country}{num}" if phone_country else num

        if CustomUser.objects.filter(phone_number=full, is_email_verified=True).exists():
            raise forms.ValidationError("Este número ya está registrado.")
        return num


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """
    Login con username O email.
    """
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_email_verified:
            raise forms.ValidationError(
                _("Debes verificar tu correo electrónico antes de iniciar sesión."),
                code="inactive",
            )

    def clean(self):
        username = self.data.get("username", "").strip()
        password = self.data.get("password", "").strip()

        if not username or not password:
            raise forms.ValidationError(
                _("Debes completar usuario/correo y contraseña."),
                code="invalid_login",
            )

        from django.contrib.auth import authenticate

        # 1. Intentar como username
        user = authenticate(self.request, username=username, password=password)

        # 2. Si falla, intentar como email
        if user is None:
            try:
                user_obj = CustomUser.objects.filter(email__iexact=username).first()
                if user_obj:
                    user = authenticate(
                        self.request,
                        username=user_obj.username,
                        password=password,
                    )
                else:
                    user = None
            except (CustomUser.DoesNotExist, MultipleObjectsReturned):
                user = None

        if user is None:
            raise forms.ValidationError(
                _("Usuario o contraseña incorrectos. Intenta de nuevo."),
                code="invalid_login",
            )

        self.confirm_login_allowed(user)
        self.user_cache = user
        self.cleaned_data["username"] = username
        self.cleaned_data["password"] = password
        return self.cleaned_data


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        required=True
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if not CustomUser.objects.filter(email=email, is_email_verified=True).exists():
            raise forms.ValidationError("No existe una cuenta activa con este correo.")
        return email


class VerificationCodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label="Código de verificación",
        required=True,
        error_messages={
            "required": "Debes ingresar el código.",
            "min_length": "El código debe tener 6 dígitos.",
            "max_length": "El código debe tener 6 dígitos.",
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "maxlength": "6",
                "class": "form-control",
                "placeholder": "000000",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip()
        if not code.isdigit():
            raise forms.ValidationError("El código debe contener solo dígitos.")
        return code
