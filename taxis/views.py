from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth import views as auth_views  # Autenticación
from django.shortcuts import render, redirect  # Para vista index y redirección
from django.contrib.auth import login
from django.contrib import messages
from .models import Conductor, Taxi
from .forms import ConductorForm, TaxiForm, CustomUserCreationForm


class ConductorListView(ListView):
    model = Conductor
    template_name = 'taxis/conductor_list.html'
    context_object_name = 'conductores'


class ConductorDetailView(DetailView):
    model = Conductor
    template_name = 'taxis/conductor_detail.html'
    context_object_name = 'conductor'


class TaxiListView(ListView):
    model = Taxi
    template_name = 'taxis/taxi_list.html'
    context_object_name = 'taxis'


class TaxiDetailView(DetailView):
    model = Taxi
    template_name = 'taxis/taxi_detail.html'
    context_object_name = 'taxi'


class ConductorCreateView(SuccessMessageMixin, CreateView):
    model = Conductor
    form_class = ConductorForm
    template_name = 'taxis/conductor_form.html'
    success_url = reverse_lazy('taxis:conductor-list')
    success_message = "Conductor creado exitosamente."


class ConductorUpdateView(SuccessMessageMixin, UpdateView):
    model = Conductor
    form_class = ConductorForm
    template_name = 'taxis/conductor_form.html'
    success_url = reverse_lazy('taxis:conductor-list')
    success_message = "Conductor actualizado exitosamente."


class ConductorDeleteView(DeleteView):
    model = Conductor
    template_name = 'taxis/conductor_confirm_delete.html'
    success_url = reverse_lazy('taxis:conductor-list')


class TaxiCreateView(SuccessMessageMixin, CreateView):
    model = Taxi
    form_class = TaxiForm
    template_name = 'taxis/taxi_form.html'
    success_url = reverse_lazy('taxis:taxi-list')
    success_message = "Taxi creado exitosamente."


class TaxiUpdateView(SuccessMessageMixin, UpdateView):
    model = Taxi
    form_class = TaxiForm
    template_name = 'taxis/taxi_form.html'
    success_url = reverse_lazy('taxis:taxi-list')
    success_message = "Taxi actualizado exitosamente."


class TaxiDeleteView(DeleteView):
    model = Taxi
    template_name = 'taxis/taxi_confirm_delete.html'
    success_url = reverse_lazy('taxis:taxi-list')


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, '¡Registro exitoso!')
            return redirect('taxis:index')  # Cambia si quieres otra url
    else:
        form = CustomUserCreationForm()
    return render(request, 'taxis/register.html', {'form': form})


def index(request):
    # Puedes extender esta vista para pasar contexto o lógica adicional
    return render(request, 'taxis/index.html')


# Vistas para restablecimiento de contraseña (mantener si usas autenticación personalizada)

class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'taxis/forgot-password.html'


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'taxis/password_reset_done.html'


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'taxis/password_reset_confirm.html'


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'taxis/password_reset_complete.html'