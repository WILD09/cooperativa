import os
import sys
import django
from django.conf import settings

# Setup Django
sys.path.insert(0, r'C:\Users\Williams\OneDrive\Desktop\cooperativa')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cooperativa.settings')
django.setup()

print(f"BASE_DIR: {settings.BASE_DIR}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")

paths_to_check = [
    os.path.join(settings.STATIC_ROOT, 'img', 'logo_transporte.png'),
    os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_transporte.png'),
    os.path.join(settings.BASE_DIR, 'media', 'vehiculos', 'logo_transporte.png'),
]

for p in paths_to_check:
    exists = os.path.exists(p)
    print(f"Path: {p} | Exists: {exists}")
