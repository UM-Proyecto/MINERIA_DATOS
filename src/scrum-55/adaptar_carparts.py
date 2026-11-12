"""SCRUM-55: adapta el conjunto público «carparts» a MULTIPARTES.

Qué es real y qué es simulado:
- REAL: las ventas mensuales de 2.674 repuestos de auto (Hyndman, Koehler, Ord y Snyder, 2008,
  «Forecasting with Exponential Smoothing», Springer; licencia GPL >= 2). Solo se les cambia la fecha.
- REAL: el tipo de cambio oficial del BCB (data/processed/scrum-54/tco_bcb_diario.csv) y la
  referencia de flete China del INE que trae HU-31.
- SINTÉTICO: proveedores, origen, plazos, costos, márgenes, la regla de reposición y el stock.
  Todos los parámetros están en las constantes de abajo, a la vista.

Solo usa la biblioteca estándar (Python 3.8+). Con la misma semilla produce siempre los mismos
archivos, byte por byte. Uso:

    python src/scrum-55/adaptar_carparts.py [--semilla N] [--salida CARPETA]
"""
import argparse
import calendar
import csv
import hashlib
import io
import json
import math
import random
import statistics
import zipfile
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ZIP_CARPARTS = RAIZ / "data" / "raw" / "scrum-55" / "expsmooth_data.zip"
TCO_CSV = RAIZ / "data" / "processed" / "scrum-54" / "tco_bcb_diario.csv"
HU31_FLETES = RAIZ / "data" / "processed" / "hu-30-31" / "hu31_costos_importacion.csv"
HU31_GASTOS = RAIZ / "data" / "processed" / "hu-30-31" / "sintetico" / "hu31_costos_complementarios_sintetico.csv"
SALIDA = RAIZ / "data" / "processed" / "scrum-55"

# Huella del zip tal como lo publica el autor. Si el archivo cambia, el script se detiene en vez de
# producir resultados distintos en silencio.
SHA256_ZIP = "7ea2aabdfde73bb48eeec68c1eba3724d12d9b4691db3e353d3f310bb0fb3770"
FECHA_DESCARGA = "2026-11-10"
FECHA_REVERIFICACION = "2026-11-12"  # se volvió a bajar de la URL y dio el mismo sha256

MARCA = "SINTÉTICO / ADAPTADO"
SEMILLA = 20261112

# Re-fechado: los 51 meses originales (ene-1998 a mar-2002) pasan, en el mismo orden, a
# ago-2022 ... oct-2026. Octubre de 2026 es el último mes completo antes del corte.
MES_INICIO = (2022, 8)
N_MESES = 51
FECHA_CORTE = date(2026, 11, 10)

# Tipo de cambio: desde el 27/06/2026 rige el TCO diario del BCB; antes, el oficial fijo de venta.
INICIO_TCO = date(2026, 6, 27)
TC_FIJO = Decimal("6.96")
TC_FUENTE_FIJO = "BCB, tipo de cambio oficial fijo de venta 6,96 Bs/USD (vigente antes del 27/06/2026)"

# Syntetos-Boylan (2005): cortes de ADI y CV².
ADI_CORTE = 1.32
CV2_CORTE = 0.49
TIPOS = ["suave", "errática", "intermitente", "irregular", "sin clasificar"]

# ABC por volumen: A hasta el 80 % acumulado de unidades, B hasta el 95 %, C el resto.
CORTE_A = 0.80
CORTE_B = 0.95

# Selección de los 30: series completas (sin meses vacíos) con al menos 6 meses con venta; 6 por cada
# combinación de tipo de demanda y clase ABC que tenga al menos 6 series así, repartidas a intervalos
# iguales en el orden por volumen. Con los datos de carparts quedan exactamente 5 combinaciones
# (intermitente A, B y C; irregular A y B): no hay series suaves ni erráticas completas, y las
# irregulares C completas son 4 y ninguna llega a 6 meses con venta.
MIN_MESES_CON_VENTA = 6
POR_ESTRATO = 6
TOTAL_ELEGIDOS = 30

# ---------------------------------------------------------------------------------------------
# Capa SINTÉTICA. Todo lo que sigue es un supuesto del equipo, no un dato de MULTIPARTES.
# ---------------------------------------------------------------------------------------------
# (id, nombre, origen, incoterm, plazo normal en días, desvío del plazo en días, % a tiempo)
PROVEEDORES = [
    ("PROV-BR-01", "Proveedor Brasil Alfa (ficticio)", "Brasil", "FOB", 30, 4, 90),
    ("PROV-BR-02", "Proveedor Brasil Beta (ficticio)", "Brasil", "EXW", 32, 6, 85),
    ("PROV-BR-03", "Proveedor Brasil Gama (ficticio)", "Brasil", "CIF", 35, 5, 88),
    ("PROV-CN-01", "Proveedor China Alfa (ficticio)", "China", "FOB", 55, 10, 75),
    ("PROV-CN-02", "Proveedor China Beta (ficticio)", "China", "CIF", 60, 8, 80),
    ("PROV-CN-03", "Proveedor China Gama (ficticio)", "China", "FOB", 50, 12, 70),
    ("PROV-CN-04", "Proveedor China Delta (ficticio)", "China", "EXW", 58, 9, 72),
    ("PROV-US-01", "Proveedor EE. UU. Alfa (ficticio)", "EE. UU.", "FOB", 40, 6, 88),
    ("PROV-US-02", "Proveedor EE. UU. Beta (ficticio)", "EE. UU.", "CIF", 45, 5, 90),
    ("PROV-US-03", "Proveedor EE. UU. Gama (ficticio)", "EE. UU.", "EXW", 42, 7, 82),
]

# Flete y seguro hasta Bolivia, en % del valor FOB. China sale de HU-31 (INE, medio CARRETERA:
# la mercadería que llega por puerto chileno y entra a Bolivia en camión). Brasil y EE. UU. no
# tienen referencia en el repositorio: son supuestos.
FLETE_CHINA_CONCEPTO = "flete y seguro implícito (CIF-FOB), origen China, medio CARRETERA"
FLETE_SUPUESTO = {"Brasil": Decimal("6.0"), "EE. UU.": Decimal("10.0")}
# EXW: se suman 3 puntos por el traslado hasta el puerto o la frontera. CIF: el flete ya viene en
# el precio del proveedor, por eso no se suma.
AJUSTE_INCOTERM = {"EXW": Decimal("3.0"), "FOB": Decimal("0"), "CIF": None}
# Gastos de importación (seguro, nacionalización y comisión, % del CIF): HU-31, archivo SINTÉTICO.
GASTOS_CONCEPTOS = ["seguro de carga", "nacionalizacion y agente aduanero", "comision de gestion de importacion"]

# Precio del proveedor en USD por unidad, según la clase ABC (rango uniforme).
COSTO_USD_POR_CLASE = {"A": (Decimal("5"), Decimal("35")), "B": (Decimal("15"), Decimal("70")),
                       "C": (Decimal("30"), Decimal("150"))}
# Margen sobre el costo puesto en Santa Cruz.
MARGEN_POR_CLASE = {"A": Decimal("35"), "B": Decimal("45"), "C": Decimal("60")}
# Regla (s, S) con revisión mensual: z del stock de seguridad y meses de cobertura sobre s.
Z_POR_CLASE = {"A": 1.65, "B": 1.28, "C": 0.84}
COBERTURA_MESES = {"A": 1, "B": 2, "C": 3}
REVISION_DIAS = 30


def dinero(valor, decimales="0.01"):
    return Decimal(valor).quantize(Decimal(decimales), rounding=ROUND_HALF_UP)


def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def mes_refechado(indice):
    anio, mes = MES_INICIO
    total = anio * 12 + (mes - 1) + indice
    return total // 12, total % 12 + 1


def leer_carparts(ruta=ZIP_CARPARTS):
    huella = sha256(ruta)
    if huella != SHA256_ZIP:
        raise SystemExit("El zip de carparts no coincide con el publicado: %s" % huella)
    with zipfile.ZipFile(ruta) as archivo:
        texto = archivo.read("carparts.csv").decode("ascii")
    filas = list(csv.reader(io.StringIO(texto)))
    encabezado = filas[0]
    if encabezado[0] != "Part" or len(encabezado) != N_MESES + 1:
        raise SystemExit("Encabezado inesperado en carparts.csv")
    series = []
    for fila in filas[1:]:
        valores = [None if celda.strip() == "" else int(float(celda)) for celda in fila[1:]]
        series.append((fila[0], valores))
    return encabezado[1:], series, hashlib.sha256(texto.encode("ascii")).hexdigest()


def clasificar_demanda(valores):
    """Devuelve (tipo, adi, cv2). ADI = meses observados / meses con venta; CV² = (desvío / media)²
    de los tamaños de venta distintos de cero (desvío poblacional). Los meses vacíos no cuentan."""
    observados = [v for v in valores if v is not None]
    con_venta = [v for v in observados if v > 0]
    if len(con_venta) < 2:
        return "sin clasificar", None, None
    adi = len(observados) / len(con_venta)
    media = statistics.mean(con_venta)
    cv2 = (statistics.pstdev(con_venta) / media) ** 2
    if adi <= ADI_CORTE:
        tipo = "suave" if cv2 <= CV2_CORTE else "errática"
    else:
        tipo = "intermitente" if cv2 <= CV2_CORTE else "irregular"
    return tipo, adi, cv2


def clasificar_todo(series):
    filas = []
    for codigo, valores in series:
        observados = [v for v in valores if v is not None]
        tipo, adi, cv2 = clasificar_demanda(valores)
        filas.append({"codigo_carparts": codigo, "meses_observados": len(observados),
                      "meses_faltantes": N_MESES - len(observados),
                      "meses_con_venta": sum(1 for v in observados if v > 0),
                      "unidades_totales": sum(observados), "adi": adi, "cv2": cv2,
                      "tipo_demanda": tipo, "completa": len(observados) == N_MESES})
    total = sum(f["unidades_totales"] for f in filas)
    acumulado = 0
    for f in sorted(filas, key=lambda f: (-f["unidades_totales"], f["codigo_carparts"])):
        previo = acumulado / total
        f["clase_abc"] = "A" if previo < CORTE_A else "B" if previo < CORTE_B else "C"
        acumulado += f["unidades_totales"]
    for f in filas:
        f["elegible"] = (f["completa"] and f["meses_con_venta"] >= MIN_MESES_CON_VENTA
                         and f["tipo_demanda"] != "sin clasificar")
    return filas


def seleccionar(filas):
    """POR_ESTRATO por cada combinación tipo × ABC con suficientes elegibles, a intervalos iguales en
    el orden por volumen (de la más vendida a la menos vendida). Las combinaciones con menos elegibles
    se omiten y quedan a la vista en resumen_clasificacion.csv (columna series_elegibles)."""
    elegidos = []
    for tipo in TIPOS:
        for clase in "ABC":
            grupo = sorted((f for f in filas if f["elegible"] and f["tipo_demanda"] == tipo
                            and f["clase_abc"] == clase),
                           key=lambda f: (-f["unidades_totales"], f["codigo_carparts"]))
            if len(grupo) < POR_ESTRATO:
                continue
            n = len(grupo)
            posiciones = [round(i * (n - 1) / (POR_ESTRATO - 1)) for i in range(POR_ESTRATO)]
            elegidos.extend(grupo[p] for p in posiciones)
    if len(elegidos) != TOTAL_ELEGIDOS:
        raise SystemExit("La regla eligió %d repuestos, se esperaban %d" % (len(elegidos), TOTAL_ELEGIDOS))
    return elegidos


def leer_tco(ruta=TCO_CSV):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    tco = {date.fromisoformat(f["fecha"]): Decimal(f["tco_bs_por_usd"]) for f in filas}
    return tco, filas[0]["fuente"]


def tipo_cambio(fecha, tco, fuente_tco):
    if fecha < INICIO_TCO:
        return TC_FIJO, "OFICIAL_FIJO_BCB", TC_FUENTE_FIJO
    if fecha not in tco:
        raise SystemExit("Falta el TCO del %s en %s" % (fecha, TCO_CSV.name))
    return tco[fecha], "TCO_BCB_DIARIO", fuente_tco + "; data/processed/scrum-54/tco_bcb_diario.csv"


def leer_referencias_hu31():
    with open(HU31_FLETES, encoding="utf-8", newline="") as archivo:
        fletes = {f["concepto"]: f for f in csv.DictReader(archivo)}
    china = fletes[FLETE_CHINA_CONCEPTO]
    pct_china = Decimal(china["unidad"].split("(")[1].split("%")[0])
    with open(HU31_GASTOS, encoding="utf-8-sig", newline="") as archivo:
        gastos = {f["concepto"]: f for f in csv.DictReader(archivo)}
    pct_gastos = sum(Decimal(gastos[c]["valor"]) for c in GASTOS_CONCEPTOS)
    flete = {"China": (pct_china, "REAL (INE, vía HU-31): %s, %s, %s" % (china["concepto"], china["unidad"],
                                                                        china["fecha_dato"]))}
    for origen, pct in FLETE_SUPUESTO.items():
        flete[origen] = (pct, "SUPUESTO del equipo: sin referencia de flete para %s en el repositorio" % origen)
    fuente_gastos = ("SINTÉTICO (HU-31, hu31_costos_complementarios_sintetico.csv): "
                     + " + ".join("%s %s %%" % (c, gastos[c]["valor"]) for c in GASTOS_CONCEPTOS))
    return flete, pct_gastos, fuente_gastos


def flete_pct(origen, incoterm, flete):
    ajuste = AJUSTE_INCOTERM[incoterm]
    return Decimal("0") if ajuste is None else flete[origen][0] + ajuste


def precio_proveedor(rng, clase, origen, incoterm, flete):
    minimo, maximo = COSTO_USD_POR_CLASE[clase]
    base = minimo + (maximo - minimo) * Decimal(str(round(rng.random(), 6)))
    if incoterm == "CIF":  # el proveedor cobra el flete dentro del precio
        base = base * (1 + flete[origen][0] / 100)
    return dinero(base)


def plazo_real(rng, plazo, desvio, pct_a_tiempo):
    if rng.random() * 100 < pct_a_tiempo:
        return plazo - rng.randint(0, 3), True
    return plazo + 1 + int(abs(rng.gauss(0, desvio))), False


def demanda_diaria(valores):
    """Reparte las unidades de cada mes en días a intervalos iguales. Noviembre de 2026 no tiene dato:
    se toma sin ventas del 1 al 10."""
    demanda = {}
    for i, unidades in enumerate(valores):
        anio, mes = mes_refechado(i)
        dias = calendar.monthrange(anio, mes)[1]
        for j in range(unidades):
            dia = date(anio, mes, 1) + timedelta(days=int((j + 0.5) * dias / unidades))
            demanda[dia] = demanda.get(dia, 0) + 1
    return demanda


def simular(repuesto, valores, proveedor, rng):
    """Reposición (s, S) con revisión mensual en un día fijo; ventas perdidas si no hay stock."""
    clase = repuesto["clase_abc"]
    media = statistics.mean(valores)
    desvio = statistics.pstdev(valores)
    proteccion = (proveedor[4] + REVISION_DIAS) / 30
    s = math.ceil(media * proteccion + Z_POR_CLASE[clase] * desvio * math.sqrt(proteccion))
    S = max(s + 1, s + math.ceil(media * COBERTURA_MESES[clase]))
    dia_revision = rng.randint(1, 28)
    demanda = demanda_diaria(valores)
    stock, faltantes, pendientes, ordenes = S, 0, [], []
    dia = date(*MES_INICIO, 1)
    while dia <= FECHA_CORTE:
        stock += sum(o["cantidad"] for o in pendientes if o["fecha_llegada"] == dia)
        pendientes = [o for o in pendientes if o["fecha_llegada"] != dia]
        pedido = demanda.get(dia, 0)
        atendido = min(stock, pedido)
        faltantes += pedido - atendido
        stock -= atendido
        if dia.day == dia_revision:
            posicion = stock + sum(o["cantidad"] for o in pendientes)
            if posicion <= s:
                dias, a_tiempo = plazo_real(rng, proveedor[4], proveedor[5], proveedor[6])
                orden = {"fecha_orden": dia, "fecha_llegada": dia + timedelta(days=dias),
                         "plazo_real_dias": dias, "a_tiempo": a_tiempo, "cantidad": S - posicion}
                pendientes.append(orden)
                ordenes.append(orden)
        dia += timedelta(days=1)
    return {"s": s, "S": S, "dia_revision": dia_revision, "stock_inicial": S, "stock_final": stock,
            "en_transito": sum(o["cantidad"] for o in pendientes), "faltantes": faltantes, "ordenes": ordenes}


def escribir_csv(ruta, filas):
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def num(valor, decimales=4):
    return "" if valor is None else ("%." + str(decimales) + "f") % valor


def ejecutar(semilla=SEMILLA, salida=SALIDA):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    meses_originales, series, sha_csv = leer_carparts()
    valores_por_codigo = dict(series)
    clasificacion = clasificar_todo(series)
    elegidos = seleccionar(clasificacion)
    tco, fuente_tco = leer_tco()
    flete, pct_gastos, fuente_gastos = leer_referencias_hu31()
    tc_ref, tc_ref_tipo, tc_ref_fuente = tipo_cambio(FECHA_CORTE, tco, fuente_tco)
    origen_real = "REAL: carparts (Hyndman et al., 2008), mes re-fechado"

    ids = {f["codigo_carparts"]: "REP-%04d" % (i + 1) for i, f in enumerate(elegidos)}
    repuestos, ventas, compras, asignados = [], [], [], {}
    for f in elegidos:
        rid, valores = ids[f["codigo_carparts"]], valores_por_codigo[f["codigo_carparts"]]
        rng = random.Random("%s-%s" % (semilla, f["codigo_carparts"]))
        proveedor = PROVEEDORES[rng.randrange(len(PROVEEDORES))]
        prov_id, prov_nombre, origen, incoterm = proveedor[:4]
        asignados[prov_id] = asignados.get(prov_id, 0) + 1
        costo = precio_proveedor(rng, f["clase_abc"], origen, incoterm, flete)
        fpct = flete_pct(origen, incoterm, flete)
        factor = (1 + fpct / 100) * (1 + pct_gastos / 100)
        costo_puesto = dinero(costo * factor)
        margen = MARGEN_POR_CLASE[f["clase_abc"]]
        precio_bs = dinero(costo_puesto * tc_ref * (1 + margen / 100), "1")
        sim = simular(f, valores, proveedor, rng)
        for i, unidades in enumerate(valores):
            anio, mes = mes_refechado(i)
            ventas.append({"repuesto_id": rid, "codigo_carparts": f["codigo_carparts"],
                           "mes": "%04d-%02d" % (anio, mes), "mes_original": meses_originales[i],
                           "unidades": unidades, "origen_dato": origen_real, "marca": MARCA})
        for o in sim["ordenes"]:
            tc, tc_tipo, tc_fuente = tipo_cambio(o["fecha_orden"], tco, fuente_tco)
            total_usd = dinero(costo * o["cantidad"])
            puesto_usd = dinero(costo * o["cantidad"] * factor)
            compras.append({"orden_id": "", "repuesto_id": rid, "proveedor_id": prov_id, "origen": origen,
                            "incoterm": incoterm, "fecha_orden": o["fecha_orden"].isoformat(),
                            "fecha_llegada": o["fecha_llegada"].isoformat(),
                            "plazo_real_dias": o["plazo_real_dias"], "a_tiempo": "SI" if o["a_tiempo"] else "NO",
                            "cantidad": o["cantidad"], "costo_unitario_usd": costo, "costo_total_usd": total_usd,
                            "costo_puesto_total_usd": puesto_usd, "tc_bs_por_usd": tc, "tc_tipo": tc_tipo,
                            "tc_fuente": tc_fuente, "costo_total_bs": dinero(total_usd * tc),
                            "costo_puesto_total_bs": dinero(puesto_usd * tc),
                            "estado": "RECIBIDA" if o["fecha_llegada"] <= FECHA_CORTE else "EN_TRANSITO",
                            "origen_dato": "SINTÉTICO: orden generada por la regla (s, S) sobre la demanda real",
                            "marca": MARCA})
        repuestos.append({
            "repuesto_id": rid, "codigo_carparts": f["codigo_carparts"], "tipo_demanda": f["tipo_demanda"],
            "clase_abc": f["clase_abc"], "adi": num(f["adi"]), "cv2": num(f["cv2"]),
            "meses_con_dato": f["meses_observados"], "meses_con_venta": f["meses_con_venta"],
            "unidades_totales": f["unidades_totales"], "promedio_mensual": num(statistics.mean(valores), 2),
            "proveedor_id": prov_id, "proveedor": prov_nombre, "origen": origen, "incoterm": incoterm,
            "plazo_normal_dias": proveedor[4], "desvio_plazo_dias": proveedor[5],
            "pct_entregas_a_tiempo": proveedor[6], "costo_unitario_usd": costo, "flete_pct": fpct,
            "gastos_pct": pct_gastos, "costo_puesto_usd": costo_puesto, "tc_referencia_bs_por_usd": tc_ref,
            "tc_referencia_fecha": FECHA_CORTE.isoformat(), "tc_referencia_tipo": tc_ref_tipo,
            "costo_unitario_bs": dinero(costo * tc_ref), "costo_puesto_bs": dinero(costo_puesto * tc_ref),
            "margen_pct": margen, "precio_venta_bs": precio_bs, "precio_venta_usd": dinero(precio_bs / tc_ref),
            "punto_pedido_s": sim["s"], "nivel_maximo_S": sim["S"], "dia_revision": sim["dia_revision"],
            "stock_inicial_2022_08_01": sim["stock_inicial"], "stock_al_2026_11_10": sim["stock_final"],
            "en_transito_al_2026_11_10": sim["en_transito"],
            "valor_stock_usd": dinero(costo_puesto * sim["stock_final"]),
            "valor_stock_bs": dinero(costo_puesto * sim["stock_final"] * tc_ref),
            "ordenes_generadas": len(sim["ordenes"]), "unidades_no_atendidas_simuladas": sim["faltantes"],
            "origen_dato": "ventas, ADI, CV² y ABC: REAL (carparts); proveedor, costos, precio y stock: SINTÉTICO",
            "marca": MARCA})

    compras.sort(key=lambda c: (c["fecha_orden"], c["repuesto_id"]))
    for i, c in enumerate(compras, 1):
        c["orden_id"] = "OC-%05d" % i

    proveedores = [{"proveedor_id": p[0], "nombre": p[1], "origen": p[2], "incoterm": p[3],
                    "plazo_normal_dias": p[4], "desvio_plazo_dias": p[5], "pct_entregas_a_tiempo": p[6],
                    "flete_pct_fob_origen": flete[p[2]][0], "flete_pct_aplicado": flete_pct(p[2], p[3], flete),
                    "flete_fuente": flete[p[2]][1] + ("; CIF: el flete va dentro del precio" if p[3] == "CIF" else
                                                      "; EXW: +3 puntos por traslado (supuesto)" if p[3] == "EXW" else ""),
                    "gastos_pct_cif": pct_gastos, "gastos_fuente": fuente_gastos,
                    "repuestos_asignados": asignados.get(p[0], 0),
                    "origen_dato": "SINTÉTICO: proveedor ficticio", "marca": MARCA} for p in PROVEEDORES]

    elegido_por_codigo = {f["codigo_carparts"]: ids[f["codigo_carparts"]] for f in elegidos}
    detalle = [{"codigo_carparts": f["codigo_carparts"], "meses_con_dato": f["meses_observados"],
                "meses_faltantes": f["meses_faltantes"], "meses_con_venta": f["meses_con_venta"],
                "unidades_totales": f["unidades_totales"], "adi": num(f["adi"]), "cv2": num(f["cv2"]),
                "tipo_demanda": f["tipo_demanda"], "clase_abc": f["clase_abc"],
                "completa": "SI" if f["completa"] else "NO", "elegible": "SI" if f["elegible"] else "NO",
                "repuesto_id": elegido_por_codigo.get(f["codigo_carparts"], ""),
                "origen_dato": "REAL: carparts; clasificación calculada por el equipo", "marca": MARCA}
               for f in clasificacion]

    resumen = []
    for grupo, filas in (("universo_2674", clasificacion), ("elegidos_30", elegidos)):
        for tipo in TIPOS:
            for clase in "ABC":
                sub = [f for f in filas if f["tipo_demanda"] == tipo and f["clase_abc"] == clase]
                resumen.append({"grupo": grupo, "tipo_demanda": tipo, "clase_abc": clase, "series": len(sub),
                                "series_completas": sum(1 for f in sub if f["completa"]),
                                "series_elegibles": sum(1 for f in sub if f["elegible"]),
                                "unidades": sum(f["unidades_totales"] for f in sub),
                                "origen_dato": "REAL: carparts; clasificación calculada por el equipo",
                                "marca": MARCA})

    fuente = {
        "conjunto": "carparts",
        "cita": "Hyndman, R. J., Koehler, A. B., Ord, J. K. y Snyder, R. D. (2008). Forecasting with "
                "Exponential Smoothing: The State Space Approach. Springer.",
        "descripcion": "Monthly car part sales, covering 2,674 series from January 1998 to March 2002",
        "licencia": "GPL (>= 2)",
        "licencia_fuente": "archivo DESCRIPTION del paquete R expsmooth 2.3 (https://cran.r-project.org/package=expsmooth)",
        "url_descarga": "https://robjhyndman.com/expsmooth/expsmooth_data.zip",
        "url_pagina": "https://robjhyndman.com/expsmooth/",
        "fecha_descarga": FECHA_DESCARGA,
        "fecha_reverificacion": FECHA_REVERIFICACION,
        "archivo_local": "data/raw/scrum-55/expsmooth_data.zip",
        "bytes": ZIP_CARPARTS.stat().st_size,
        "sha256_zip": SHA256_ZIP,
        "sha256_carparts_csv": sha_csv,
        "series": len(series),
        "meses": N_MESES,
        "periodo_original": "%s a %s" % (meses_originales[0], meses_originales[-1]),
        "periodo_refechado": "%04d-%02d a %04d-%02d" % (mes_refechado(0) + mes_refechado(N_MESES - 1)),
        "supuesto_refechado": "Los 51 meses se trasladan en orden a ago-2022 ... oct-2026, el último mes completo "
                              "antes del corte del 10/11/2026. Las cantidades no se modifican.",
        "semilla": semilla,
        "marca": MARCA,
    }

    escribir_csv(salida / "repuestos.csv", repuestos)
    escribir_csv(salida / "ventas_mensuales.csv", ventas)
    escribir_csv(salida / "proveedores.csv", proveedores)
    escribir_csv(salida / "compras_historicas.csv", compras)
    escribir_csv(salida / "resumen_clasificacion.csv", resumen)
    escribir_csv(salida / "clasificacion_2674.csv", detalle)
    (salida / "fuente.json").write_text(json.dumps(fuente, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"repuestos": len(repuestos), "ventas": len(ventas), "compras": len(compras),
            "clasificadas": len(clasificacion)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    parser.add_argument("--salida", default=str(SALIDA))
    args = parser.parse_args()
    resultado = ejecutar(args.semilla, args.salida)
    print("Listo: %(clasificadas)d series clasificadas, %(repuestos)d repuestos, %(ventas)d filas de "
          "ventas, %(compras)d órdenes de compra." % resultado)
    print("Salida: %s" % args.salida)


if __name__ == "__main__":
    main()
