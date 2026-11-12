"""Datos de la app del simulador de compras de MULTIPARTES (SCRUM-64).

Junta en un solo JSON lo que la app necesita y que ya existe en el repositorio:
- los 30 repuestos, los 10 proveedores, las ventas mensuales y la clasificación de las 2.674 series (SCRUM-55);
- el tipo de cambio oficial diario del BCB (SCRUM-54);
- el dólar paralelo del 23-10-2026 (HU-32), que se muestra marcado PRIVADO;
- los parámetros del motor. `costo_pedido_bs` y `costo_capital_mensual` son SINTÉTICOS (supuestos del equipo).

No calcula nada del motor: solo lee, convierte números y ordena.

Uso, desde la raíz del repositorio:
    python3 src/simulador/preparar_datos.py

Solo usa la biblioteca estándar. Las rutas salen de la ubicación de este archivo.
"""
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
S55 = BASE / "data/processed/scrum-55"
TCO = BASE / "data/processed/scrum-54/tco_bcb_diario.csv"
PARALELO = BASE / "data/raw/hu-32/insumos_publicos/puntos_documentados.csv"
SALIDA = BASE / "data/processed/simulador/datos_app.json"


# Parámetros del motor. Los dos primeros son SINTÉTICOS: no hay dato de MULTIPARTES para ellos.
PARAMETROS = {
    "costo_pedido_bs": 350,          # trámites y despacho de cada pedido (supuesto del equipo)
    "costo_capital_mensual": 0.015,  # costo de tener dinero en stock, 1,5 % al mes (supuesto del equipo)
    "simulaciones": 1500,
    "semilla": 20261112,
}

# Columnas que son códigos aunque parezcan números.
TEXTO = {"repuesto_id", "codigo_carparts", "proveedor_id"}


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def numero(valor):
    """'12' -> 12, '5.498' -> 5.498; lo demás queda como texto."""
    try:
        return int(valor)
    except ValueError:
        pass
    try:
        return float(valor)
    except ValueError:
        return valor


def convertir(fila):
    return {k: (v if k in TEXTO else numero(v)) for k, v in fila.items()}


def paralelo():
    """Punto documentado del dólar paralelo (promedio P2P). Se busca por serie y fecha, no por número de línea."""
    with open(PARALELO, encoding="utf-8-sig", newline="") as f:
        for fila in csv.reader(f):
            if len(fila) > 2 and fila[0] == "PARALELO_P2P_VENTA" and fila[1] == "2026-10-23":
                return {"valor": float(fila[2]), "fecha": fila[1],
                        "fuente": "Promedio de venta en 8 plataformas P2P (dolarbolivia.net), consultado el 2026-10-25",
                        "marca": "PRIVADO"}
    raise SystemExit(f"No se encontró el dólar paralelo del 2026-10-23 en {PARALELO}")


def preparar():
    repuestos = [convertir(r) for r in leer(S55 / "repuestos.csv")]
    repuestos.sort(key=lambda r: r["repuesto_id"])
    proveedores = [convertir(r) for r in leer(S55 / "proveedores.csv")]
    proveedores.sort(key=lambda r: r["proveedor_id"])

    ventas = defaultdict(list)
    for r in leer(S55 / "ventas_mensuales.csv"):
        ventas[r["repuesto_id"]].append([r["mes"], int(r["unidades"])])
    for serie in ventas.values():
        serie.sort()

    tco = sorted(leer(TCO), key=lambda r: r["fecha"])
    ultimo = tco[-1]
    # El corte es el último día publicado por el BCB (SCRUM-54); no se fija a mano para que la app
    # tome sola el dato nuevo cada vez que se actualiza el CSV.

    clasif = leer(S55 / "clasificacion_2674.csv")
    puntos = [[float(r["adi"]), float(r["cv2"]), r["tipo_demanda"]]
              for r in clasif if r["tipo_demanda"] != "sin clasificar" and r["adi"] and r["cv2"]]
    conteo = Counter(r["tipo_demanda"] for r in clasif)
    conteo.setdefault("erratica", 0)  # el cuadrante existe aunque carparts no tenga ninguna

    return {
        "generado": date.today().isoformat(),
        "corte": ultimo["fecha"],
        "tc": {
            "oficial": {"valor": float(ultimo["tco_bs_por_usd"]), "fecha": ultimo["fecha"], "fuente": ultimo["fuente"]},
            "serie": [[r["fecha"], float(r["tco_bs_por_usd"])] for r in tco],
            "paralelo": paralelo(),
        },
        "repuestos": repuestos,
        "proveedores": proveedores,
        "ventas": dict(sorted(ventas.items())),
        "clasificacion": {"puntos": puntos, "conteo": dict(sorted(conteo.items()))},
        "parametros": PARAMETROS,
    }


def main():
    datos = preparar()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{SALIDA.relative_to(BASE)}: {len(datos['repuestos'])} repuestos, {len(datos['proveedores'])} proveedores, "
          f"{len(datos['clasificacion']['puntos'])} puntos, {SALIDA.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
