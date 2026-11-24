"""Decisión D9 (24-11-2026): tabla repuesto ↔ vehículo para filtrar el catálogo por marca, modelo y año.

Ninguna fuente del proyecto trae a qué vehículo sirve cada repuesto: carparts (SCRUM-55) solo da un código numérico y
el campo `marca` del catálogo es la PROCEDENCIA del dato («ILUSTRATIVO» o «SINTÉTICO / ADAPTADO»), no la marca del
auto. Esta tabla es, por lo tanto, ILUSTRATIVA: sirve para que el prototipo muestre los filtros con datos coherentes,
no para decir que una pieza calza en un vehículo real.

Cómo se arma (siempre igual, sin nada escrito a mano fila por fila):
1. VEHICULOS es un parque de modelos comunes en Bolivia, solo de las 10 marcas con las que trabaja MULTIPARTES
   (data/raw/tienda/contenido_sitio.json → marcas_vehiculos). Cada modelo tiene una generación (años), un motor, el
   combustible, la cilindrada y el tipo (auto, SUV, camioneta o furgoneta). Los motores y los años son los conocidos de cada
   generación, redondeados; no se verificaron contra un catálogo de fabricante.
2. Cada repuesto se lee por su nombre (data/processed/scrum-74/catalogo.csv) y se le asigna el conjunto de vehículos
   que cumplen la regla de su nombre (REGLAS): «motor 1.6» → motores a gasolina de 1.6; «diésel 2.5» → diésel de 2.5;
   «para camioneta» → camionetas; «motor diésel» → todos los diésel; las bujías → solo motores a gasolina; etc.
3. Si la regla deja más de MAXIMO vehículos, se eligen MAXIMO con una semilla fija (SEMILLA + número del repuesto),
   para que la tabla salga idéntica en cada corrida y un repuesto no sirva a medio parque.
4. Cada fila de salida es una aplicación: repuesto_id, marca, modelo, anio_desde, anio_hasta, motor y
   procedencia=ILUSTRATIVO. Un repuesto tiene varias filas (relación de muchos a muchos).

Si un repuesto no encaja en ninguna regla, el script se detiene: así no queda un repuesto sin aplicación sin aviso.

Uso, desde cualquier carpeta:
    python3 src/scrum-74/armar_aplicaciones.py

Solo usa la biblioteca estándar.
"""
import csv
import json
import random
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
CATALOGO = BASE / "data/processed/scrum-74/catalogo.csv"
CONTENIDO = BASE / "data/raw/tienda/contenido_sitio.json"
SALIDA = BASE / "data/processed/scrum-74/aplicaciones.csv"

SEMILLA = 20261124
MAXIMO = 6  # aplicaciones por repuesto como máximo
CAMPOS = ("repuesto_id", "marca", "modelo", "anio_desde", "anio_hasta", "motor", "procedencia")

# (marca, modelo, año desde, año hasta, combustible, cilindrada, tipo). Modelos comunes en Bolivia. Algunos tienen dos
# generaciones (Hilux, Frontier, Corolla, Swift) con motores distintos: así el filtro por año cambia el resultado.
VEHICULOS = [
    ("TOYOTA", "Corolla", 2008, 2019, "gasolina", "1.6", "auto"),
    ("TOYOTA", "Corolla", 2020, 2024, "gasolina", "1.8", "auto"),
    ("TOYOTA", "Yaris", 2006, 2013, "gasolina", "1.5", "auto"),
    ("TOYOTA", "RAV4", 2006, 2012, "gasolina", "2.0", "suv"),
    ("TOYOTA", "Hilux", 2005, 2015, "diésel", "2.5", "camioneta"),
    ("TOYOTA", "Hilux", 2005, 2015, "gasolina", "2.7", "camioneta"),
    ("TOYOTA", "Hilux", 2016, 2023, "diésel", "2.4", "camioneta"),
    ("TOYOTA", "Hiace", 2005, 2018, "diésel", "2.5", "furgoneta"),
    ("TOYOTA", "Land Cruiser Prado", 2003, 2009, "diésel", "3.0", "suv"),
    ("NISSAN", "March", 2011, 2020, "gasolina", "1.6", "auto"),
    ("NISSAN", "Sentra", 2007, 2012, "gasolina", "2.0", "auto"),
    ("NISSAN", "X-Trail", 2007, 2013, "gasolina", "2.0", "suv"),
    ("NISSAN", "Frontier", 2008, 2015, "diésel", "2.5", "camioneta"),
    ("NISSAN", "Frontier", 2016, 2023, "diésel", "2.3", "camioneta"),
    ("SUZUKI", "Swift", 2011, 2017, "gasolina", "1.4", "auto"),
    ("SUZUKI", "Swift", 2018, 2024, "gasolina", "1.2", "auto"),
    ("SUZUKI", "Vitara", 2015, 2022, "gasolina", "1.6", "suv"),
    ("SUZUKI", "Grand Vitara", 2006, 2014, "gasolina", "2.0", "suv"),
    ("MAZDA", "Mazda3", 2004, 2013, "gasolina", "1.6", "auto"),
    ("MAZDA", "CX-5", 2012, 2017, "gasolina", "2.0", "suv"),
    ("MAZDA", "BT-50", 2006, 2011, "diésel", "2.5", "camioneta"),
    ("MITSUBISHI", "Lancer", 2007, 2017, "gasolina", "1.6", "auto"),
    ("MITSUBISHI", "Outlander", 2007, 2012, "gasolina", "2.0", "suv"),
    ("MITSUBISHI", "L200", 2006, 2015, "diésel", "2.5", "camioneta"),
    ("HONDA", "Fit", 2008, 2014, "gasolina", "1.5", "auto"),
    ("HONDA", "Civic", 2006, 2011, "gasolina", "1.8", "auto"),
    ("HONDA", "CR-V", 2007, 2011, "gasolina", "2.0", "suv"),
    ("HYUNDAI", "Accent", 2011, 2017, "gasolina", "1.4", "auto"),
    ("HYUNDAI", "Tucson", 2010, 2015, "gasolina", "2.0", "suv"),
    ("HYUNDAI", "H-1", 2008, 2020, "diésel", "2.5", "furgoneta"),
    ("KIA", "Rio", 2011, 2017, "gasolina", "1.4", "auto"),
    ("KIA", "Sportage", 2011, 2015, "gasolina", "2.0", "suv"),
    ("KIA", "Sorento", 2003, 2009, "diésel", "2.5", "suv"),
    ("DAIHATSU", "Terios", 2006, 2017, "gasolina", "1.5", "suv"),
    ("DAIHATSU", "Sirion", 2005, 2012, "gasolina", "1.3", "auto"),
    ("ISUZU", "D-Max", 2012, 2019, "diésel", "2.5", "camioneta"),
    ("ISUZU", "D-Max", 2012, 2019, "diésel", "3.0", "camioneta"),
]


def motor(v):
    return f"{v[5]} {v[4]}"


def es(comb=None, cil=None, tipos=None, desde_min=None):
    """Arma un filtro de vehículos. Todas las condiciones dadas se tienen que cumplir."""
    def f(v):
        return ((comb is None or v[4] == comb) and (cil is None or v[5] == cil)
                and (tipos is None or v[6] in tipos) and (desde_min is None or v[2] >= desde_min))
    return f


GASOLINA = es(comb="gasolina")
LIVIANO = es(tipos={"auto", "suv"})
# Regla por nombre: el primer patrón que aparece en el nombre (en minúsculas) decide. El orden importa: lo específico
# (cilindrada, combustible, camioneta) va antes que lo genérico de cada familia.
REGLAS = [
    (r"diésel 2\.5", es(comb="diésel", cil="2.5")),
    (r"motor 1\.4", es(comb="gasolina", cil="1.4")),
    (r"motor 1\.6", es(comb="gasolina", cil="1.6")),
    (r"motor 2\.0", es(comb="gasolina", cil="2.0")),
    (r"motor diésel", es(comb="diésel")),
    (r"motor a gasolina", GASOLINA),
    (r"para camioneta", es(tipos={"camioneta"})),
    (r"sensor abs", es(tipos={"auto", "suv"}, desde_min=2008)),  # ABS de serie en las generaciones más nuevas
    (r"^bujía", GASOLINA),                                        # las bujías de encendido solo van en motores a gasolina
    (r"ventilado", es(tipos={"suv"})),                            # disco ventilado: vehículos más pesados
    (r"embrague", LIVIANO),
    (r"filtro de aceite", LIVIANO),
    (r"pastillas|disco|cubo|amortiguador", LIVIANO),
]


def regla(nombre):
    n = nombre.lower()
    for patron, filtro in REGLAS:
        if re.search(patron, n):
            return patron, filtro
    raise SystemExit(f"Ningún patrón de REGLAS cubre el repuesto «{nombre}»")


def armar(catalogo, marcas_validas):
    faltan = {v[0] for v in VEHICULOS} - set(marcas_validas)
    if faltan:
        raise SystemExit(f"Marcas fuera de marcas_vehiculos: {sorted(faltan)}")
    filas = []
    for c in sorted(catalogo, key=lambda r: r["repuesto_id"]):
        _, filtro = regla(c["nombre"])
        candidatos = [v for v in VEHICULOS if filtro(v)]
        if not candidatos:
            raise SystemExit(f"La regla de «{c['nombre']}» no deja ningún vehículo")
        if len(candidatos) > MAXIMO:
            azar = random.Random(SEMILLA + int(c["repuesto_id"].split("-")[1]))
            candidatos = sorted(azar.sample(candidatos, MAXIMO), key=VEHICULOS.index)
        for v in candidatos:
            filas.append({"repuesto_id": c["repuesto_id"], "marca": v[0], "modelo": v[1], "anio_desde": v[2],
                          "anio_hasta": v[3], "motor": motor(v), "procedencia": "ILUSTRATIVO"})
    return filas


def validar(filas, marcas_validas, ids, anio_max=2026):
    """Lista de problemas de la tabla; vacía si está bien. La usan main() y las pruebas (con su control negativo)."""
    problemas = []
    for i, r in enumerate(filas, start=2):  # línea del CSV, contando el encabezado
        try:
            desde, hasta = int(r["anio_desde"]), int(r["anio_hasta"])
        except (TypeError, ValueError):
            problemas.append(f"línea {i}: años no numéricos"); continue
        if not 1990 <= desde <= hasta <= anio_max:
            problemas.append(f"línea {i}: años {desde}-{hasta} fuera de 1990-{anio_max} o invertidos")
        if r["marca"] not in marcas_validas:
            problemas.append(f"línea {i}: marca {r['marca']!r} fuera de marcas_vehiculos")
        if r["procedencia"] != "ILUSTRATIVO":
            problemas.append(f"línea {i}: procedencia {r['procedencia']!r}, debe ser ILUSTRATIVO")
        if r["repuesto_id"] not in ids:
            problemas.append(f"línea {i}: {r['repuesto_id']} no está en el catálogo")
        if not r["modelo"] or not r["motor"]:
            problemas.append(f"línea {i}: falta modelo o motor")
    sin = sorted(set(ids) - {r["repuesto_id"] for r in filas})
    if sin:
        problemas.append(f"repuestos sin aplicación: {sin}")
    return problemas


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    marcas = json.loads(CONTENIDO.read_text(encoding="utf-8"))["marcas_vehiculos"]
    catalogo = leer(CATALOGO)
    filas = armar(catalogo, marcas)
    problemas = validar(filas, marcas, {c["repuesto_id"] for c in catalogo})
    if problemas:
        raise SystemExit("La tabla de aplicaciones no pasa la validación:\n" + "\n".join(problemas))
    with open(SALIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)
    print(f"{SALIDA.relative_to(BASE)}: {len(filas)} aplicaciones de {len({r['repuesto_id'] for r in filas})} repuestos, "
          f"{len({(r['marca'], r['modelo']) for r in filas})} modelos")


if __name__ == "__main__":
    main()
