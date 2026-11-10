"""Cruce del tipo de cambio con compras y ventas (insumo de la pantalla de decisión de compra, HU-12).

Mide, con los CSV del repositorio, qué se puede y qué no se puede concluir sobre el efecto del
dólar en las decisiones de compra. Imprime los resultados y los guarda en
data/processed/hu-12/analisis_tc.json para que la pantalla y el informe usen los mismos números.

Uso, desde la raíz del repositorio:
    python src/hu-12/analisis_tc.py

Cuando lleguen datos reales de MULTIPARTES (facturas de compra y ventas con precio), basta reemplazar
los tres CSV de entrada por los reales con las mismas columnas y volver a correr este archivo.
Solo usa la biblioteca estándar.
"""
import csv
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
COMPRAS = BASE / "data/processed/hu-34/compras_limpias.csv"
VENTAS = BASE / "data/processed/hu-34/ventas_limpias.csv"
TC = BASE / "data/processed/hu-32/tc_series_diaria.csv"
SALIDA = BASE / "data/processed/hu-12/analisis_tc.json"


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else float("nan")


def dlog(serie):
    return [math.log(serie[i + 1] / serie[i]) for i in range(len(serie) - 1)]


def main():
    compras, ventas, tc = leer(COMPRAS), leer(VENTAS), leer(TC)
    res = {}

    # 1. El dólar oficial (BCB) frente al dólar que registran las compras
    tco = {r["fecha"]: float(r["valor"]) for r in tc if r["id_serie"] == "TCO_BCB"}
    inicio = min(tco)
    solape = [r for r in compras if r["fecha_pedido"] >= inicio]
    usado = [float(r["tipo_cambio_bs_usd"]) for r in solape]
    oficial = [tco[r["fecha_pedido"]] for r in solape if r["fecha_pedido"] in tco]
    res["solape"] = {
        "desde": inicio, "compras_en_solape": len(solape), "compras_total": len(compras),
        "usado_min": min(usado), "usado_max": max(usado),
        "oficial_min": min(oficial), "oficial_max": max(oficial),
        "brecha_media_pct": round((st.mean(oficial) / st.mean(usado) - 1) * 100, 1),
    }

    # 2. Volatilidad del dólar oficial (retorno logarítmico diario y su equivalente a 30 días)
    fechas = sorted(tco)
    rd = dlog([tco[f] for f in fechas])
    res["volatilidad"] = {
        "observaciones": len(fechas), "desvio_diario": round(st.pstdev(rd), 5),
        "desvio_30_dias": round(st.pstdev(rd) * math.sqrt(30), 4),
        "variacion_total_pct": round((tco[fechas[-1]] / tco[fechas[0]] - 1) * 100, 1),
        "primero": [fechas[0], tco[fechas[0]]], "ultimo": [fechas[-1], tco[fechas[-1]]],
        "maximo": max(tco.values()),
    }

    # 3. ¿El precio de venta sigue al dólar? Por mes y categoría
    meses = sorted({r["fecha"][:7] for r in ventas})[:-1]  # sin el último mes, incompleto
    tc_mes = defaultdict(list)
    for r in compras:
        tc_mes[r["fecha_pedido"][:7]].append(float(r["tipo_cambio_bs_usd"]))
    tc_m = [st.mean(tc_mes[m]) for m in meses]
    precios = defaultdict(lambda: defaultdict(list))
    for r in ventas:
        if r["precio_unitario_bs"] and r["fecha"][:7] in meses:
            precios[r["categoria"]][r["fecha"][:7]].append(float(r["precio_unitario_bs"]))
    por_cat = {}
    for cat, d in sorted(precios.items()):
        p = [st.mean(d[m]) for m in meses]
        por_cat[cat] = {
            "corr_variacion_precio_vs_dolar": round(corr(dlog(tc_m), dlog(p)), 3),
            "precio_sobre_dolar_min": round(min(a / b for a, b in zip(p, tc_m)), 2),
            "precio_sobre_dolar_max": round(max(a / b for a, b in zip(p, tc_m)), 2),
        }
    res["traspaso_al_precio"] = {"meses": len(meses), "por_categoria": por_cat}

    # 4. ¿Se compra más o menos según el dólar?
    unidades = defaultdict(int)
    for r in compras:
        unidades[r["fecha_pedido"][:7]] += int(r["cantidad"])
    u = [unidades[m] for m in meses]
    res["compras_vs_dolar"] = {
        "corr_nivel": round(corr(tc_m, u), 2), "corr_variacion": round(corr(dlog(tc_m), dlog(u)), 2),
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
