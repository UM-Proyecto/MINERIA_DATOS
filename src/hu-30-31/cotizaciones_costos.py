"""HU-31 (SCRUM-7): registra los costos de importación con su respaldo.

Cada fila dice si es DOCUMENTADO (con su fuente), ESTIMACION (derivado de datos públicos) o PENDIENTE.
Las cotizaciones de proveedor salen de genera_datos_sinteticos.py mientras no lleguen las reales.
Sin argumentos usa los archivos que están junto a este script, así que corre igual en cualquier máquina.
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
PENDIENTES = ("seguro (separado del flete)", "costos de nacionalización y agente aduanero",
              "comisiones de gestión de importación", "flete terrestre Arica/Iquique -> Santa Cruz")


def leer(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        sys.exit(f"No se encontró el archivo requerido: {ruta}")
    with ruta.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def costos(flete_ref, ine, n_meses):
    filas = []
    for r in flete_ref:
        filas.append({
            "concepto": r["concepto"], "ruta_o_alcance": r["ruta"], "valor_min": r["valor_min_usd"],
            "valor_max": r["valor_max_usd"], "unidad": r["unidad"], "fecha_dato": r["fecha_dato"],
            "tipo_dato": "DOCUMENTADO", "respaldo": r["url"],
            "nota": r["tipo_fuente"] + ("; " + r["nota"] if r["nota"] else ""),
        })
    periodos = sorted({r["periodo"] for r in ine})[-n_meses:]
    acum = defaultdict(lambda: [0.0, 0.0, 0.0])  # kg, flete, fob
    for r in ine:
        if r["periodo"] in periodos and r["origen_grupo"] == "CHINA":
            a = acum[r["medio_transporte"]]
            a[0] += float(r["peso_bruto_kg"])
            a[1] += float(r["flete_seguro_usd"])
            a[2] += float(r["fob_usd"])
    for medio, (kg, fl, fob) in sorted(acum.items()):
        if kg <= 0 or fob <= 0:
            continue
        filas.append({
            "concepto": "flete y seguro implícito (CIF-FOB), origen China, medio " + medio,
            "ruta_o_alcance": "China -> frontera de Bolivia, 10 partidas de repuestos",
            "valor_min": "%.4f" % (fl / kg), "valor_max": "%.4f" % (fl / kg),
            "unidad": "USD por kg (%.1f%% del FOB)" % (100 * fl / fob),
            "fecha_dato": "%s a %s" % (periodos[0], periodos[-1]), "tipo_dato": "ESTIMACION",
            "respaldo": "INE importaciones, ine_repuestos_flete_implicito_mensual.csv",
            "nota": "promedio ponderado por kg sobre {:,.0f} kg; agregado declarado en aduana, no tarifa cotizada; flete y seguro vienen juntos".format(kg),
        })
    for concepto in PENDIENTES:
        filas.append({
            "concepto": concepto, "ruta_o_alcance": "pedido de MultiPartes", "valor_min": "", "valor_max": "",
            "unidad": "", "fecha_dato": "", "tipo_dato": "PENDIENTE", "respaldo": "",
            "nota": "sin documento de respaldo en las fuentes disponibles; pedir facturas al encargado de compras",
        })
    return filas


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--flete", default=RAIZ / "data" / "raw" / "hu-30-31" / "insumos_publicos" / "flete_referencias_puntuales.csv")
    ap.add_argument("--ine", default=RAIZ / "data" / "raw" / "hu-30-31" / "insumos_publicos" / "ine_repuestos_flete_implicito_mensual.csv")
    ap.add_argument("--salida", default=RAIZ / "data" / "processed" / "hu-30-31" / "hu31_costos_importacion.csv")
    ap.add_argument("--meses", type=int, default=12, help="meses del INE a promediar")
    a = ap.parse_args()
    filas = costos(leer(a.flete), leer(a.ine), a.meses)
    campos = ["concepto", "ruta_o_alcance", "valor_min", "valor_max", "unidad", "fecha_dato", "tipo_dato", "respaldo", "nota"]
    with Path(a.salida).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    tipos = defaultdict(int)
    for c in filas:
        tipos[c["tipo_dato"]] += 1
    print("costos:", dict(tipos))


if __name__ == "__main__":
    main()
