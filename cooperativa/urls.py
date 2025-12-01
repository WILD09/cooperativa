from django.contrib import admin
from django.urls import path, include
from core.views import home  # Vista original (puedes eliminar si no usarás)
from django.shortcuts import redirect


# Vista para redirigir en la raíz
def redirect_root(request):
    if request.user.is_authenticated:
        return redirect('taxis:index')  # Página principal para usuarios autenticados
    else:
        return redirect('login')  # Página de login para usuarios no autenticados


urlpatterns = [
    path('admin/', admin.site.urls),
    path('taxis/', include(('taxis.urls', 'taxis'), namespace='taxis')),
    path('', redirect_root, name='root_redirect'),  # Raíz que redirige
    path('captcha/', include('captcha.urls')),
    path('accounts/', include('django.contrib.auth.urls')),  # Login, logout, etc.
]
