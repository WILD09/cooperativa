# 🚕 Sistema de Gestión de Cooperativa de Taxis

Sistema web completo para administrar cooperativas de taxis desarrollado con Django.

## 📋 Características

- ✅ Gestión de afiliados (conductores)
- ✅ Registro de vehículos
- ✅ Sistema de pagos mensuales
- ✅ Adelanto de cuotas
- ✅ Generación de comprobantes (PDF)
- ✅ Exportación de reportes (Excel)
- ✅ Historial de movimientos
- ✅ Auditoría completa
- ✅ Sistema de autenticación con roles
- ✅ Modo oscuro/claro
- ✅ Responsive design

## 🔧 Requisitos

- **Python:** 3.10+ (recomendado 3.14)
- **Base de datos:** PostgreSQL (recomendado) o SQLite
- **Sistema operativo:** Windows, Linux o macOS

## 🚀 Instalación en Nueva Computadora

### 1️⃣ Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/cooperativa-taxis.git
cd cooperativa-taxis

2️⃣ Crear Entorno Virtual
python -m venv env_new
.\env_new\Scripts\activate

3️⃣ Instalar Dependencias
pip install --upgrade pip
pip install -r requirements.txt

4️⃣ Configurar Variables de Entorno
Crea un archivo .env en la raíz del proyecto:

# Django
SECRET_KEY=tu-clave-secreta-muy-larga-y-aleatoria
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de datos PostgreSQL (Opcional)
DB_NAME=cooperativa_wilson
DB_USER=postgres
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432

# Email (Gmail)
EMAIL_HOST_USER=tu_correo@gmail.com
EMAIL_HOST_PASSWORD=tu_app_password
DEFAULT_FROM_EMAIL="Cooperativa <tu_correo@gmail.com>"

# Superusuario inicial
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@cooperativa.com
DJANGO_SUPERUSER_PASSWORD=tu_password_seguro

5️⃣ Configurar Base de Datos
# Instalar PostgreSQL primero
# Crear base de datos:
psql -U postgres
CREATE DATABASE cooperativa_wilson;
\q

# Migrar
python manage.py migrate

6️⃣ Crear Superusuario
python manage.py createsuperuser
# Seguir las instrucciones

7️⃣ Ejecutar Servidor
python manage.py runserver



🔐 Seguridad
Cambiar SECRET_KEY en producción
Configurar DEBUG=False en producción
Usar contraseñas de aplicación para Gmail
Habilitar HTTPS en producción



📧 Configuración de Email
Para usar Gmail:
Activar verificación en 2 pasos
Generar contraseña de aplicación: https://myaccount.google.com/apppasswords
Usar esa contraseña en EMAIL_HOST_PASSWORD


📦 PASOS PARA SUBIR A GITHUB
bash
# 1. Inicializar Git (si no está inicializado)
git init

# 2. Agregar .gitignore
git add .gitignore

# 3. Agregar archivos
git add .
git status  # Verificar que .env NO esté incluido

# 4. Commit inicial
git commit -m "Initial commit - Sistema Cooperativa v1.0"

# 5. Crear repositorio en GitHub
# Ir a: https://github.com/new

# 6. Conectar con GitHub
git remote add origin https://github.com/tu-usuario/cooperativa-taxis.git
git branch -M main
git push -u origin main