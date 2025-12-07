"""
forms.py
Formularios de la aplicación 'taxis':
- Formularios para Conductor y Taxi (CRUD).
- Formularios de registro de usuario (presidente/asociado).
- Formulario de código de verificación.
- Formulario de autenticación (login con usuario o email).
- Formulario de solicitud de restablecimiento de contraseña.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm  # Formularios base de auth.
from django.db import OperationalError, ProgrammingError                    # Excepciones de base de datos.
from django.utils.translation import gettext_lazy as _                      # Soporte para texto traducible.

from .models import Conductor, Taxi, CustomUser


# -------------------------------------------------------------------
# FORMULARIOS PARA CONDUCTOR Y TAXI
# -------------------------------------------------------------------


class ConductorForm(forms.ModelForm):
    """
    Formulario para crear/editar conductores.
    Muestra solo campos básicos al crear; controla pago de patente al editar.
    """

    class Meta:
        model = Conductor
        # Campos visibles en el formulario.
        fields = [
            "nombre",
            "apellido",
            "telefono",
            "cedula_identidad",
            "fecha_nacimiento",
            "sexo",
        ]

    def __init__(self, *args, **kwargs):
        """
        Personaliza el formulario:
        - Si el conductor es nuevo (sin pk), se ocultan campos de pago de patente.
        - Si ya existe, se permiten editar esos campos pero no son obligatorios.
        """
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            # Al crear un nuevo conductor, no se muestran estos campos.
            self.fields.pop("pago_patente_realizado", None)
            self.fields.pop("fecha_pago_patente", None)
        else:
            # Al editar, los campos de pago no son obligatorios.
            self.fields["pago_patente_realizado"].required = False
            self.fields["fecha_pago_patente"].required = False


class TaxiForm(forms.ModelForm):
    """
    Formulario simple para crear/editar taxis.
    """

    class Meta:
        model = Taxi
        # Campos básicos del taxi.
        fields = ["placa", "modelo", "anio", "conductor"]


# -------------------------------------------------------------------
# FORMULARIOS DE USUARIO (REGISTRO, LOGIN, RESET)
# -------------------------------------------------------------------


class BaseUserRegisterForm(UserCreationForm):
    """
    Formulario base de registro de usuario.
    Extiende UserCreationForm para agregar:
    - email obligatorio,
    - nombre, apellido,
    - fecha de nacimiento,
    - sexo,
    - rol (oculto, asignado desde la vista).
    """

    # Campos adicionales visibles en el formulario.
    email = forms.EmailField(required=True, label="Correo electrónico")
    first_name = forms.CharField(required=True, label="Nombre")
    last_name = forms.CharField(required=True, label="Apellido")

    # Fecha de nacimiento con soporte para varios formatos.
    fecha_nacimiento = forms.DateField(
        required=True,
        label="Fecha de nacimiento",
        widget=forms.TextInput(
            attrs={
                "placeholder": "dd/mm/aaaa",  # Ayuda visual en el input.
            }
        ),
        input_formats=["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"],  # Formatos aceptados.
    )

    # Campo de selección de sexo con una opción vacía inicial.
    sexo = forms.ChoiceField(
        choices=[("", "Seleccionar género"), ("M", "Masculino"), ("F", "Femenino")],
        label="Sexo",
    )

    class Meta:
        """
        Define el modelo y los campos que se manejarán en el formulario.
        """
        model = CustomUser
        fields = (
            "username",          # Oculto, se autogenera a partir del email.
            "first_name",
            "last_name",
            "email",
            "fecha_nacimiento",
            "sexo",
            "role",              # Oculto, se asigna en la vista según el rol elegido.
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        """
        Personaliza campos:
        - Oculta username y role.
        - Añade clase CSS 'form-control' a todos los campos.
        - Marca explícitamente los campos requeridos en el HTML.
        """
        super().__init__(*args, **kwargs)

        # El nombre de usuario no se pide al usuario; se genera automáticamente.
        self.fields["username"].required = False
        self.fields["username"].widget = forms.HiddenInput()

        # El rol también se oculta; la vista decide el valor (presidente/asociado).
        self.fields["role"].required = False
        self.fields["role"].widget = forms.HiddenInput()

        # Añade estilos y el atributo 'required' a los campos obligatorios.
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            if field.required:
                field.widget.attrs["required"] = "required"

    def clean_email(self):
        """
        Valida que el correo:
        - se normaliza a minúsculas,
        - no esté ya registrado con email verificado.
        Permite reusar correos no verificados.
        """
        email = self.cleaned_data.get("email", "").lower()
        try:
            existing = CustomUser.objects.filter(email=email).first()
        except (OperationalError, ProgrammingError):
            # Si la tabla de usuarios no existe aún (migraciones iniciales), no falla.
            existing = None

        if existing and existing.is_email_verified:
            # Si ya hay un usuario activo con este correo, se bloquea el registro.
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def clean(self):
        """
        Limpieza general del formulario.
        - Si no se ha proporcionado username, se genera automáticamente
          a partir de la parte local del email (antes de la @),
          añadiendo un sufijo numérico si existe colisión.
        """
        cleaned = super().clean()
        username = cleaned.get("username")
        email = cleaned.get("email")

        if not username and email:
            base = email.split("@")[0]   # Parte antes de la @.
            candidate = base
            i = 1
            # Busca un username disponible; agrega números si está ocupado.
            while CustomUser.objects.filter(username=candidate).exists():
                candidate = f"{base}{i}"
                i += 1
            cleaned["username"] = candidate
            self.cleaned_data["username"] = candidate
        return cleaned

    def clean_fecha_nacimiento(self):
        """
        Asegura que fecha_nacimiento no venga vacía.
        (El campo ya es required=True, esto refuerza la validación).
        """
        value = self.cleaned_data.get("fecha_nacimiento")
        if value is None:
            raise forms.ValidationError("Este campo es obligatorio.")
        return value

    def clean_password1(self):
        """
        Valida la longitud de la contraseña:
        - mínimo 6 caracteres,
        - máximo 20 caracteres.
        """
        pwd = self.cleaned_data.get("password1") or ""
        if len(pwd) < 6:
            raise forms.ValidationError("La contraseña debe tener al menos 6 caracteres.")
        if len(pwd) > 20:
            raise forms.ValidationError("La contraseña no puede tener más de 20 caracteres.")
        return pwd


# Lista de opciones de prefijo telefónico por país.
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
    """
    Formulario de registro para el rol PRESIDENTE.
    Extiende el formulario base agregando campos obligatorios de teléfono.
    """

    # País (prefijo telefónico).
    phone_country = forms.ChoiceField(
        choices=PHONE_COUNTRY_CHOICES,
        label="País",
        required=True,
    )

    # Número de teléfono (parte local sin prefijo).
    phone_number = forms.CharField(
        max_length=15,
        label="Número de teléfono",
        required=True,
    )

    class Meta(BaseUserRegisterForm.Meta):
        """
        Agrega los campos de teléfono a los campos del formulario base.
        """
        fields = BaseUserRegisterForm.Meta.fields + (
            "phone_country",
            "phone_number",
        )

    def clean_phone_number(self):
        """
        Valida el número de teléfono:
        - solo dígitos,
        - longitud mínima,
        - que no esté ya registrado y verificado en otro usuario.
        """
        # Elimina guiones y espacios, y recorta espacios extremos.
        num = self.cleaned_data.get("phone_number", "").replace("-", "").strip()
        if not num.isdigit():
            raise forms.ValidationError("Solo se permiten números.")
        if len(num) < 6:
            raise forms.ValidationError("Número demasiado corto.")

        # Construye el número completo con prefijo de país.
        phone_country = self.cleaned_data.get("phone_country")
        full = f"{phone_country}{num}" if phone_country else num

        # Verifica que no exista otro usuario con ese número ya verificado.
        qs = CustomUser.objects.filter(phone_number=full, is_phone_verified=True)
        if qs.exists():
            raise forms.ValidationError("Este número ya está registrado.")

        # Devuelve solo la parte local; la vista se encarga de unir con el prefijo.
        return num


class AsociadoRegisterForm(BaseUserRegisterForm):
    """
    Formulario de registro para el rol ASOCIADO.
    Tiene la misma lógica telefónica que PresidenteRegisterForm.
    """

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
        """
        Agrega los campos de teléfono al formulario base de usuario.
        """
        fields = BaseUserRegisterForm.Meta.fields + (
            "phone_country",
            "phone_number",
        )

    def clean_phone_number(self):
        """
        Validación del teléfono del asociado:

        - Normaliza el número (quita guiones/espacios).
        - Verifica solo dígitos y longitud mínima.
        - Construye código de país + número local para buscar duplicados
          contra usuarios con email verificado.
        - Devuelve SOLO el número local; la vista arma el número completo.
        """
        raw = self.cleaned_data.get("phone_number", "") or ""
        num = raw.replace("-", "").replace(" ", "").strip()

        if not num.isdigit():
            raise forms.ValidationError("Solo se permiten números.")

        if len(num) < 6:
            raise forms.ValidationError("Número demasiado corto.")

        phone_country = self.cleaned_data.get("phone_country")
        full = f"{phone_country}{num}" if phone_country else num

        # Bloquea si ya existe un usuario con este número y correo verificado
        if CustomUser.objects.filter(
            phone_number=full,
            is_email_verified=True,
        ).exists():
            raise forms.ValidationError("Este número ya está registrado.")

        # Devolvemos solo el número local; la vista le agrega el prefijo
        return num

class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """
    Formulario de login que permite autenticarse con:
    - nombre de usuario (username), o
    - correo electrónico (email).

    Además:
    - exige que el correo del usuario esté verificado (is_email_verified=True),
    - reutiliza la lógica estándar de AuthenticationForm (is_active, etc.).
    """

    def confirm_login_allowed(self, user):
        """
        Valida si al usuario se le permite iniciar sesión.

        Extiende la validación base de Django:
        - primero llama a la implementación original (comprueba is_active),
        - luego verifica que el correo esté verificado (is_email_verified=True).
        """
        # Lógica base: comprueba is_active y otras restricciones estándar
        super().confirm_login_allowed(user)

        # Restricción adicional: el correo debe estar verificado
        if not user.is_email_verified:
            raise forms.ValidationError(
                _("Debes verificar tu correo electrónico antes de iniciar sesión."),
                code="inactive",
            )

    def clean(self):
        """
        Proceso principal de autenticación.

        Flujo:
        1. Obtiene lo que el usuario escribió en el campo "username" (puede ser usuario o correo)
           y la contraseña desde self.data.
        2. Valida que ambos campos no estén vacíos.
        3. Intenta autenticar usando el valor tal cual como username.
        4. Si falla, intenta interpretarlo como correo:
           - busca un CustomUser con ese email (case-insensitive),
           - si lo encuentra, reintenta authenticate usando user.username.
        5. Si después de ambos intentos no hay usuario válido, lanza error genérico.
        6. Si encuentra usuario:
           - llama a confirm_login_allowed(user) para aplicar restricciones extra,
           - guarda el usuario en self.user_cache,
           - devuelve cleaned_data con username y password.
        """
        # Lo que llega desde el formulario HTML
        username = self.data.get("username")
        password = self.data.get("password")

        print("DEBUG LOGIN POST:", repr(username), repr(password))

        # 1) Validación de campos vacíos
        if not username or not password:
            raise forms.ValidationError(
                _("Debes completar usuario/correo y contraseña."),
                code="invalid_login",
            )

        from django.contrib.auth import authenticate

        user = None

        # 2) Primer intento: usar el valor tal cual como username
        user = authenticate(self.request, username=username, password=password)

        # 3) Segundo intento: si no se autenticó, probar interpretando como email
        if user is None:
            try:
                # Busca un usuario cuyo email coincida (ignorando mayúsculas/minúsculas)
                user_obj = CustomUser.objects.get(email__iexact=username.strip())
                # Reintenta authenticate usando el username real del usuario encontrado
                user = authenticate(
                    self.request,
                    username=user_obj.username,
                    password=password,
                )
            except CustomUser.DoesNotExist:
                user = None

        # 4) Si sigue sin encontrar usuario válido, lanza error genérico
        if user is None:
            raise forms.ValidationError(
                _("Usuario o contraseña incorrectos. Intenta de nuevo."),
                code="invalid_login",
            )

        # 5) Verifica restricciones adicionales (is_active, is_email_verified, etc.)
        self.confirm_login_allowed(user)

        # 6) Guarda el usuario autenticado en el formulario
        self.user_cache = user
        # Asegura que los campos queden en cleaned_data
        self.cleaned_data["username"] = username
        self.cleaned_data["password"] = password
        return self.cleaned_data


class PasswordResetRequestForm(forms.Form):
    """
    Formulario para solicitar restablecimiento de contraseña:
    - solo pide correo electrónico,
    - valida que exista una cuenta activa (correo verificado).
    """

    email = forms.EmailField(label="Correo electrónico", required=True)

    def clean_email(self):
        """
        Valida que el correo:
        - se normaliza a minúsculas,
        - exista un usuario con ese correo y con is_email_verified=True.
        """
        email = self.cleaned_data["email"].lower()
        if not CustomUser.objects.filter(email=email, is_email_verified=True).exists():
            raise forms.ValidationError("No existe una cuenta activa con este correo.")
        return email

class VerificationCodeForm(forms.Form):
    """
    Formulario para introducir un código de 6 dígitos enviado por correo.

    Se usa en:
    - verify_email_view (verificación de correo tras registro)
    - password_reset_verify_view (verificación de código de recuperación)
    """
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
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
