"""SCRUM-74: catálogo de los 30 repuestos del simulador, con nombre, categoría, descripción e imagen.

carparts (SCRUM-55) solo trae un código numérico por repuesto: no dice qué pieza es. Para que el cliente vea un
catálogo, cada repuesto recibe un nombre, una categoría y una descripción ILUSTRATIVOS con una regla fija:
- se ordenan los 30 repuestos por costo unitario en USD (SINTÉTICO, SCRUM-55), de menor a mayor;
- se reparten en ocho categorías ordenadas de la pieza más barata a la más cara (4, 4, 4, 4, 4, 4, 3 y 3);
- dentro de cada categoría, la variante sigue el mismo orden de costo.
Así una bujía no queda más cara que un kit de embrague. La regla no dice nada sobre las ventas reales.

Cada categoría tiene una foto con licencia libre, recomprimida en data/raw/scrum-74/imagenes/. Su título, autor,
licencia y página de origen están en data/raw/scrum-74/fuentes_imagenes.csv.

Uso, desde cualquier carpeta:
    python3 src/scrum-74/armar_catalogo.py

Solo usa la biblioteca estándar.
"""
import csv
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
REPUESTOS = BASE / "data/processed/scrum-55/repuestos.csv"
FUENTES = BASE / "data/raw/scrum-74/fuentes_imagenes.csv"
SALIDA = BASE / "data/processed/scrum-74/catalogo.csv"

# (categoría, imagen, cuántos repuestos, descripción, variantes). De la más barata a la más cara.
CATEGORIAS = [
    ("Bujía de encendido", "bujia.jpg", 4, "Enciende la mezcla de aire y combustible en cada cilindro. Se cambia según el kilometraje del fabricante.",
     ["de níquel", "de cobre", "de iridio", "de platino"]),
    ("Filtro de aceite", "filtro_aceite.jpg", 4, "Retiene la suciedad del aceite del motor. Se cambia junto con el aceite.",
     ["de rosca, motor a gasolina", "de rosca, motor diésel", "de cartucho", "de alto caudal"]),
    ("Pastillas de freno", "pastillas_freno.jpg", 4, "Rozan contra el disco para frenar la rueda. Se gastan con el uso y se cambian por juego.",
     ["delanteras, orgánicas", "traseras, semimetálicas", "delanteras, semimetálicas", "delanteras, cerámicas"]),
    ("Correa de distribución", "correa_distribucion.jpg", 4, "Sincroniza el cigüeñal con las válvulas. Si se corta, el motor puede dañarse.",
     ["para motor 1.4", "para motor 1.6", "para motor 2.0", "para motor diésel 2.5"]),
    ("Cubo y rodamiento de rueda", "rodamiento_rueda.jpg", 4, "Permite que la rueda gire sin juego. Un rodamiento gastado hace ruido al girar.",
     ["trasero", "delantero", "delantero con sensor ABS", "para camioneta"]),
    ("Disco de freno", "disco_freno.jpg", 4, "Gira con la rueda y recibe las pastillas. Se cambia cuando pierde espesor o se deforma.",
     ["sólido, trasero", "sólido, delantero", "ventilado, delantero", "ventilado, para camioneta"]),
    ("Amortiguador", "amortiguador.jpg", 3, "Controla el rebote de la suspensión y mantiene la rueda pegada al camino.",
     ["trasero a gas", "delantero a gas", "delantero, para camioneta"]),
    ("Kit de embrague", "kit_embrague.jpg", 3, "Disco, plato y collarín que conectan el motor con la caja de cambios.",
     ["para motor 1.6", "para motor diésel 2.5", "reforzado, para camioneta"]),
]

COLUMNAS = ["repuesto_id", "codigo_carparts", "nombre", "categoria", "descripcion", "imagen", "origen_dato", "marca"]


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def armar(repuestos, fuentes):
    if sum(c[2] for c in CATEGORIAS) != len(repuestos):
        raise SystemExit(f"Las categorías cubren {sum(c[2] for c in CATEGORIAS)} repuestos y hay {len(repuestos)}")
    imagenes = {f["archivo"] for f in fuentes}
    orden = sorted(repuestos, key=lambda r: (float(r["costo_unitario_usd"]), r["repuesto_id"]))
    filas, i = [], 0
    for nombre, imagen, n, descripcion, variantes in CATEGORIAS:
        if imagen not in imagenes:
            raise SystemExit(f"La imagen {imagen} no tiene su fuente en {FUENTES}")
        if len(variantes) != n:
            raise SystemExit(f"{nombre}: {n} repuestos y {len(variantes)} variantes")
        for v in variantes:
            r = orden[i]
            i += 1
            filas.append({"repuesto_id": r["repuesto_id"], "codigo_carparts": r["codigo_carparts"],
                          "nombre": f"{nombre} {v}", "categoria": nombre, "descripcion": descripcion, "imagen": imagen,
                          "origen_dato": "ILUSTRATIVO: nombre y categoría asignados por costo; carparts solo trae el código",
                          "marca": "ILUSTRATIVO"})
    return sorted(filas, key=lambda f: f["repuesto_id"])


def main():
    filas = armar(leer(REPUESTOS), leer(FUENTES))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    tmp = SALIDA.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    tmp.replace(SALIDA)
    print(f"{SALIDA.relative_to(BASE)}: {len(filas)} repuestos en {len(CATEGORIAS)} categorías")


if __name__ == "__main__":
    main()
