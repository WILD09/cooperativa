from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Conductor, Taxi, CustomUser
from captcha.fields import CaptchaField  # IMPORTADO EL CAMPO DE django-simple-captcha

class ConductorForm(forms.ModelForm):
    class Meta:
        model = Conductor
        fields = ['nombre', 'apellido', 'telefono', 'cedula_identidad', 'fecha_nacimiento', 'sexo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields.pop('pago_patente_realizado', None)
            self.fields.pop('fecha_pago_patente', None)
        else:
            self.fields['pago_patente_realizado'].required = False
            self.fields['fecha_pago_patente'].required = False

class TaxiForm(forms.ModelForm):
    class Meta:
        model = Taxi
        fields = ['placa', 'modelo', 'anio', 'conductor']

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo electrónico")
    first_name = forms.CharField(required=True, label="Nombre")
    last_name = forms.CharField(required=True, label="Apellido")
    edad = forms.IntegerField(required=False, label="Edad")
    sexo = forms.ChoiceField(choices=[('M', 'Masculino'), ('F', 'Femenino')], label="Sexo")
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES, label="Rol")
    captcha = CaptchaField(label="Verificación")  # CAMPO DEL CAPTCHA SIMPLE

    class Meta:
        model = CustomUser
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'edad',
            'sexo',
            'role',
            'password1',
            'password2',
        )

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agregar clases bootstrap a los campos del formulario para integrar con tu template
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control form-control-user'
            if field.required:
                field.widget.attrs['required'] = 'required'
