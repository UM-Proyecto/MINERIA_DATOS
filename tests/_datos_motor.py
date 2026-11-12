"""Cargador mínimo del JSON de datos del simulador, solo para las pruebas del motor.

Arma el objeto con las mismas claves que fija el contrato para data/processed/simulador/datos_app.json,
leyendo directo los CSV de SCRUM-55 y SCRUM-54. Así las pruebas del motor no dependen de
src/simulador/preparar_datos.py (lo hace otro frente). No es el preparador de la app.
"""
import csv
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SCRUM55 = RAIZ / "data" / "processed" / "scrum-55"
SCRUM54 = RAIZ / "data" / "processed" / "scrum-54"

NUMERO = re.compile(r"^-?\d+(\.\d+)?$")
# Columnas que parecen número pero son códigos.
TEXTO = {"repuesto_id", "codigo_carparts", "proveedor_id"}

PARAMETROS = {"costo_pedido_bs": 350, "costo_capital_mensual": 0.015, "simulaciones": 1500, "semilla": 20261112}


def _leer(ruta):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _tipar(fila):
    salida = {}
    for clave, valor in fila.items():
        if clave not in TEXTO and NUMERO.match(valor or ""):
            salida[clave] = int(valor) if "." not in valor else float(valor)
        else:
            salida[clave] = valor
    return salida


def cargar():
    repuestos = [_tipar(f) for f in _leer(SCRUM55 / "repuestos.csv")]
    proveedores = [_tipar(f) for f in _leer(SCRUM55 / "proveedores.csv")]
    ventas = {}
    for f in _leer(SCRUM55 / "ventas_mensuales.csv"):
        ventas.setdefault(f["repuesto_id"], []).append([f["mes"], int(f["unidades"])])
    for serie in ventas.values():
        serie.sort(key=lambda x: x[0])
    tco = _leer(SCRUM54 / "tco_bcb_diario.csv")
    serie_tc = [[f["fecha"], float(f["tco_bs_por_usd"])] for f in tco]
    ultimo = tco[-1]
    puntos, conteo = [], {}
    for f in _leer(SCRUM55 / "clasificacion_2674.csv"):
        conteo[f["tipo_demanda"]] = conteo.get(f["tipo_demanda"], 0) + 1
        if f["adi"] and f["cv2"]:
            puntos.append([float(f["adi"]), float(f["cv2"]), f["tipo_demanda"]])
    return {
        "generado": "2026-11-12", "corte": "2026-11-10",
        "tc": {"oficial": {"valor": float(ultimo["tco_bs_por_usd"]), "fecha": ultimo["fecha"], "fuente": ultimo["fuente"]},
               "serie": serie_tc,
               "paralelo": {"valor": 11.99, "fecha": "2026-10-23", "fuente": "promedio de plataformas P2P",
                            "marca": "PRIVADO"}},
        "repuestos": repuestos,
        "proveedores": proveedores,
        "ventas": ventas,
        "clasificacion": {"puntos": puntos, "conteo": conteo},
        "parametros": dict(PARAMETROS),
    }
