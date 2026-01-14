import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cooperativa.settings') 
django.setup()

from taxis.models import Municipio, Parroquia

# DATOS MAESTROS
datos_guarico = [
    ("Juan Germán Roscio", ["San Juan de los Morros (Capital)", "Parapara", "Cantagallo"]),
    ("Francisco de Miranda", ["Calabozo (Capital)", "El Rastro", "Guardatinajas", "El Calvario"]),
    ("Leonardo Infante", ["Valle de la Pascua (Capital)", "Espino"]),
    ("José Tadeo Monagas", ["Altagracia de Orituco (Capital)", "San Rafael de Orituco", "San Francisco de Javier de Lezama", "Paso Real de Macaira", "Libertad de Orituco", "San Francisco de Macaira", "Soublette"]),
    ("Julián Mellado", ["El Sombrero (Capital)", "Sosa"]),
    ("Ortiz", ["Ortiz (Capital)", "San Francisco de Tiznados", "San José de Tiznados", "San Lorenzo de Tiznados"]),
    ("San Gerónimo de Guayabal", ["Guayabal (Capital)", "Cazorla"]),
    ("Las Mercedes", ["Las Mercedes del Llano (Capital)", "Cabruta", "Santa Rita de Manapire"]),
    ("Pedro Zaraza", ["Zaraza (Capital)", "San José de Unare"]),
    ("José Félix Ribas", ["Tucupido (Capital)", "San Rafael de Laya"]),
    ("Santa María de Ipire", ["Santa María de Ipire (Capital)", "Altamira"]),
    ("Camaguán", ["Camaguán (Capital)", "Puerto Miranda", "Uverito"]),
    ("El Socorro", ["El Socorro (Capital)"]),
    ("Chaguaramas", ["Chaguaramas (Capital)"]),
    ("San José de Guaribe", ["San José de Guaribe (Capital)"])
]

def poblar_db():
    print("----- ACTUALIZANDO MUNICIPIOS Y PARROQUIAS -----")
    for mun_nombre, parroquias in datos_guarico:
        mun, _ = Municipio.objects.get_or_create(nombre=mun_nombre)
        print(f"📍 {mun_nombre}")
        for parr_nombre in parroquias:
            Parroquia.objects.get_or_create(municipio=mun, nombre=parr_nombre)
    print("✅ Base de datos sincronizada.")

if __name__ == '__main__':
    poblar_db()
