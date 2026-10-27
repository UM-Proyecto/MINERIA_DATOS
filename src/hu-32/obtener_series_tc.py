"""HU-32: series históricas del tipo de cambio (Bs por USD) para evaluar su relación con los costos de compra.

Uso: python src/hu-32/obtener_series_tc.py [--semilla N] [--fecha-actualizacion AAAA-MM-DD]
Solo usa la librería estándar de Python (3.8 o superior). Funciona desde cualquier carpeta o desde la raíz del repositorio.

Criterio 1: fuentes_tipo_cambio.csv      -> fuente, moneda, unidad, período y tipo de cotización de cada serie
Criterio 2: tc_series_diaria.csv         -> fecha y valor tal como los publicó la fuente
            tc_fechas_faltantes.csv      -> fechas que faltan en cada serie (nunca se rellenan)
Criterio 3: tc_referencia_vs_utilizado.csv -> tipo de cambio de referencia (BCB) frente al efectivamente utilizado por la empresa
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
DIR_RAW = RAIZ / "data" / "raw" / "hu-32"
DIR_PROCESSED = RAIZ / "data" / "processed" / "hu-32"

MESES = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], 1)}
FECHA_EXTRACCION = date(2026, 10, 25)          # día en que se leyeron las fuentes
FIN_VIGENCIA_PUBLICADA = date(2026, 10, 26)    # el BCB publicó por adelantado la vigencia hasta esta fecha
URL_BCB = "https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php"
DATO_FICTICIO = "Dato ficticio generado por el equipo (pendiente del comprobante real de MULTIPARTES)"


def leer(nombre, carpeta="insumos_publicos"):
    p = DIR_RAW / carpeta / nombre
    if not p.is_file():
        p = AQUI / carpeta / nombre
    if not p.is_file() and carpeta == "insumos_equipo":
        p = RAIZ / "data" / "processed" / "hu-30-31" / "sintetico" / nombre
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def escribir(nombre, columnas, filas):
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(DIR_PROCESSED / nombre, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, lineterminator="\r\n")
        w.writeheader()
        w.writerows(filas)


def fecha_desde_texto(txt):
    """'sábado 27 de junio de 2026' -> date(2026, 6, 27)"""
    _, dia, _, mes, _, anio = txt.split()
    return date(int(anio), MESES[mes], int(dia))


def rangos_faltantes(esperadas, observadas):
    """Agrupa en rangos consecutivos las fechas esperadas que no tienen observación."""
    falt = sorted(d for d in esperadas if d not in observadas)
    rangos, ini, prev = [], None, None
    for d in falt:
        if ini is None:
            ini = prev = d
        elif d == prev + timedelta(days=1):
            prev = d
        else:
            rangos.append((ini, prev)); ini = prev = d
    if ini is not None:
        rangos.append((ini, prev))
    return rangos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semilla", type=int, default=20261019)
    ap.add_argument("--fecha-actualizacion", default=FECHA_EXTRACCION.isoformat())
    ap.add_argument("--spread-min", type=float, default=0.5, help="sobreprecio mínimo (%) del dato ficticio utilizado")
    ap.add_argument("--spread-max", type=float, default=3.0, help="sobreprecio máximo (%) del dato ficticio utilizado")
    a = ap.parse_args()
    actualizacion = a.fecha_actualizacion

    # ---------- 1. serie diaria ----------
    filas, tco = [], {}
    for r in leer("bcb_tco_diario_captura_2026-10-25.csv"):
        d = fecha_desde_texto(r["fecha_texto_original"])
        v = float(r["valor_texto_original"].replace(",", "."))
        assert d not in tco, f"fecha repetida {d}"
        tco[d] = v
        nota = []
        if d.weekday() >= 5 or d.weekday() == 0:
            nota.append("sábado, domingo o lunes: rige la cotización publicada el viernes")
        if d > FECHA_EXTRACCION:
            nota.append("vigencia publicada por adelantado; aún no ocurre")
        filas.append({"id_serie": "TCO_BCB", "fecha": d.isoformat(), "valor": f"{v:.2f}", "unidad": "Bs por 1 USD",
                      "tipo_cotizacion": "oficial flexible (TCO): mediana ponderada de compras de dólares de los bancos",
                      "tipo_dato": "DOCUMENTADO", "nota": "; ".join(nota), "fuente": "Banco Central de Bolivia (BCB)",
                      "url": URL_BCB, "fecha_actualizacion": actualizacion})
    puntos = {}
    for r in leer("puntos_documentados.csv"):
        d = date.fromisoformat(r["fecha"])
        puntos.setdefault(r["id_serie"], {})[d] = float(r["valor"])
        filas.append({"id_serie": r["id_serie"], "fecha": r["fecha"], "valor": f"{float(r['valor']):.2f}", "unidad": "Bs por 1 USD",
                      "tipo_cotizacion": r["tipo_cotizacion"], "tipo_dato": "DOCUMENTADO", "nota": r["nota"],
                      "fuente": r["fuente"], "url": r["url"], "fecha_actualizacion": actualizacion})
    escribir("tc_series_diaria.csv", ["id_serie", "fecha", "valor", "unidad", "tipo_cotizacion", "tipo_dato", "nota", "fuente", "url", "fecha_actualizacion"], filas)

    # ---------- 2. fuentes (criterio 1) ----------
    ini_tco, fin_tco = min(tco), max(tco)
    series = [
        ("TCO_BCB", "Tipo de cambio oficial (TCO) del BCB", "Banco Central de Bolivia (BCB)", URL_BCB, "diaria (rige todos los días; el viernes cubre sábado a lunes)",
         ini_tco, fin_tco, (ini_tco, fin_tco), "oficial flexible (TCO): mediana ponderada por monto de las compras de dólares de los bancos con sus clientes", "único",
         "DOCUMENTADO", "Es el tipo de cambio de referencia vigente desde el fin del régimen fijo. No es lo que paga una empresa al comprar dólares."),
        ("OFICIAL_FIJO_BCB_COMPRA", "Tipo de cambio oficial fijo del BCB (compra)", "Banco Central de Bolivia (BCB), citado por El Deber", "https://eldeber.com.bo/economia/bcb-publica-valor-referencial-dolar-bs-7-85-compra-bs-9-32-venta_1764627291", "sin cambios hasta el retiro del régimen fijo",
         date(2025, 12, 1), date(2026, 6, 26), (date(2025, 12, 1), date(2026, 6, 26)), "oficial fijo", "compra", "DOCUMENTADO",
         "El BCB lo mantuvo en 6,86 hasta el 26/06/2026, fecha en que abandonó el régimen fijo. Solo se verificó el 01/12/2025; los demás días no se rellenan."),
        ("OFICIAL_FIJO_BCB_VENTA", "Tipo de cambio oficial fijo del BCB (venta)", "Banco Central de Bolivia (BCB), citado por El Deber", "https://eldeber.com.bo/economia/bcb-publica-valor-referencial-dolar-bs-7-85-compra-bs-9-32-venta_1764627291", "sin cambios hasta el retiro del régimen fijo",
         date(2025, 12, 1), date(2026, 6, 26), (date(2025, 12, 1), date(2026, 6, 26)), "oficial fijo", "venta", "DOCUMENTADO",
         "Igual que la serie de compra: 6,96 el 01/12/2025."),
        ("VRD_BCB_COMPRA", "Valor referencial del dólar del BCB (compra)", "Banco Central de Bolivia (BCB), citado por El Deber", "https://www.bcb.gob.bo/?q=content/valor-referencial-de-compra-del-d%C3%B3lar-estadounidense-3", "diaria",
         date(2025, 12, 1), date(2026, 6, 26), (date(2025, 12, 1), date(2026, 6, 26)), "valor referencial: promedio ponderado de operaciones de bancos con clientes", "compra", "DOCUMENTADO",
         "El BCB tiene la serie histórica completa (01/12/2025 a 26/06/2026), pero la página la carga con JavaScript y no se pudo leer automáticamente. Pendiente de descarga manual."),
        ("VRD_BCB_VENTA", "Valor referencial del dólar del BCB (venta)", "Banco Central de Bolivia (BCB), citado por El Deber", "https://www.bcb.gob.bo/?q=content/valor-referencial-de-venta-del-d%C3%B3lar-estadounidense-0", "diaria",
         date(2025, 12, 1), date(2026, 6, 26), (date(2025, 12, 1), date(2026, 6, 26)), "valor referencial de venta: máximo que los bancos pueden cobrar en operaciones con el exterior", "venta", "DOCUMENTADO",
         "Es el más cercano a lo que paga una empresa que gira dólares al exterior. Pendiente de descarga manual, igual que la de compra."),
        ("PARALELO_P2P_VENTA", "Dólar paralelo (promedio de venta en plataformas P2P)", "dolarbolivia.net (agregador, fuente secundaria)", "https://dolarbolivia.net/", "diaria",
         date(2026, 10, 23), date(2026, 10, 23), (ini_tco, FECHA_EXTRACCION), "mercado paralelo: promedio de 8 plataformas P2P", "venta", "DOCUMENTADO",
         "Solo se obtuvo el dato del 23/10/2026. No hay historial verificable; si se necesita, hay que pedirlo a una fuente que lo publique."),
        ("TC_UTILIZADO_EMPRESA", "Tipo de cambio efectivamente utilizado por la empresa", "Comprobantes de MULTIPARTES (banco o casa de cambio, factura de la operación)", "", "por operación (cada pago a un proveedor)",
         None, None, None, "tipo de cambio de la operación real de compra de dólares o giro al exterior", "venta (lo que paga la empresa)", "SINTETICO",
         "PENDIENTE del dato real. Mientras tanto, tc_referencia_vs_utilizado.csv trae valores ficticios marcados como SINTETICO."),
    ]
    obs = {}
    for r in filas:
        obs.setdefault(r["id_serie"], set()).add(date.fromisoformat(r["fecha"]))
    fuentes = []
    for sid, nom, fte, url, frec, p_ini, p_fin, _, tipo, lado, tdato, nota in series:
        n = len(obs.get(sid, ()))
        fuentes.append({"id_serie": sid, "nombre": nom, "fuente": fte, "url": url, "moneda_cotizada": "USD (dólar estadounidense)",
                        "moneda_base": "BOB (boliviano)", "unidad": "Bs por 1 USD", "periodo_inicio": p_ini.isoformat() if p_ini else "",
                        "periodo_fin": p_fin.isoformat() if p_fin else "", "frecuencia": frec, "tipo_cotizacion": tipo, "lado": lado,
                        "observaciones_obtenidas": n, "tipo_dato": tdato, "fecha_extraccion": FECHA_EXTRACCION.isoformat(),
                        "fecha_actualizacion": actualizacion, "nota": nota})
    escribir("fuentes_tipo_cambio.csv", list(fuentes[0].keys()), fuentes)

    # ---------- 3. fechas faltantes (criterio 2) ----------
    falt = []
    for sid, *_r in series:
        ventana = next(s[7] for s in series if s[0] == sid)
        if ventana is None:
            continue
        esperadas = [ventana[0] + timedelta(days=i) for i in range((ventana[1] - ventana[0]).days + 1)]
        rangos = rangos_faltantes(esperadas, obs.get(sid, set()))
        motivo = next(s[11] for s in series if s[0] == sid)
        if not rangos:
            falt.append({"id_serie": sid, "fecha_inicio_faltante": "", "fecha_fin_faltante": "", "dias_faltantes": 0,
                         "periodo_esperado": f"{ventana[0]} a {ventana[1]}", "estado": "SIN FALTANTES", "motivo": "Todas las fechas del período tienen valor publicado."})
        for ini, fin in rangos:
            falt.append({"id_serie": sid, "fecha_inicio_faltante": ini.isoformat(), "fecha_fin_faltante": fin.isoformat(), "dias_faltantes": (fin - ini).days + 1,
                         "periodo_esperado": f"{ventana[0]} a {ventana[1]}", "estado": "FALTANTE (NO SE RELLENA)",
                         "motivo": "No se obtuvo el dato de esta fecha; se deja vacío y no se estima."})
    escribir("tc_fechas_faltantes.csv", ["id_serie", "fecha_inicio_faltante", "fecha_fin_faltante", "dias_faltantes", "periodo_esperado", "estado", "motivo"], falt)

    # ---------- 4. referencia vs utilizado (criterio 3) ----------
    rnd = random.Random(a.semilla)
    vistos, comp = set(), []
    for r in leer("movimientos_inventario_sintetico.csv", "insumos_equipo"):
        if r["tipo_movimiento"] != "ENTRADA" or not r["documento"].startswith("OC-") or r["documento"] in vistos:
            continue
        vistos.add(r["documento"])
        d = date.fromisoformat(r["fecha"])
        usd = round(int(r["cantidad"]) * float(r["precio_unitario_usd"]), 2)
        ref = tco.get(d)
        fila = {"fecha_operacion": r["fecha"], "documento": r["documento"], "codigo_unico": r["codigo_unico"], "proveedor": r["proveedor_cliente"],
                "monto_usd": f"{usd:.2f}", "tc_referencia_bcb": "", "tc_utilizado_empresa": "", "diferencia_bs_por_usd": "", "diferencia_pct": "",
                "monto_bs_con_referencia": "", "monto_bs_con_utilizado": "", "diferencia_monto_bs": "", "tipo_dato_utilizado": "", "estado": "", "fuente": ""}
        if ref is None:
            fila.update(estado="SIN REFERENCIA: fecha anterior al inicio de la serie TCO", tipo_dato_utilizado="PENDIENTE",
                        fuente="Sin valor de referencia ni comprobante: no se estima")
        else:
            spread = rnd.uniform(a.spread_min, a.spread_max) / 100
            usado = round(ref * (1 + spread), 2)
            fila.update(tc_referencia_bcb=f"{ref:.2f}", tc_utilizado_empresa=f"{usado:.2f}", diferencia_bs_por_usd=f"{usado - ref:.2f}",
                        diferencia_pct=f"{(usado / ref - 1) * 100:.2f}", monto_bs_con_referencia=f"{usd * ref:.2f}", monto_bs_con_utilizado=f"{usd * usado:.2f}",
                        diferencia_monto_bs=f"{usd * (usado - ref):.2f}", tipo_dato_utilizado="SINTETICO", estado="CON REFERENCIA", fuente=DATO_FICTICIO)
        comp.append(fila)
    comp.sort(key=lambda x: (x["fecha_operacion"], x["documento"]))
    escribir("tc_referencia_vs_utilizado.csv", list(comp[0].keys()), comp)

    # ---------- resumen ----------
    vals = sorted(tco.items(), key=lambda kv: kv[1])
    print(f"TCO: {len(tco)} fechas, {ini_tco} a {fin_tco}; mínimo {vals[0][1]:.2f} ({vals[0][0]}), máximo {vals[-1][1]:.2f} ({vals[-1][0]})")
    print(f"Fechas faltantes en TCO: {sum(f['dias_faltantes'] for f in falt if f['id_serie'] == 'TCO_BCB')}")
    con = [c for c in comp if c["estado"] == "CON REFERENCIA"]
    print(f"Operaciones de compra: {len(comp)} (con referencia: {len(con)}, sin referencia: {len(comp) - len(con)})")
    if con:
        print(f"Diferencia total (Bs) utilizado - referencia en {len(con)} operaciones: {sum(float(c['diferencia_monto_bs']) for c in con):.2f}")
    print("Archivos: fuentes_tipo_cambio.csv, tc_series_diaria.csv, tc_fechas_faltantes.csv, tc_referencia_vs_utilizado.csv")


if __name__ == "__main__":
    main()
