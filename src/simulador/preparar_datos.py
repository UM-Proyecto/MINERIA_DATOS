"""Datos de la app del simulador de compras de MULTIPARTES (SCRUM-64).

Junta en un solo JSON lo que la app necesita y que ya existe en el repositorio:
- los 30 repuestos, los 10 proveedores, las ventas mensuales y la clasificación de las 2.674 series (SCRUM-55);
- el tipo de cambio oficial diario del BCB (SCRUM-54);
- el dólar paralelo del 23-10-2026 (HU-32), que se muestra marcado PRIVADO;
- el catálogo ILUSTRATIVO de SCRUM-74 (nombre, categoría, descripción e imagen de cada repuesto) y la fuente de
  cada foto; las fotos las incrusta generar_app.py;
- los clientes SINTÉTICOS de SCRUM-76 y sus compras (repartidas sobre las ventas reales);
- el resultado del clasificador de SCRUM-80 (probabilidad de venta del mes siguiente, con su validación), que calcula
  src/scrum-80/predecir_venta.py; sin ese archivo la app muestra que falta correr el script;
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
PARALELO = BASE / "data/processed/scrum-54/dolar_paralelo_diario.csv"  # serie diaria, referencia privada
CATALOGO = BASE / "data/processed/scrum-74/catalogo.csv"
FUENTES_IMG = BASE / "data/raw/scrum-74/fuentes_imagenes.csv"
CLIENTES = BASE / "data/processed/scrum-76/clientes.csv"
VENTAS_CLI = BASE / "data/processed/scrum-76/ventas_por_cliente.csv"
PREDICCION = BASE / "data/processed/scrum-80/prediccion.json"
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
    """Último valor de la serie diaria del dólar paralelo (src/scrum-54/obtener_paralelo.py). Es una referencia
    privada: no entra en ningún cálculo. No se fija la fecha: la app toma sola el valor nuevo cada día y, si la
    fuente no respondió, sigue con el último y muestra de qué día es."""
    filas = sorted(leer(PARALELO), key=lambda r: r["fecha"])
    if not filas:
        raise SystemExit(f"La serie del dólar paralelo está vacía: {PARALELO}")
    u = filas[-1]
    return {"valor": float(u["paralelo_bs_por_usd"]), "fecha": u["fecha"], "fuente": u["fuente"],
            "lectura": u["fecha_lectura"], "marca": u["marca"]}


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
        "catalogo": {"repuestos": sorted(leer(CATALOGO), key=lambda r: r["repuesto_id"]),
                     "fuentes": leer(FUENTES_IMG)},
        "clientes": {"lista": [{k: c[k] for k in ("cliente_id", "nombre", "tipo", "zona")} for c in leer(CLIENTES)],
                     "ventas": [[v["mes"], v["repuesto_id"], v["cliente_id"], int(v["unidades"])] for v in leer(VENTAS_CLI)]},
        "prediccion": json.loads(PREDICCION.read_text(encoding="utf-8")) if PREDICCION.exists() else None,
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
