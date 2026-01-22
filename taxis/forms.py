from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm
from django.core.validators import RegexValidator
from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from .models import Conductor, Vehiculo, CustomUser, UbicacionGeografica, Pago, PagoMensual


# ====================================================================
# LISTA DE PAÍSES LATAM
# ====================================================================
LATAM_PREFIXES = [
    ('+58', '(+58) Venezuela'), ('+54', '(+54) Argentina'), ('+591', '(+591) Bolivia'),
    ('+55', '(+55) Brasil'), ('+56', '(+56) Chile'), ('+57', '(+57) Colombia'),
    ('+506', '(+506) Costa Rica'), ('+53', '(+53) Cuba'), ('+593', '(+593) Ecuador'),
    ('+503', '(+503) El Salvador'), ('+502', '(+502) Guatemala'), ('+504', '(+504) Honduras'),
    ('+52', '(+52) México'), ('+505', '(+505) Nicaragua'), ('+507', '(+507) Panamá'),
    ('+595', '(+595) Paraguay'), ('+51', '(+51) Perú'), ('+1787', '(+1787) Puerto Rico'),
    ('+1809', '(+1809) Rep. Dominicana'), ('+598', '(+598) Uruguay'),
]


# Validadores Reutilizables
solo_letras = RegexValidator(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', 'Solo se permiten letras.')
solo_numeros = RegexValidator(r'^\d+$', 'Solo se permiten números.')


def validar_unicidad_cruzada(model_field, value, exclude_pk=None):
    """
    Verifica que el valor no exista en Conductor ni en CustomUser.
    Permite excluir un ID (para ediciones).
    """
    # 1. Verificar en Conductores
    qs_cond = Conductor.objects.filter(**{model_field: value})
    if exclude_pk:
        qs_cond = qs_cond.exclude(pk=exclude_pk)
    
    if qs_cond.exists():
        raise ValidationError(f"Este dato ya está registrado en otro afiliado.")


    # 2. Verificar en Presidentes (Mapeo de campos)
    user_field_map = {
        'email': 'email',
        'telefono_principal': 'phone_number',
    }
    
    if model_field in user_field_map:
        user_field = user_field_map[model_field]
        # Aquí no excluimos exclude_pk porque los ID de Conductor y User son tablas distintas
        if CustomUser.objects.filter(**{user_field: value}).exists():
            raise ValidationError(f"Este dato ya está registrado por un directivo.")


# ====================================================================
# FORMULARIOS UBICACIÓN
# ====================================================================


class UbicacionGeograficaForm(forms.ModelForm):
    # Estado fijo en Guárico
    ESTADO_CHOICES = [('Guárico', 'Guárico')]


    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES, 
        widget=forms.Select(attrs={"id": "select-estado"}),
        label="Estado"
    )


    class Meta:
        model = UbicacionGeografica
        fields = ["estado", "localidad", "municipio", "parroquia", "sector", "calle_avenida", "numero_casa", "zona_postal"]
        widgets = {
            "localidad": forms.Select(attrs={"id": "select-localidad"}),
            "municipio": forms.Select(attrs={"id": "select-municipio"}),
            "parroquia": forms.Select(attrs={"id": "select-parroquia"}),
            "sector": forms.TextInput(attrs={"placeholder": "Urb/Barrio/Sector", "autocomplete": "new-password", "maxlength": "50"}),
            "calle_avenida": forms.TextInput(attrs={"placeholder": "Calle/Av", "autocomplete": "new-password", "maxlength": "50"}),
            "numero_casa": forms.TextInput(attrs={"placeholder": "N° Casa", "autocomplete": "new-password", "maxlength": "10"}),
            "zona_postal": forms.TextInput(attrs={"placeholder": "Zona Postal", "readonly": "readonly"}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'vsms-input'
        
        self.fields['localidad'].choices = [('', 'Seleccione una localidad...')]



# ====================================================================
# FORMULARIOS CONDUCTOR
# ====================================================================


class ConductorForm(forms.ModelForm):
    # --- FECHAS CON SOPORTE DD/MM/YYYY ---
    fecha_nacimiento = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA", "autocomplete": "off"})
    )
    cedula_vencimiento = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA", "autocomplete": "off"})
    )
    rif_vencimiento = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA", "autocomplete": "off"})
    )


    class Meta:
        model = Conductor
        fields = [
            "nombres", "apellidos", "fecha_nacimiento", "sexo", "estado_civil",
            "cedula_prefijo", "cedula_identidad", "cedula_archivo", "cedula_vencimiento",
            "rif_prefijo", "rif", "rif_archivo", "rif_vencimiento",
            "email", "telefono_principal", "telefono_secundario", "telefono_fijo",
            "avatar"
        ]
        widgets = {
            "nombres": forms.TextInput(attrs={"placeholder": "Ej. Juan Carlos", "autocomplete": "new-password", "maxlength": "25"}),
            "apellidos": forms.TextInput(attrs={"placeholder": "Ej. Pérez", "autocomplete": "new-password", "maxlength": "25"}),
            # Las fechas se definen arriba explícitamente para controlar input_formats
            "cedula_identidad": forms.TextInput(attrs={"class": "num-only", "placeholder": "Ej. 12345678", "autocomplete": "new-password", "maxlength": "11"}),
            "rif": forms.TextInput(attrs={"placeholder": "Ej. J123456789", "autocomplete": "new-password", "maxlength": "12"}),
            "telefono_principal": forms.TextInput(attrs={"class": "num-only", "placeholder": "04121234567", "autocomplete": "new-password", "maxlength": "11"}),
            "telefono_secundario": forms.TextInput(attrs={"class": "num-only", "placeholder": "Opcional", "autocomplete": "new-password", "maxlength": "11"}),
            "telefono_fijo": forms.TextInput(attrs={"class": "num-only", "placeholder": "Opcional", "autocomplete": "new-password", "maxlength": "11"}),
            "email": forms.EmailInput(attrs={"placeholder": "correo@ejemplo.com", "autocomplete": "new-password"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Asignar clases CSS a los inputs
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput) and not isinstance(field.widget, forms.FileInput):
                existing_classes = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"vsms-input {existing_classes}"
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'dropzone-input'


        # 2. LOGICA CORREGIDA PARA EDICIÓN DE ARCHIVOS
        if self.instance.pk:
            if self.instance.cedula_archivo:
                self.fields['cedula_archivo'].required = False
            
            if self.instance.rif_archivo:
                self.fields['rif_archivo'].required = False
                
            if self.instance.avatar:
                self.fields['avatar'].required = False


    # --- VALIDACIONES ---


    def clean_nombres(self):
        n = self.cleaned_data.get('nombres')
        if len(n) > 25: raise ValidationError("Máximo 25 caracteres.")
        return n.title()


    def clean_apellidos(self):
        a = self.cleaned_data.get('apellidos')
        if len(a) > 25: raise ValidationError("Máximo 25 caracteres.")
        return a.title()


    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get("fecha_nacimiento")
        if fecha:
            hoy = date.today()
            if fecha > hoy:
                raise ValidationError("La fecha no puede ser futura.")
            edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
            if edad < 18:
                raise ValidationError(f"El afiliado es menor de edad ({edad} años).")
        return fecha


    def clean_cedula_identidad(self):
        cedula = self.cleaned_data.get('cedula_identidad')
        if cedula:
            if not cedula.isdigit(): raise ValidationError("Solo números permitidos.")
            if not (7 <= len(cedula) <= 11): raise ValidationError("Debe tener entre 7 y 11 dígitos.")
            validar_unicidad_cruzada('cedula_identidad', cedula, self.instance.pk)
        return cedula


    def clean_rif(self):
        rif = self.cleaned_data.get('rif')
        if rif:
            rif = rif.upper().strip() # Normalizar
            if len(rif) < 8: raise ValidationError("El RIF es muy corto.")
            validar_unicidad_cruzada('rif', rif, self.instance.pk)
        return rif


    def clean_telefono_principal(self):
        tel = self.cleaned_data.get('telefono_principal')
        if tel:
            if not tel.isdigit(): raise ValidationError("Solo números permitidos.")
            if not (10 <= len(tel) <= 11): raise ValidationError("Debe tener 10 u 11 dígitos.")
            validar_unicidad_cruzada('telefono_principal', tel, self.instance.pk)
        return tel


    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            validar_unicidad_cruzada('email', email, self.instance.pk)
        return email


    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data



# ====================================================================
# FORMULARIOS VEHICULO
# ====================================================================


class VehiculoForm(forms.ModelForm):
    # --- FECHAS CON SOPORTE DD/MM/YYYY ---
    patente_vencimiento = forms.DateField(input_formats=['%d/%m/%Y', '%Y-%m-%d'], widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA"}))
    licencia_vencimiento = forms.DateField(input_formats=['%d/%m/%Y', '%Y-%m-%d'], widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA"}))
    rcv_vencimiento = forms.DateField(input_formats=['%d/%m/%Y', '%Y-%m-%d'], widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA"}))
    medico_vencimiento = forms.DateField(input_formats=['%d/%m/%Y', '%Y-%m-%d'], widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA"}))
    aceite_ultimo_cambio = forms.DateField(input_formats=['%d/%m/%Y', '%Y-%m-%d'], widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA"}), required=False)
    kit_tiempo_cambio = forms.DateField(input_formats=['%d/%m/%Y', '%Y-%m-%d'], widget=forms.DateInput(attrs={"class": "date-mask", "placeholder": "DD/MM/AAAA"}), required=False)


    class Meta:
        model = Vehiculo
        fields = "__all__"
        widgets = {
            # Las fechas se definen arriba
            # --- WIDGETS PARA LOS NUEVOS CAMPOS ---
            "bateria_amperaje": forms.TextInput(attrs={"placeholder": "Ej: 700 AMP", "maxlength": "10"}),
            "aceite_viscosidad": forms.TextInput(attrs={"placeholder": "Ej: 15W40", "maxlength": "10"}),
            "combustible_litros": forms.TextInput(attrs={"placeholder": "Ej: 45", "maxlength": "10"}),
            "cauchos_medida": forms.TextInput(attrs={"placeholder": "Ej: 185/65", "maxlength": "10"}),
            "diametro_rin": forms.TextInput(attrs={"placeholder": "Ej: 14", "maxlength": "5", "type": "number"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'vsms-input'


        # --- LÓGICA DE CASCOS UNICOS ---
        cascos_ocupados = Vehiculo.objects.all().values_list('numero_casco', flat=True)
        if self.instance and self.instance.pk:
            cascos_ocupados = cascos_ocupados.exclude(pk=self.instance.pk)
            
        if 'numero_casco' in self.fields:
            if hasattr(self.fields['numero_casco'], 'choices'):
                todas_opciones = self.fields['numero_casco'].choices
                opciones_disponibles = [
                    (k, v) for k, v in todas_opciones 
                    if k not in cascos_ocupados
                ]
                self.fields['numero_casco'].choices = opciones_disponibles
        
        if self.instance.pk:
            file_fields = [
                'patente_archivo', 'licencia_archivo', 'rcv_archivo', 'medico_archivo', 
                'circulacion_archivo', 'registro_archivo', 'foto'
            ]
            for f_name in file_fields:
                if f_name in self.fields and getattr(self.instance, f_name):
                    self.fields[f_name].required = False



# ====================================================================
# FORMULARIOS FINANCIEROS
# ====================================================================


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ["monto_bs", "tasa_bcv", "comprobante"]
        widgets = {
            "monto_bs": forms.NumberInput(attrs={"step": "0.01", "placeholder": "Monto en Bs"}),
            "tasa_bcv": forms.NumberInput(attrs={"step": "0.0001", "placeholder": "Tasa BCV"}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'vsms-input'


class PagoMensualForm(forms.ModelForm):
    """
    Formulario para registrar pagos mensuales.
    Los campos mes y anio se manejan desde los checkboxes en el template,
    no desde este formulario.
    """
    
    # ✅ SOPORTE PARA DD/MM/YYYY
    fecha_pago = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(
            attrs={
                'class': 'vsms-input',
                'type': 'text',
                'placeholder': 'DD/MM/YYYY',
                'autocomplete': 'off'
            }
        )
    )

    class Meta:
        model = PagoMensual
        fields = ['fecha_pago', 'comprobante', 'notas']  # ✅ SIN mes y anio
        widgets = {
            'comprobante': forms.FileInput(
                attrs={
                    'accept': 'image/*,application/pdf',
                    'class': 'file-input'
                }
            ),
            'notas': forms.Textarea(
                attrs={
                    'rows': 4,
                    'class': 'vsms-input',
                    'placeholder': 'Notas opcionales...'
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ✅ Fecha por defecto: hoy
        hoy = timezone.localtime().date()
        self.fields['fecha_pago'].initial = hoy.strftime('%d/%m/%Y')
        
        # ✅ Campos opcionales
        self.fields['comprobante'].required = False
        self.fields['notas'].required = False


# ====================================================================
# FORMULARIOS AUTH
# ====================================================================


class BaseUserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo electrónico", error_messages={'required': 'Obligatorio.'})
    first_name = forms.CharField(required=True, label="Nombres", max_length=20, validators=[solo_letras], error_messages={'required': 'Obligatorio.', 'max_length': 'Máximo 20 caracteres.'})
    last_name = forms.CharField(required=True, label="Apellidos", max_length=20, validators=[solo_letras], error_messages={'required': 'Obligatorio.', 'max_length': 'Máximo 20 caracteres.'})
    fecha_nacimiento = forms.DateField(
        required=True, 
        label="Fecha de nacimiento", 
        widget=forms.DateInput(attrs={"type": "date"}), # Este input es nativo (yyyy-mm-dd), no necesita format
        error_messages={'required': 'Obligatorio.'}
    )
    sexo = forms.ChoiceField(choices=[("", "Seleccionar género"), ("M", "Masculino"), ("F", "Femenino")], label="Género", error_messages={'required': 'Obligatorio.'})


    class Meta:
        model = CustomUser
        fields = ("username", "first_name", "last_name", "email", "fecha_nacimiento", "sexo", "role")


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].required = False
        self.fields["username"].widget = forms.HiddenInput()
        self.fields["role"].required = False
        self.fields["role"].widget = forms.HiddenInput()
        for name, field in self.fields.items():
            if name not in ['username', 'role']:
                field.widget.attrs['class'] = 'vsms-input'


    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower().strip()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Correo ya registrado.")
        return email


    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        email = cleaned.get("email")
        if not username and email:
            base = email.split("@")[0]
            candidate = base
            i = 1
            while CustomUser.objects.filter(username=candidate).exists():
                candidate = f"{base}{i}"
                i += 1
            cleaned["username"] = candidate
        return cleaned


    def clean_fecha_nacimiento(self):
        value = self.cleaned_data.get("fecha_nacimiento")
        if value:
            hoy = date.today()
            edad = hoy.year - value.year - ((hoy.month, hoy.day) < (value.month, value.day))
            if edad < 18:
                raise forms.ValidationError("Debes ser mayor de 18 años.")
            if edad > 100:
                raise forms.ValidationError("Fecha no válida.")
        return value



class PresidenteRegisterForm(BaseUserRegisterForm):
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'placeholder': 'Mín. 6 caracteres', 'class': 'vsms-input'}), min_length=6, max_length=20, error_messages={'required': 'Obligatorio.', 'min_length': 'Mínimo 6 caracteres.', 'max_length': 'Máximo 20 caracteres.'})
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput(attrs={'placeholder': 'Repite contraseña', 'class': 'vsms-input'}), max_length=20, error_messages={'required': 'Obligatorio.'})
    phone_country = forms.ChoiceField(choices=LATAM_PREFIXES, label="País", required=True, widget=forms.Select(attrs={'class': 'vsms-input'}), error_messages={'required': 'Obligatorio.'})
    phone_number = forms.CharField(min_length=10, max_length=15, label="Número de teléfono", required=True, validators=[solo_numeros], widget=forms.TextInput(attrs={'class': 'vsms-input', 'placeholder': '0412-1234567'}), error_messages={'required': 'Obligatorio.', 'min_length': 'Mínimo 10 dígitos.', 'max_length': 'Máximo 15 dígitos.', 'invalid': 'Solo se permiten números.'})


    class Meta(BaseUserRegisterForm.Meta):
        fields = BaseUserRegisterForm.Meta.fields + ("phone_country", "phone_number")
    
    def clean_phone_number(self):
        numero = self.cleaned_data.get('phone_number')
        if not numero.isdigit():
            raise forms.ValidationError("Solo números.")
        if CustomUser.objects.filter(phone_number=numero).exists():
            raise forms.ValidationError("Este teléfono ya está registrado.")
        return numero


    def save(self, commit=True):
        user = super(BaseUserRegisterForm, self).save(commit=False)
        user.username = self.cleaned_data["username"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.fecha_nacimiento = self.cleaned_data["fecha_nacimiento"]
        user.sexo = self.cleaned_data["sexo"]
        user.role = self.cleaned_data.get("role", "presidente")
        user.phone_country = self.cleaned_data["phone_country"]
        user.phone_number = self.cleaned_data["phone_number"]
        user.set_password(self.cleaned_data["password1"])
        if commit: user.save()
        return user



class VerificationCodeForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6, label="Código", widget=forms.TextInput(attrs={"placeholder": "000000"}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].widget.attrs['class'] = 'vsms-input'
    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip()
        if not code.isdigit(): raise forms.ValidationError("Solo dígitos.")
        return code



class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'vsms-input'
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            if '@' in username:
                User = get_user_model()
                try:
                    user = User.objects.get(email__iexact=username)
                    username = user.username
                    self.cleaned_data['username'] = username
                except User.DoesNotExist: pass
        return super().clean()
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_active: raise forms.ValidationError("Esta cuenta está inactiva.", code="inactive")



class CustomPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()
        if not User.objects.filter(email=email, is_active=True).exists():
            raise forms.ValidationError("No existe una cuenta activa asociada a este correo.")
        return email
