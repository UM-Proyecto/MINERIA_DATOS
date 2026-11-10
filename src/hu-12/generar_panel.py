"""Pantalla de decisión de compra de MULTIPARTES (HU-12).

Lee los CSV ya limpios del repositorio, calcula por repuesto (SKU) todo lo que el panel
necesita y lo incorpora a la plantilla HTML. No genera datos nuevos ni modifica los CSV.

Uso, desde la raíz del repositorio:
    python src/hu-12/analisis_tc.py
    python src/hu-12/generar_panel.py

Solo usa la biblioteca estándar. Las rutas salen de la ubicación de este archivo.
"""
import base64
import csv
import json
import statistics as st
from collections import defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
COMPRAS = BASE / "data/processed/hu-34/compras_limpias.csv"
VENTAS = BASE / "data/processed/hu-34/ventas_limpias.csv"
INVENTARIO = BASE / "data/processed/hu-34/inventario_limpio.csv"
TC = BASE / "data/processed/hu-32/tc_series_diaria.csv"
ANALISIS = BASE / "data/processed/hu-12/analisis_tc.json"  # lo genera analisis_tc.py
PLANTILLA = BASE / "src/hu-12/plantilla_panel.html"
LOGO = BASE / "src/hu-12/logo_multipartes.jpg"  # logotipo publicado en multipartes.com.bo
SALIDA = BASE / "reports/hu-12/MULTIPARTES_Decision_Compra.html"

MESES_PRUEBA = 6  # meses reservados para medir el error (MAE) de cada método


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def mes_de(fecha):
    return fecha[:7]


def metodos(serie, i):
    """Pronóstico del mes i con lo que se sabía antes de ese mes."""
    previos = serie[:i]
    return {
        "ultimo": previos[-1],
        "promedio3": sum(previos[-3:]) / len(previos[-3:]),
        "estacional": serie[i - 12] if i >= 12 else None,
    }


def preparar():
    compras, ventas, inv = leer(COMPRAS), leer(VENTAS), leer(INVENTARIO)

    ultima_fecha = max(r["fecha"] for r in ventas)
    mes_parcial = mes_de(ultima_fecha)
    # El último mes está incompleto: no entra en el historial mensual.
    meses = sorted({mes_de(r["fecha"]) for r in ventas if mes_de(r["fecha"]) != mes_parcial})

    por_sku_dia = defaultdict(dict)
    por_sku_mes = defaultdict(lambda: defaultdict(int))
    precios = defaultdict(list)
    categoria = {}
    for r in ventas:
        u = int(r["unidades_vendidas"])
        por_sku_dia[r["sku"]][r["fecha"]] = u
        categoria[r["sku"]] = r["categoria"]
        if mes_de(r["fecha"]) != mes_parcial:
            por_sku_mes[r["sku"]][mes_de(r["fecha"])] += u
        precios[r["sku"]].append((r["fecha"], float(r["precio_unitario_bs"])))

    stock = {}
    for r in sorted(inv, key=lambda x: x["fecha"]):
        stock[r["sku"]] = (r["fecha"], int(r["stock_final"]))

    prov = defaultdict(lambda: defaultdict(list))
    for r in compras:
        plazo = (date.fromisoformat(r["fecha_recepcion"]) - date.fromisoformat(r["fecha_pedido"])).days
        cant = int(r["cantidad"])
        prov[r["sku"]][r["proveedor"]].append(
            (r["fecha_pedido"], float(r["costo_unitario_usd"]), plazo, float(r["flete_bs"]) / cant)
        )

    productos = {}
    for sku in sorted(por_sku_dia):
        serie = [por_sku_mes[sku].get(m, 0) for m in meses]
        n = len(serie)
        prueba = range(n - MESES_PRUEBA, n)
        preds = {k: [] for k in ("ultimo", "promedio3", "estacional")}
        for i in prueba:
            for k, v in metodos(serie, i).items():
                preds[k].append(round(v, 1) if v is not None else None)
        reales = serie[n - MESES_PRUEBA:]
        mae = {}
        for k, p in preds.items():
            if all(x is not None for x in p):
                mae[k] = round(sum(abs(a - b) for a, b in zip(reales, p)) / len(reales), 2)
        siguiente = {k: (round(v, 1) if v is not None else None) for k, v in metodos(serie + [0], n).items()}

        dias = sorted(por_sku_dia[sku])
        ult90 = [por_sku_dia[sku][d] for d in dias[-90:]]
        fecha_stock, stock_final = stock[sku]
        pv = [p for _, p in sorted(precios[sku])[-30:]]
        # Margen que traen los datos: precio de venta sobre el costo en Bs de las compras recientes.
        recientes = sorted((r for r in compras if r["sku"] == sku), key=lambda r: r["fecha_pedido"])[-20:]
        costo_bs = st.mean(float(r["costo_unitario_usd"]) * float(r["tipo_cambio_bs_usd"]) for r in recientes)
        recargo = round((sum(pv) / len(pv)) / costo_bs, 3)

        proveedores = []
        for pid, filas in prov[sku].items():
            filas.sort()
            plazos = [f[2] for f in filas]
            proveedores.append({
                "plazo_desvio": round(st.pstdev(plazos), 2),
                "id": pid,
                "pedidos": len(filas),
                "costo_usd": round(sum(f[1] for f in filas) / len(filas), 2),
                "costo_ultimo_usd": filas[-1][1],
                "plazo_dias": round(sum(f[2] for f in filas) / len(filas), 1),
                "plazo_max": max(f[2] for f in filas),
                "flete_bs_unidad": round(sum(f[3] for f in filas) / len(filas), 2),
            })
        proveedores.sort(key=lambda p: p["id"])

        productos[sku] = {
            "categoria": categoria[sku],
            "mensual": serie,
            "prueba": {"reales": reales, "predicciones": preds, "mae": mae},
            "siguiente": siguiente,
            "demanda_dia_90": round(sum(ult90) / len(ult90), 3),
            "desvio_dia_90": round(st.pstdev(ult90), 3),
            "stock": stock_final,
            "fecha_stock": fecha_stock,
            "precio_venta_bs": round(sum(pv) / len(pv), 2),
            "recargo": recargo,
            "ventas_dia": [por_sku_dia[sku][d] for d in dias[-365:]],
            "proveedores": proveedores,
        }

    tco = [r for r in leer(TC) if r["id_serie"] == "TCO_BCB"]
    tco.sort(key=lambda r: r["fecha"])
    valores = [float(r["valor"]) for r in tco]
    tc = {
        "minimo": min(valores),
        "maximo": max(valores),
        "actual": valores[-1],
        "fecha_actual": tco[-1]["fecha"],
        "referencia": 11.0,
        "serie": [[r["fecha"], float(r["valor"])] for r in tco],
    }

    analisis = json.loads(ANALISIS.read_text(encoding="utf-8")) if ANALISIS.exists() else None
    tc["desvio_diario"] = analisis["volatilidad"]["desvio_diario"] if analisis else 0.0166
    return {
        "analisis": analisis,
        "meses": meses,
        "mes_parcial": mes_parcial,
        "ultima_fecha_ventas": ultima_fecha,
        "meses_prueba": MESES_PRUEBA,
        "productos": productos,
        "tc": tc,
    }


def main():
    datos = preparar()
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    if plantilla.count("__DATA__") != 1:
        raise SystemExit("La plantilla debe tener una única marca __DATA__")
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    logo = "data:image/jpeg;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    SALIDA.write_text(plantilla.replace("__LOGO__", logo).replace("__DATA__", texto), encoding="utf-8")
    print(f"{SALIDA.relative_to(BASE)}: {len(datos['productos'])} repuestos, {SALIDA.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
