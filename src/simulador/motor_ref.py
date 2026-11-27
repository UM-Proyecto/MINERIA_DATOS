"""Referencia en Python del motor del simulador (src/simulador/motor.js).

Repite cada cálculo de motor.js en el mismo orden y con las mismas operaciones, para que la prueba
tests/test_simulador_motor.py compruebe que los dos motores dan lo mismo. La app usa solo motor.js;
este archivo existe para las pruebas. Si cambias una fórmula en uno, cámbiala igual en el otro.

Detalles que importan para la equivalencia bit a bit:
- mulberry32 con aritmética uint32 (máscara 0xFFFFFFFF), igual que Math.imul y >>> en JavaScript;
- la normal es la suma de 12 uniformes menos 6, y la exponencial sale de la serie de exp_serie;
- Python redondea «al par» con round(); aquí se usa floor(x + 0,5), como en JavaScript.
Solo biblioteca estándar.
"""
import math
import re

Z_CLASE = {"A": 1.65, "B": 1.28, "C": 0.84}
ALFA_SBA = 0.1
ALTERNATIVAS = ["A", "B", "C", "D"]
ORDEN_CLASE = {"A": 0, "B": 1, "C": 2}
ETIQUETAS = ["Pedir ya", "Vigilar", "Cubierto", "Sin datos"]
EPS = 1e-9
ATRASO_EXTRA_MIN = 5
ATRASO_EXTRA_RANGO = 15
TC_FIJO = 6.96
INICIO_TCO = "2026-06-27"
QUIEBRE_PASOS = 120
N_ANALISIS = 400
M32 = 0xFFFFFFFF


def num(x):
    return float(x)


# ------------------------------------------------------------------ utilidades numéricas

def _imul(a, b):
    return (a * b) & M32


def mulberry32(semilla):
    estado = [int(semilla) & M32]

    def r():
        a = (estado[0] + 0x6D2B79F5) & M32
        estado[0] = a
        t = _imul(a ^ (a >> 15), a | 1)
        t = ((t + _imul(t ^ (t >> 7), t | 61)) & M32) ^ t
        return ((t ^ (t >> 14)) & M32) / 4294967296

    return r


def normal_ih(r):
    s = 0.0
    for _ in range(12):
        s += r()
    return s - 6


def exp_serie(x):
    y = x / 16
    s = 1.0
    for k in range(20, 0, -1):
        s = 1 + s * y / k
    s = s * s
    s = s * s
    s = s * s
    s = s * s
    return s


def redondear(x, dec):
    f = 10 ** dec
    return math.floor(x * f + 0.5 + EPS) / f


def techo(x):
    return math.ceil(x - EPS)


def media(v):
    if not v:
        return 0
    s = 0
    for x in v:
        s += x
    return s / len(v)


def desvio(v):
    if not v:
        return 0
    m = media(v)
    s = 0
    for x in v:
        s += (x - m) * (x - m)
    return math.sqrt(s / len(v))


def volatilidad_diaria(serie):
    c = [num(serie[i][1]) / num(serie[i - 1][1]) - 1 for i in range(1, len(serie))]
    return desvio(c)


# ------------------------------------------------------------------ búsquedas

def buscar_repuesto(datos, rid):
    for r in datos["repuestos"]:
        if r["repuesto_id"] == rid:
            return r
    raise KeyError("Repuesto desconocido: " + rid)


def buscar_proveedor(datos, pid):
    for p in datos["proveedores"]:
        if p["proveedor_id"] == pid:
            return p
    raise KeyError("Proveedor desconocido: " + pid)


def valores(ventas):
    return [num(v[1]) if isinstance(v, (list, tuple)) else num(v) for v in ventas]


def ultimos(v, n):
    return v[len(v) - n:] if len(v) > n else list(v)


# ------------------------------------------------------------------ costo puesto

def costo_puesto(rep, prov, tc):
    usd = num(rep["costo_unitario_usd"])
    tc = num(tc)
    incluido = prov["incoterm"] == "CIF"
    fp = 0 if incluido else num(prov["flete_pct_aplicado"])
    g = num(prov["gastos_pct_cif"])
    total_usd = redondear(usd * ((1 + fp / 100) * (1 + g / 100)), 2)
    total = redondear(total_usd * tc, 2)
    fabrica = redondear(usd * tc, 2)
    flete = redondear(usd * fp / 100 * tc, 2)
    return {"fabrica_bs": fabrica, "flete_bs": flete, "gastos_bs": redondear(total - fabrica - flete, 2),
            "total_bs": total, "total_usd": total_usd, "incoterm": prov["incoterm"], "flete_incluido": incluido}


# ------------------------------------------------------------------ pronóstico

def pronostico(ventas, tipo=None):
    v = valores(ventas)
    if tipo is None:
        con_venta = sum(1 for x in v if x > 0)
        tipo = "suave" if con_venta > 0 and len(v) / con_venta <= 1.32 else "intermitente"
    if tipo in ("intermitente", "irregular"):
        z = p = None
        q = 0
        for x in v:
            q += 1
            if x > 0:
                if z is None:
                    z, p = x, q
                else:
                    z = z + ALFA_SBA * (x - z)
                    p = p + ALFA_SBA * (q - p)
                q = 0
        return {"metodo": "SBA", "unidades_mes": 0 if z is None else (1 - ALFA_SBA / 2) * z / p}
    return {"metodo": "media", "unidades_mes": media(ultimos(v, 12))}


def necesidad(tasa_dia, sigma_mes, clase, plazo, posicion):
    reserva = Z_CLASE[clase] * sigma_mes * math.sqrt(plazo / 30)
    return {"reserva": reserva, "cantidad": max(0, techo(tasa_dia * plazo + reserva - posicion))}


# ------------------------------------------------------------------ simulación de 90 días

def plazo_sorteado(r, prov, atraso):
    z = normal_ih(r)
    u = r()
    extra = ATRASO_EXTRA_MIN + ATRASO_EXTRA_RANGO * r()
    dias = num(prov["plazo_normal_dias"]) + num(atraso) + num(prov["desvio_plazo_dias"]) * z
    if u < (100 - num(prov["pct_entregas_a_tiempo"])) / 100:
        dias += extra
    return max(1, math.floor(dias + 0.5))


def simular(datos, rep_id, prov_id, sup, opc=None):
    opc = opc or {}
    par = datos["parametros"]
    n = int(opc["n"]) if opc.get("n") is not None else int(num(par["simulaciones"]))
    semilla = opc["semilla"] if opc.get("semilla") is not None else int(num(par["semilla"]))
    H = opc["horizonte_dias"] if opc.get("horizonte_dias") is not None else 90
    rep = buscar_repuesto(datos, rep_id)
    prov = buscar_proveedor(datos, prov_id or rep["proveedor_id"])
    tcb, tc90 = num(sup["tc_base"]), num(sup["tc_90"])
    f = 1 + num(sup["venta_pct"]) / 100
    atraso = num(sup["atraso_dias"])
    sigue = bool(sup.get("precio_sigue_dolar"))
    cped, tasa_cap = num(par["costo_pedido_bs"]), num(par["costo_capital_mensual"])

    hist = valores(datos["ventas"][rep_id])
    ult = ultimos(hist, 24)
    pr = pronostico(datos["ventas"][rep_id], rep["tipo_demanda"])
    tasa = pr["unidades_mes"] * f / 30
    sigma = desvio(ult) * f
    plazo_esp = num(prov["plazo_normal_dias"]) + atraso
    stock, camino = num(rep["stock_al_2026_11_10"]), num(rep["en_transito_al_2026_11_10"])
    pos = stock + camino
    nec = necesidad(tasa, sigma, rep["clase_abc"], plazo_esp, pos)
    q_a = max(1, nec["cantidad"])
    q_b = q_a + techo(30 * tasa)
    q_c = q_a + techo(60 * tasa)
    mitad = (q_c + 1) // 2
    cant = {"A": [q_a, 0], "B": [q_b, 0], "C": [q_c, 0], "D": [mitad, q_c - mitad]}
    cp = costo_puesto(rep, prov, tcb)
    cu = cp["total_usd"]
    precio = num(rep["precio_venta_bs"])
    dia_camino = math.floor(num(rep["plazo_normal_dias"]) / 2)
    s90 = volatilidad_diaria(datos["tc"]["serie"]) * math.sqrt(90)
    n_meses = math.ceil(H / 30)

    acum = {L: {"gan": [], "sum_gan": 0.0, "perd": 0.0, "quiebres": 0, "cap": 0.0, "gana": 0} for L in ALTERNATIVAS}
    r = mulberry32(semilla)
    meses = [0.0] * n_meses
    for _ in range(n):
        for m in range(n_meses):
            meses[m] = ult[math.floor(r() * len(ult))] * f
        zd = normal_ih(r)
        p1 = plazo_sorteado(r, prov, atraso)
        p2 = plazo_sorteado(r, prov, atraso)
        tc_fin = tc90 * exp_serie(s90 * zd - s90 * s90 / 2)
        tc30 = tcb + (tc_fin - tcb) * 30 / H
        mejor_gan, mejor_alt = 0.0, -1
        for a, L in enumerate(ALTERNATIVAS):
            q1, q2 = cant[L]
            c1, c2 = cu * tcb, cu * tc30
            viejo, nuevo, vend_nuevo, perd, ingreso, cap_sum = stock, 0.0, 0.0, 0.0, 0.0, 0.0
            for d in range(H):
                if d == dia_camino:
                    viejo += camino
                if d == p1:
                    nuevo += q1
                if q2 > 0 and d == 30 + p2:
                    nuevo += q2
                mi = min(math.floor(d / 30), n_meses - 1)
                dem = meses[mi] / 30
                vv = min(viejo, dem)
                viejo -= vv
                resto = dem - vv
                vn = min(nuevo, resto)
                nuevo -= vn
                vend_nuevo += vn
                resto -= vn
                perd += resto
                precio_dia = precio * (tcb + (tc_fin - tcb) * d / H) / tcb if sigue else precio
                ingreso += (vv + vn) * precio_dia
                pagado2 = q2 > 0 and d >= 30
                if vend_nuevo <= q1:
                    cap = (q1 - vend_nuevo) * c1 + (q2 * c2 if pagado2 else 0)
                else:
                    cap = (q1 + q2 - vend_nuevo) * c2
                cap_sum += cap
            pedidos = (1 if q1 > 0 else 0) + (1 if q2 > 0 else 0)
            residual = (q1 + q2 - vend_nuevo) * cu * tc_fin
            gan = ingreso - (q1 * c1 + q2 * c2) - cped * pedidos - cap_sum * tasa_cap / 30 + residual
            ac = acum[L]
            ac["gan"].append(gan)
            ac["sum_gan"] += gan
            ac["perd"] += perd
            if perd > 1e-6:
                ac["quiebres"] += 1
            ac["cap"] += cap_sum / H
            if mejor_alt < 0 or gan > mejor_gan:
                mejor_gan, mejor_alt = gan, a
        acum[ALTERNATIVAS[mejor_alt]]["gana"] += 1

    puntajes = repartir_cien([acum[L]["gana"] for L in ALTERNATIVAS], n)
    res = {}
    mejor = "A"
    for a, L in enumerate(ALTERNATIVAS):
        ac = acum[L]
        q = cant[L][0] + cant[L][1]
        nped = (1 if cant[L][0] > 0 else 0) + (1 if cant[L][1] > 0 else 0)
        orden = sorted(ac["gan"])
        capital = ac["cap"] / n if n else 0
        res[L] = {
            "cantidad": q, "cantidad_hoy": cant[L][0], "cantidad_30_dias": cant[L][1], "pedidos": nped,
            "costo": {"fabrica_bs": redondear(cp["fabrica_bs"] * q, 2), "flete_bs": redondear(cp["flete_bs"] * q, 2),
                      "gastos_bs": redondear(cp["gastos_bs"] * q, 2), "total_bs": redondear(cp["total_bs"] * q, 2),
                      "pedidos_bs": cped * nped, "flete_incluido": cp["flete_incluido"]},
            "margen_dias": redondear((pos + q - tasa * plazo_esp) / tasa, 0) if tasa > 0 else None,
            "riesgo_quiebre": redondear(100 * ac["quiebres"] / n, 0) if n else 0,
            "unidades_perdidas": ac["perd"] / n if n else 0,
            "capital_inmovilizado_bs": capital,
            "dias_venta_capital": redondear(capital / (tasa * cu * tcb), 0) if tasa > 0 and cu > 0 else None,
            "ganancia_media_bs": ac["sum_gan"] / n if n else 0,
            "ganancia_p10_bs": orden[math.floor(0.1 * (n - 1))] if n else 0,
            "futuros_ganados": ac["gana"],
            "puntaje": puntajes[a],
        }
        if ac["gana"] > acum[mejor]["gana"]:
            mejor = L
    res["mejor"] = mejor
    res["info"] = {"metodo": pr["metodo"], "unidades_mes": pr["unidades_mes"], "venta_dia": tasa,
                   "plazo_esperado": plazo_esp, "reserva": nec["reserva"], "stock": stock, "en_camino": camino,
                   "costo_unitario_bs": cp["total_bs"], "precio_bs": precio, "volatilidad_90": s90, "n": n,
                   "semilla": semilla}
    return res


def repartir_cien(cuentas, n):
    if not n:
        return [0 for _ in cuentas]
    crudo = [100 * c / n for c in cuentas]
    base = [math.floor(x + EPS) for x in crudo]
    falta = 100 - sum(base)
    idx = sorted(range(len(crudo)), key=lambda i: (-(crudo[i] - base[i]), i))
    for k in range(min(falta, len(idx))):
        base[idx[k]] += 1
    return base


def _opc_analisis(opc):
    opc = opc or {}
    return {"n": opc.get("n", N_ANALISIS), "semilla": opc.get("semilla"), "horizonte_dias": opc.get("horizonte_dias")}


# ------------------------------------------------------------------ dólar de quiebre y sensibilidad

def quiebre_dolar(datos, rep_id, prov_id, sup, opc=None):
    o = _opc_analisis(opc)
    memo = {}

    def mejor_en(k):
        if k not in memo:
            memo[k] = simular(datos, rep_id, prov_id, dict(sup, tc_90=(900 + 5 * k) / 100), o)["mejor"]
        return memo[k]

    antes, al_final = mejor_en(0), mejor_en(QUIEBRE_PASOS)
    if antes == al_final:
        return None
    lo, hi, despues = 0, QUIEBRE_PASOS, al_final
    while hi - lo > 1:
        mid = (lo + hi) // 2
        m = mejor_en(mid)
        if m == antes:
            lo = mid
        else:
            hi, despues = mid, m
    return {"valor": (900 + 5 * hi) / 100, "antes": antes, "despues": despues}


def sensibilidad(datos, rep_id, prov_id, sup, opc=None):
    o = _opc_analisis(opc)
    alt = simular(datos, rep_id, prov_id, sup, o)["mejor"]
    casos = [("dolar", "tc_90", 9, 15), ("venta", "venta_pct", -30, 30), ("atraso", "atraso_dias", 0, 30)]
    filas = []
    for i, (nombre, clave, minimo, maximo) in enumerate(casos):
        de = simular(datos, rep_id, prov_id, dict(sup, **{clave: minimo}), o)[alt]["ganancia_media_bs"]
        a = simular(datos, rep_id, prov_id, dict(sup, **{clave: maximo}), o)[alt]["ganancia_media_bs"]
        filas.append((i, {"supuesto": nombre, "rango_bs": abs(a - de), "de": de, "a": a, "alternativa": alt}))
    filas.sort(key=lambda x: (-x[1]["rango_bs"], x[0]))
    return [f for _, f in filas]


# ------------------------------------------------------------------ alertas y presupuesto

def dato_valido(x):
    """Número finito y no negativo, o None. Un dato vacío no se convierte en cero (criterio de HU-09)."""
    if x is None or (isinstance(x, str) and x.strip() == ""):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")) or v < 0:
        return None
    return v


def alertas(datos, tc):
    """Lógica única de alertas (SCRUM-66 unida con HU-09).

    Estados: 0 «Pedir ya» (stock + en camino en o bajo el punto de pedido), 1 «Vigilar» (llega al punto de pedido
    antes de que el proveedor pueda entregar), 2 «Cubierto», 3 «Sin datos» (falta stock, plazo o historial de venta;
    no se rellena con cero). Demanda durante la entrega = venta diaria pronosticada × plazo, sin redondear antes de
    comparar. Faltante previsto = max(0, demanda durante la entrega − (stock + en camino)); la igualdad no es faltante.
    """
    filas = []
    for rep in datos["repuestos"]:
        prov = next((p for p in datos["proveedores"] if p["proveedor_id"] == rep.get("proveedor_id")), None)
        ventas = datos["ventas"].get(rep["repuesto_id"]) or []
        stock, camino = dato_valido(rep.get("stock_al_2026_11_10")), dato_valido(rep.get("en_transito_al_2026_11_10"))
        s, S = dato_valido(rep.get("punto_pedido_s")), dato_valido(rep.get("nivel_maximo_S"))
        plazo = dato_valido(prov.get("plazo_normal_dias")) if prov else None
        motivos = []
        if stock is None or camino is None:
            motivos.append("STOCK_FALTANTE")
        if plazo is None:
            motivos.append("PLAZO_FALTANTE")
        if len(ventas) == 0 or any(dato_valido(v[1]) is None for v in ventas):
            motivos.append("DEMANDA_FALTANTE")
        if s is None or S is None:
            motivos.append("REGLA_FALTANTE")
        base = {"id": rep["repuesto_id"], "clase": rep["clase_abc"], "tipo_demanda": rep["tipo_demanda"],
                "proveedor_id": rep["proveedor_id"]}
        if motivos:
            base.update({"est": 3, "etiqueta": ETIQUETAS[3], "motivos": motivos, "stock": stock, "en_camino": camino,
                         "punto_pedido": s, "nivel_maximo": S, "plazo": plazo, "margen_dias": None,
                         "demanda_entrega": None, "faltante_previsto": None, "cantidad_sugerida": 0,
                         "costo_bs": None, "venta_mes": None, "_m": None, "_f": 0})
            filas.append(base)
            continue
        pr = pronostico(ventas, rep["tipo_demanda"])
        tasa = pr["unidades_mes"] / 30
        pos = stock + camino
        demanda = tasa * plazo
        faltante = demanda - pos if demanda > pos else 0
        margen = (pos - s) / tasa if tasa > 0 else None
        est = 0 if pos <= s else (1 if margen is not None and margen < plazo else 2)
        cantidad = max(math.floor(S - pos + 0.5), 0)
        if est < 2:
            cantidad = max(cantidad, 1)
        cp = costo_puesto(rep, prov, tc)
        base.update({
            "est": est, "etiqueta": ETIQUETAS[est], "motivos": [], "stock": stock, "en_camino": camino,
            "punto_pedido": s, "nivel_maximo": S, "plazo": plazo,
            "margen_dias": None if margen is None else math.floor(margen + EPS),
            "demanda_entrega": demanda, "faltante_previsto": faltante,
            "cantidad_sugerida": cantidad, "costo_bs": redondear(cantidad * cp["total_bs"], 2),
            "venta_mes": pr["unidades_mes"], "_m": margen, "_f": faltante})
        filas.append(base)
    filas.sort(key=lambda x: (x["est"], -x["_f"], x["_m"] is None, x["_m"] if x["_m"] is not None else 0, x["id"]))
    for x in filas:
        del x["_m"]
        del x["_f"]
    return filas


def plan_presupuesto(filas_alertas, presupuesto):
    presupuesto = num(presupuesto)
    filas = [dict(x) for x in filas_alertas if x["cantidad_sugerida"] > 0]
    filas.sort(key=lambda x: (x["est"], ORDEN_CLASE[x["clase"]], x["margen_dias"] is None,
                              x["margen_dias"] if x["margen_dias"] is not None else 0, x["id"]))
    acum, sigue = 0, True
    for x in filas:
        acum = redondear(acum + x["costo_bs"], 2)
        sigue = sigue and acum <= presupuesto + EPS
        x["acumulado_bs"] = acum
        x["alcanza"] = sigue
    return filas


# ------------------------------------------------------------------ proveedores

def comparar_proveedores(datos, rep_id, tc):
    rep = buscar_repuesto(datos, rep_id)
    filas = []
    for p in datos["proveedores"]:
        c = costo_puesto(rep, p, tc)
        filas.append({
            "proveedor_id": p["proveedor_id"], "nombre": p["nombre"], "origen": p["origen"], "incoterm": p["incoterm"],
            "plazo_normal_dias": num(p["plazo_normal_dias"]), "desvio_plazo_dias": num(p["desvio_plazo_dias"]),
            "pct_entregas_a_tiempo": num(p["pct_entregas_a_tiempo"]), "asignado": p["proveedor_id"] == rep["proveedor_id"],
            "fabrica_bs": c["fabrica_bs"], "flete_bs": c["flete_bs"], "gastos_bs": c["gastos_bs"],
            "total_bs": c["total_bs"], "total_usd": c["total_usd"], "flete_incluido": c["flete_incluido"]})
    filas.sort(key=lambda x: (x["total_bs"], x["proveedor_id"]))
    return filas


# ------------------------------------------------------------------ ¿qué hubiera pasado?

def dias_del_mes(anio, mes):
    if mes == 2:
        return 29 if (anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0)) else 28
    return 30 if mes in (4, 6, 9, 11) else 31


def calendario_pasado():
    dias = []
    anio, mes = 2025, 11
    for _ in range(12):
        dm = dias_del_mes(anio, mes)
        for d in range(1, dm + 1):
            dias.append(("%04d-%02d-%02d" % (anio, mes, d), "%04d-%02d" % (anio, mes), dm))
        mes += 1
        if mes > 12:
            mes, anio = 1, anio + 1
    return dias


def tc_del_dia(fecha, tabla, serie):
    if fecha < INICIO_TCO:
        return TC_FIJO
    if fecha in tabla:
        return tabla[fecha]
    v = TC_FIJO
    for f, x in serie:
        if f <= fecha:
            v = num(x)
    return v


def pasado(datos, politica):
    if politica not in ("lo_justo", "cubrir_60", "dos_pedidos"):
        raise ValueError("Política desconocida: " + politica)
    par = datos["parametros"]
    cped, tasa_cap = num(par["costo_pedido_bs"]), num(par["costo_capital_mensual"])
    dias = calendario_pasado()
    nd = len(dias)
    serie = datos["tc"]["serie"]
    tabla = {f: num(x) for f, x in serie}
    tcs = [tc_del_dia(x[0], tabla, serie) for x in dias]
    total = {"politica": politica, "ventas_perdidas": 0.0, "ventas_atendidas": 0.0, "capital_promedio_bs": 0.0,
             "pedidos": 0, "ganancia_bs": 0.0, "ordenes": []}

    for rep in datos["repuestos"]:
        prov = buscar_proveedor(datos, rep["proveedor_id"])
        plazo = num(prov["plazo_normal_dias"])
        plazo_i = int(plazo)
        cu = costo_puesto(rep, prov, 1)["total_usd"]
        precio, tc_ref = num(rep["precio_venta_bs"]), num(rep["tc_referencia_bs_por_usd"])
        ventas = datos["ventas"][rep["repuesto_id"]]
        por_mes = {m: num(u) for m, u in ventas}
        stock = num(rep["nivel_maximo_S"])
        llegadas, programadas = [], []
        st = {"compras": 0.0, "pedidos": 0}
        ingreso = cap_sum = perdidas = atendidas = 0.0
        valor_inicial = stock * cu * tcs[0]

        def pedir(idx, q):
            st["compras"] += q * cu * tcs[idx]
            st["pedidos"] += 1
            llegadas.append((idx + plazo_i, q))
            total["ordenes"].append({"repuesto_id": rep["repuesto_id"], "fecha": dias[idx][0], "cantidad": q,
                                     "tc": tcs[idx]})

        for di in range(nd):
            fecha, mes_actual, dm = dias[di]
            for dia_l, q in llegadas:
                if dia_l == di:
                    stock += q
            for dia_p, q in programadas:
                if dia_p == di:
                    pedir(di, q)
            if fecha[8:] == "01":
                hist = [v for v in ventas if v[0] < mes_actual]
                pr = pronostico(hist, rep["tipo_demanda"])
                tasa = pr["unidades_mes"] / 30
                sigma = desvio(ultimos(valores(hist), 24))
                pos = stock
                for dia_l, q in llegadas:
                    if dia_l > di:
                        pos += q
                for dia_p, q in programadas:
                    if dia_p > di:
                        pos += q
                qa = necesidad(tasa, sigma, rep["clase_abc"], plazo, pos)["cantidad"]
                if qa > 0:
                    if politica == "lo_justo":
                        pedir(di, qa)
                    else:
                        qc = qa + techo(60 * tasa)
                        if politica == "cubrir_60":
                            pedir(di, qc)
                        else:
                            q1 = (qc + 1) // 2
                            q2 = qc - q1
                            pedir(di, q1)
                            if q2 > 0 and di + 30 < nd:
                                programadas.append((di + 30, q2))
            dem = por_mes.get(mes_actual, 0) / dm
            vend = min(stock, dem)
            stock -= vend
            perdidas += dem - vend
            atendidas += vend
            ingreso += vend * precio * tcs[di] / tc_ref
            cap_sum += stock * cu * tcs[di]
        en_camino = 0
        for dia_l, q in llegadas:
            if dia_l >= nd:
                en_camino += q
        valor_final = (stock + en_camino) * cu * tcs[nd - 1]
        total["ventas_perdidas"] += perdidas
        total["ventas_atendidas"] += atendidas
        total["capital_promedio_bs"] += cap_sum / nd
        total["pedidos"] += st["pedidos"]
        total["ganancia_bs"] += (ingreso - st["compras"] - cped * st["pedidos"] - cap_sum * tasa_cap / 30
                                 + valor_final - valor_inicial)
    return total


# ------------------------------------------------------------------ temporadas (SCRUM-75)

def perfil_mensual(serie):
    """Venta promedio por mes del año (ver motor.js: perfilMensual). Un mes no válido no entra a su promedio."""
    suma, obs = [0] * 12, [0] * 12
    for mes, u in serie:
        u = dato_valido(u)
        if u is None:
            continue
        try:
            m = int(str(mes)[5:7]) - 1
        except ValueError:
            continue
        if not 0 <= m < 12:
            continue
        suma[m] += u
        obs[m] += 1
    prom, acum, con_dato = [], 0, 0
    for i in range(12):
        prom.append(suma[i] / obs[i] if obs[i] else None)
        if obs[i]:
            acum += prom[i]
            con_dato += 1
    media = acum / con_dato if con_dato else None
    indice, fuertes, pico, flojo = [], [], None, None
    for i in range(12):
        indice.append(None if prom[i] is None or not media else prom[i] / media)
        if prom[i] is None:
            continue
        if media is not None and prom[i] > media + EPS:
            fuertes.append(i + 1)
        if pico is None or prom[i] > prom[pico - 1] + EPS:
            pico = i + 1
        if flojo is None or prom[i] < prom[flojo - 1] - EPS:
            flojo = i + 1
    return {"promedio_mes": prom, "observaciones": obs, "media": media, "indice": indice,
            "meses_fuertes": fuertes, "mes_pico": pico, "mes_flojo": flojo}


def temporadas(datos):
    por_mes, claves, repuestos = {}, [], []
    for r in datos["repuestos"]:
        rid = r["repuesto_id"]
        serie = datos["ventas"].get(rid, [])
        for mes, u in serie:
            u = dato_valido(u)
            if u is None:
                continue
            if mes not in por_mes:
                por_mes[mes] = 0
                claves.append(mes)
            por_mes[mes] += u
        p = perfil_mensual(serie)
        p["id"] = rid
        repuestos.append(p)
    claves.sort()
    return {"repuestos": repuestos, "total": perfil_mensual([[k, por_mes[k]] for k in claves])}


# ------------------------------------------------------------------ cotización (SCRUM-72)

TRAMOS_EJEMPLO = [{"desde": 10, "pct": 5}, {"desde": 50, "pct": 10}]


def cotizar(datos, rep_id, cantidad, tc, tramos=None):
    """Precio de una cantidad con descuento por volumen (ver motor.js: cotizar)."""
    rep = buscar_repuesto(datos, rep_id)
    try:
        q = float(cantidad)
    except (TypeError, ValueError):
        q = float("nan")
    if q != q or q in (float("inf"), float("-inf")) or q < 1 or math.floor(q) != q:
        raise ValueError("La cantidad debe ser un número entero de 1 o más")
    q = int(q)
    tc = num(tc)
    if tc != tc or tc in (float("inf"), float("-inf")) or tc <= 0:
        raise ValueError("El dólar debe ser un número mayor que cero")
    t = sorted(tramos or TRAMOS_EJEMPLO, key=lambda x: x["desde"])
    prov = buscar_proveedor(datos, rep["proveedor_id"])
    costo = costo_puesto(rep, prov, tc)["total_bs"]
    lista = redondear(num(rep["precio_venta_usd"]) * tc, 2)
    pct, siguiente = 0, None
    for x in t:
        if q >= x["desde"]:
            pct = x["pct"]
        elif siguiente is None:
            siguiente = {"desde": x["desde"], "pct": x["pct"], "faltan": x["desde"] - q}
    max_pct = max(0, (1 - costo / lista) * 100) if lista > 0 else 0
    tope = pct > max_pct + EPS
    unitario = costo if tope else redondear(lista * (1 - pct / 100), 2)
    subtotal, total = redondear(lista * q, 2), redondear(unitario * q, 2)
    stock = dato_valido(rep.get("stock_al_2026_11_10"))
    en_stock = None if stock is None else min(stock, q)
    return {
        "id": rep["repuesto_id"], "cantidad": q, "tc": tc, "precio_lista_bs": lista, "costo_puesto_bs": costo,
        "pct_tramo": pct, "pct_aplicado": redondear(max_pct, 2) if tope else pct, "tope": tope,
        "precio_unitario_bs": unitario, "subtotal_bs": subtotal, "descuento_bs": redondear(subtotal - total, 2),
        "total_bs": total, "siguiente_tramo": siguiente, "stock": stock, "en_stock": en_stock,
        "por_pedir": None if en_stock is None else q - en_stock, "plazo_dias": num(prov["plazo_normal_dias"])}


# ------------------------------------------------------------------ clientes (SCRUM-76)

def tablero_clientes(datos, tc):
    """Tablero de clientes SINTÉTICOS (ver motor.js: tableroClientes)."""
    tc = num(tc)
    temporada = temporadas(datos)["total"]["meses_fuertes"]
    en_temp = set(temporada)
    precio = {r["repuesto_id"]: redondear(num(r["precio_venta_usd"]) * tc, 2) for r in datos["repuestos"]}
    C, orden = {}, []
    for c in datos["clientes"]["lista"]:
        C[c["cliente_id"]] = {"id": c["cliente_id"], "nombre": c["nombre"], "tipo": c["tipo"], "zona": c["zona"],
                              "unidades": 0, "monto_bs": 0, "unid_temp": 0, "unid_fuera": 0,
                              "monto_temp_bs": 0, "monto_fuera_bs": 0, "_rep": {}}
        orden.append(c["cliente_id"])
    total = {"unidades": 0, "monto_bs": 0, "monto_temp_bs": 0, "monto_fuera_bs": 0}
    for mes, rep, cli, u in datos["clientes"]["ventas"]:
        c, u = C.get(cli), dato_valido(u)
        if c is None or u is None or rep not in precio:
            continue
        monto = u * precio[rep]
        try:
            t = int(str(mes)[5:7]) in en_temp
        except ValueError:
            t = False
        c["unidades"] += u
        c["monto_bs"] += monto
        if t:
            c["unid_temp"] += u
            c["monto_temp_bs"] += monto
            total["monto_temp_bs"] += monto
        else:
            c["unid_fuera"] += u
            c["monto_fuera_bs"] += monto
            total["monto_fuera_bs"] += monto
        c["_rep"][rep] = c["_rep"].get(rep, 0) + u
        total["unidades"] += u
        total["monto_bs"] += monto
    lista = []
    for cid in orden:
        c = C[cid]
        c["pct_temp"] = c["monto_temp_bs"] / c["monto_bs"] * 100 if c["monto_bs"] > 0 else None
        c["pct_total"] = c["monto_bs"] / total["monto_bs"] * 100 if total["monto_bs"] > 0 else None
        c["top"] = [{"id": r, "unidades": n} for r, n in sorted(c["_rep"].items(), key=lambda x: (-x[1], x[0]))][:3]
        del c["_rep"]
        lista.append(c)
    lista.sort(key=lambda c: (-c["monto_bs"], c["id"]))
    tipos, orden_tipos = {}, []
    for c in lista:
        if c["tipo"] not in tipos:
            tipos[c["tipo"]] = {"tipo": c["tipo"], "clientes": 0, "monto_bs": 0, "monto_temp_bs": 0}
            orden_tipos.append(c["tipo"])
        tipos[c["tipo"]]["clientes"] += 1
        tipos[c["tipo"]]["monto_bs"] += c["monto_bs"]
        tipos[c["tipo"]]["monto_temp_bs"] += c["monto_temp_bs"]
    por_tipo = sorted((tipos[t] for t in orden_tipos), key=lambda x: (-x["monto_bs"], x["tipo"]))
    return {"temporada": temporada, "clientes": lista, "por_tipo": por_tipo, "total": total}


# ------------------------------------------------------------------ dashboard (SCRUM-79)

def mes_menos(mes, k):
    a, m = int(str(mes)[:4]), int(str(mes)[5:7]) - 1 - k
    a += m // 12
    m %= 12
    return f"{a}-{m + 1:02d}"


def trimestre(mes):
    return f"{str(mes)[:4]}-T{(int(str(mes)[5:7]) - 1) // 3 + 1}"


def filas_de_ventas(datos, tc):
    """Ventas válidas con su monto en Bs (ver motor.js: filasDeVentas)."""
    import re
    precio = {r["repuesto_id"]: redondear(num(r["precio_venta_usd"]) * tc, 2) for r in datos["repuestos"]}
    nombre = {c["cliente_id"]: c["nombre"] for c in datos["clientes"]["lista"]}
    filas = []
    for v in datos["clientes"]["ventas"]:
        u, mes = dato_valido(v[3]), str(v[0])
        if u is None or v[1] not in precio or v[2] not in nombre or not re.fullmatch(r"\d{4}-\d{2}", mes):
            continue
        filas.append({"mes": mes, "rep": v[1], "cli": v[2], "u": u, "bs": u * precio[v[1]]})
    return filas, nombre


def dashboard(datos, tc):
    """Dashboard de ventas (ver motor.js: dashboard). Todo sale de las compras por cliente."""
    tc = num(tc)
    filas, nombre = filas_de_ventas(datos, tc)
    total = {"unidades": 0, "monto_bs": 0}
    if not filas:
        return {"meses": [], "demanda_mes": [], "por_anio": [], "total": total, "repuestos": [], "clientes": [],
                "trimestres": [], "ultimo_mes": None, "ult12_bs": 0, "prev12_bs": 0, "top5_pct": None}
    meses = sorted(f["mes"] for f in filas)
    desde, ultimo = meses[0], meses[-1]
    lista, k = [], 0
    while True:
        m = mes_menos(ultimo, k)
        lista.insert(0, m)
        if m == desde:
            break
        k += 1
    dm = {m: {"mes": m, "unidades": 0, "monto_bs": 0} for m in lista}
    trims = []
    for m in lista:
        if not trims or trims[-1] != trimestre(m):
            trims.append(trimestre(m))
    r6, p6, r12, p12 = mes_menos(ultimo, 5), mes_menos(ultimo, 11), mes_menos(ultimo, 11), mes_menos(ultimo, 23)
    ult12 = prev12 = 0
    anios, reps, clis = {}, {}, {}
    for f in filas:
        total["unidades"] += f["u"]
        total["monto_bs"] += f["bs"]
        dm[f["mes"]]["unidades"] += f["u"]
        dm[f["mes"]]["monto_bs"] += f["bs"]
        a = anios.setdefault(f["mes"][:4], {"anio": f["mes"][:4], "unidades": 0, "monto_bs": 0, "meses": set()})
        a["unidades"] += f["u"]
        a["monto_bs"] += f["bs"]
        a["meses"].add(f["mes"])
        r = reps.setdefault(f["rep"], {"id": f["rep"], "unidades": 0, "monto_bs": 0})
        r["unidades"] += f["u"]
        r["monto_bs"] += f["bs"]
        c = clis.setdefault(f["cli"], {"id": f["cli"], "nombre": nombre[f["cli"]], "unidades": 0, "monto_bs": 0,
                                       "ult6_bs": 0, "prev6_bs": 0, "ultima_compra": f["mes"], "_t": {}})
        c["unidades"] += f["u"]
        c["monto_bs"] += f["bs"]
        c["_t"][trimestre(f["mes"])] = c["_t"].get(trimestre(f["mes"]), 0) + f["bs"]
        c["ultima_compra"] = max(c["ultima_compra"], f["mes"])
        if f["mes"] >= r6:
            c["ult6_bs"] += f["bs"]
        elif f["mes"] >= p6:
            c["prev6_bs"] += f["bs"]
        if f["mes"] >= r12:
            ult12 += f["bs"]
        elif f["mes"] >= p12:
            prev12 += f["bs"]
    por_anio = [{"anio": a, "unidades": x["unidades"], "monto_bs": x["monto_bs"], "meses": len(x["meses"])}
                for a, x in sorted(anios.items())]
    for r in reps.values():
        r["pct_unidades"] = r["unidades"] / total["unidades"] * 100
    repuestos = sorted(reps.values(), key=lambda r: (-r["unidades"], -r["monto_bs"], r["id"]))
    clientes = []
    for c in clis.values():
        c["trimestres"] = [c["_t"].get(t, 0) for t in trims]
        c["pct_total"] = c["monto_bs"] / total["monto_bs"] * 100
        c["variacion_pct"] = (c["ult6_bs"] - c["prev6_bs"]) / c["prev6_bs"] * 100 if c["prev6_bs"] > 0 else None
        if c["ult6_bs"] == 0 and c["prev6_bs"] == 0:
            c["tendencia"] = "sin compras"
        elif c["prev6_bs"] == 0:
            c["tendencia"] = "nuevo"
        else:
            c["tendencia"] = "sube" if c["variacion_pct"] >= 10 else "baja" if c["variacion_pct"] <= -10 else "estable"
        del c["_t"]
        clientes.append(c)
    clientes.sort(key=lambda c: (-c["monto_bs"], c["id"]))
    top5 = sum(c["monto_bs"] for c in clientes[:5])
    return {"meses": lista, "demanda_mes": [dm[m] for m in lista], "por_anio": por_anio, "total": total,
            "repuestos": repuestos, "clientes": clientes, "trimestres": trims, "ultimo_mes": ultimo,
            "ult12_bs": ult12, "prev12_bs": prev12, "top5_pct": top5 / total["monto_bs"] * 100 if total["monto_bs"] > 0 else None}


# ------------------------------------------------------------------ tablero para la gerencia (SCRUM-79, versión empresarial)

TIPO_PLURAL = {"Taller mecánico": "los talleres mecánicos", "Repuestera": "las repuesteras",
               "Flota de empresa": "las flotas de empresa", "Particular": "los particulares",
               "Tienda web": "las ventas de la tienda web"}
MES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
DONA_MAX = 5
NOMBRE_CORTO_MAX = 44
CONECTORES = ["con", "de", "del", "para", "y", "a", "en"]


def miles(x):
    """Entero con punto de miles (ver motor.js: miles)."""
    n = int(redondear(abs(x), 0))
    s = f"{n:,}".replace(",", ".")
    return ("−" if x < 0 and n != 0 else "") + s


def bs_txt(x):
    return "Bs " + miles(x)


def _pl(n, uno, varios):
    return uno if n == 1 else varios


def _mayuscula(s):
    return s[:1].upper() + s[1:]


def _minuscula(s):
    return s[:1].lower() + s[1:]


def mes_largo(m):
    return f"{MES_LARGO[int(m[5:7]) - 1]} de {m[:4]}"


def enteros100(valores):
    """Porcentajes enteros que suman 100, por el resto mayor (ver motor.js: enteros100)."""
    tot = sum(valores)
    if not tot > 0:
        return [0 for _ in valores]
    crudo = [v / tot * 100 for v in valores]
    base = [math.floor(c) for c in crudo]
    resto = 100 - sum(base)
    orden = sorted(range(len(crudo)), key=lambda i: (-(crudo[i] - base[i]), i))
    for k in range(resto):
        base[orden[k]] += 1
    return base


def nombre_corto(s):
    s = str(s)
    if len(s) <= NOMBRE_CORTO_MAX:
        return s
    p = s[:s.rfind(" ", 0, NOMBRE_CORTO_MAX)].split(" ")
    while len(p) > 1 and p[-1].lower() in CONECTORES:
        p.pop()
    return re.sub(r",$", "", " ".join(p)) + "…"


def _sumar_por(filas, clave):
    acc = {}
    for f in filas:
        k = clave(f)
        x = acc.setdefault(k, {"clave": k, "monto_bs": 0, "unidades": 0})
        x["monto_bs"] += f["bs"]
        x["unidades"] += f["u"]
    return sorted(acc.values(), key=lambda x: (-x["monto_bs"], x["clave"]))


def _variacion(ahora, antes):
    return (ahora - antes) / antes * 100 if antes > 0 else None


def tablero_empresa(datos, tc, periodo="12m"):
    """Tablero de ventas en lenguaje simple (ver motor.js: tableroEmpresa)."""
    periodo = "todo" if periodo == "todo" else "12m"
    tc = num(tc)
    sem, costo_pedir = [0, 0, 0, 0], 0
    for a in alertas(datos, tc):
        sem[a["est"]] += 1
        if a["est"] == 0:
            costo_pedir += num(a["costo_bs"])
    r = rotacion(datos, tc)
    estados = [e for e in [("pedir", "Pedir ya", sem[0]), ("vigilar", "Vigilar", sem[1]),
                           ("suficiente", "Con stock suficiente", sem[2]), ("sin_datos", "Sin datos para decidir", sem[3])]
               if e[0] != "sin_datos" or e[2] > 0]
    pct_alm = enteros100([e[2] for e in estados])
    almacen = [{"clave": e[0], "etiqueta": e[1], "repuestos": e[2], "pct": pct_alm[i]} for i, e in enumerate(estados)]
    concl_alm = ((f"{sem[0]} " + _pl(sem[0], "repuesto está por agotarse y hay que pedirlo ya.",
                                     "repuestos están por agotarse y hay que pedirlos ya.")) if sem[0] > 0
                 else "Ningún repuesto está por agotarse.")
    if sem[1] > 0:
        concl_alm += f" {sem[1]} más " + _pl(sem[1], "hay que vigilarlo", "hay que vigilarlos") + "."
    concl_alm += " " + _mayuscula(f"{sem[2]} " + _pl(sem[2], "tiene", "tienen") + " stock suficiente.")
    if sem[3] > 0:
        concl_alm += f" De {sem[3]} no hay datos para decidir."
    hoy = {"pedir_ya": {"repuestos": sem[0], "costo_bs": costo_pedir},
           "dinero_parado": {"valor_bs": r["valor_acumulado_bs"], "repuestos": r["acumulacion"]},
           "almacen": almacen, "almacen_total": sum(sem)}

    t = dashboard(datos, tc)
    filas_todas, nombre = filas_de_ventas(datos, tc)
    if not t["meses"]:
        return {"periodo": periodo, "vacio": True, "hoy": hoy, "conclusiones": {"almacen": concl_alm}}
    ultimo = t["ultimo_mes"]
    desde = t["meses"][0] if periodo == "todo" else mes_menos(ultimo, 11)
    desde = max(desde, t["meses"][0])
    filas = [f for f in filas_todas if f["mes"] >= desde]

    r12, p12 = mes_menos(ultimo, 11), mes_menos(ultimo, 23)
    c = {"ult12_bs": 0, "prev12_bs": 0, "ult12_u": 0, "prev12_u": 0}
    for f in filas_todas:
        if f["mes"] >= r12:
            c["ult12_bs"] += f["bs"]
            c["ult12_u"] += f["u"]
        elif f["mes"] >= p12:
            c["prev12_bs"] += f["bs"]
            c["prev12_u"] += f["u"]
    c["var_bs_pct"] = _variacion(c["ult12_bs"], c["prev12_bs"])
    c["var_u_pct"] = _variacion(c["ult12_u"], c["prev12_u"])
    tot_bs, tot_u = 0, 0
    for f in filas:
        tot_bs += f["bs"]
        tot_u += f["u"]

    meses = [{"mes": x["mes"], "monto_bs": x["monto_bs"], "unidades": x["unidades"]} for x in t["demanda_mes"] if x["mes"] >= desde]
    mejor = meses[0]
    for x in meses:
        if x["monto_bs"] > mejor["monto_bs"]:
            mejor = x
    prom_mes = tot_bs / len(meses)

    tipo_de = {x["cliente_id"]: x.get("tipo") or "Sin tipo" for x in datos["clientes"]["lista"]}
    tipos = _sumar_por(filas, lambda f: tipo_de[f["cli"]])
    if len(tipos) > DONA_MAX:
        otros = {"clave": "Otros", "monto_bs": 0, "unidades": 0}
        for x in tipos[DONA_MAX - 1:]:
            otros["monto_bs"] += x["monto_bs"]
            otros["unidades"] += x["unidades"]
        tipos = tipos[:DONA_MAX - 1] + [otros]
    pct_tipos = enteros100([x["monto_bs"] for x in tipos])
    tipos = [{"tipo": x["clave"], "monto_bs": x["monto_bs"], "unidades": x["unidades"], "pct": pct_tipos[i]}
             for i, x in enumerate(tipos)]

    cat, nom_rep = {}, {}
    for x in (datos.get("catalogo") or {}).get("repuestos") or []:
        cat[x["repuesto_id"]] = x["categoria"]
        nom_rep[x["repuesto_id"]] = x["nombre"]

    def con_pct(lista):
        for x in lista:
            x["pct"] = x["monto_bs"] / tot_bs * 100 if tot_bs > 0 else 0
        return lista

    categorias = con_pct([{"categoria": x["clave"], "monto_bs": x["monto_bs"], "unidades": x["unidades"]}
                          for x in _sumar_por(filas, lambda f: cat.get(f["rep"]) or "Sin categoría")])
    clientes = con_pct([{"id": x["clave"], "nombre": str(nombre[x["clave"]]).replace(" (ficticio)", ""),
                         "monto_bs": x["monto_bs"], "unidades": x["unidades"]} for x in _sumar_por(filas, lambda f: f["cli"])])
    repuestos = con_pct([{"id": x["clave"], "nombre": nom_rep.get(x["clave"]) or x["clave"],
                          "nombre_corto": nombre_corto(nom_rep.get(x["clave"]) or x["clave"]),
                          "monto_bs": x["monto_bs"], "unidades": x["unidades"]} for x in _sumar_por(filas, lambda f: f["rep"])])

    def suma(lista):
        s = 0
        for x in lista:
            s += x["monto_bs"]
        return s

    top5, top10 = clientes[:5], repuestos[:10]
    top5_pct = suma(top5) / tot_bs * 100 if tot_bs > 0 else 0
    top10_pct = suma(top10) / tot_bs * 100 if tot_bs > 0 else 0
    por_anio = [{"anio": a["anio"], "monto_bs": a["monto_bs"], "unidades": a["unidades"], "meses": a["meses"],
                 "completo": a["meses"] >= 12} for a in t["por_anio"]]

    tipo0 = tipos[0]
    quien = TIPO_PLURAL.get(tipo0["tipo"]) or f"los clientes de tipo «{tipo0['tipo']}»"
    concl_tipos = (f"Más de la mitad de lo que vendemos se lo llevan {quien} ({tipo0['pct']} %)." if tipo0["pct"] > 50
                   else f"{_mayuscula(quien)} son los que más compran: se llevan el {tipo0['pct']} % de lo que vendemos.")
    cat0, cat_n = categorias[0], categorias[-1]
    concl_cat = f"Lo que más vendemos es {_minuscula(cat0['categoria'])}: el {miles(cat0['pct'])} % de las ventas."
    if len(categorias) > 1:
        concl_cat += f" Lo que menos, {_minuscula(cat_n['categoria'])} ({miles(cat_n['pct'])} %)."
    concl_cli = (f"Estos {len(top5)} clientes (de {len(clientes)}) dejan el {miles(top5_pct)} % de las ventas." +
                 (" Si uno deja de comprar, se nota." if top5_pct >= 50 else " Las ventas están repartidas entre muchos clientes."))
    concl_rep = (f"Estos {len(top10)} repuestos (de {len(repuestos)}) dejan el {miles(top10_pct)} % de las ventas." +
                 (" Conviene no quedarse nunca sin ellos." if top10_pct >= 50 else ""))
    comp = [a for a in por_anio if a["completo"]]
    if len(comp) >= 2:
        x, y = comp[-2], comp[-1]
        d_bs, d_u = _variacion(y["monto_bs"], x["monto_bs"]), _variacion(y["unidades"], x["unidades"])
        if abs(d_bs) < 5:
            if abs(d_u) < 5:
                concl_anio = f"{x['anio']} y {y['anio']} vendieron casi lo mismo, en dinero y en piezas."
            else:
                concl_anio = (f"{x['anio']} y {y['anio']} vendieron lo mismo en dinero, aunque en {y['anio']} salieron "
                              f"{'más' if d_u > 0 else 'menos'} piezas: se vendieron repuestos más {'baratos' if d_u > 0 else 'caros'}.")
        else:
            concl_anio = f"{y['anio']} vendió {miles(abs(d_bs))} % {'más' if d_bs > 0 else 'menos'} que {x['anio']} en dinero."
    elif len(comp) == 1:
        concl_anio = f"{comp[0]['anio']} es el único año completo: {bs_txt(comp[0]['monto_bs'])}."
    else:
        concl_anio = "Todavía no hay un año completo para comparar."

    return {
        "periodo": periodo, "vacio": False, "desde": desde, "hasta": ultimo, "meses_periodo": len(meses),
        "tarjetas": {"ventas_bs": tot_bs, "unidades": tot_u, "comparacion": c},
        "hoy": hoy,
        "meses": meses, "promedio_mes_bs": prom_mes, "mejor_mes": {"mes": mejor["mes"], "monto_bs": mejor["monto_bs"]},
        "tipos_cliente": tipos, "categorias": categorias, "clientes": clientes, "clientes_total": len(clientes),
        "top_clientes": top5, "top_clientes_pct": top5_pct, "repuestos": repuestos, "repuestos_total": len(repuestos),
        "top_repuestos": top10, "top_repuestos_pct": top10_pct, "por_anio": por_anio,
        "conclusiones": {
            "meses": f"{_mayuscula(mes_largo(mejor['mes']))} fue el mejor mes ({bs_txt(mejor['monto_bs'])}). "
                     f"En promedio, cada mes se venden {bs_txt(prom_mes)}.",
            "tipos_cliente": concl_tipos, "almacen": concl_alm, "categorias": concl_cat, "top_clientes": concl_cli,
            "top_repuestos": concl_rep, "anios": concl_anio,
        },
    }


# ------------------------------------------------------------------ rotación e importancia (SCRUM-81)

ROT_ALTA_MESES = 3
ROT_MEDIA_MESES = 12
ACUM_MESES = 24
ABC_CORTES = [0.80, 0.95]


def rotacion(datos, tc):
    """ABC por valor de los últimos 12 meses cruzado con la rotación (ver motor.js: rotacion)."""
    tc = num(tc)
    filas = []
    for r in datos["repuestos"]:
        rid = r["repuesto_id"]
        v = [dato_valido(x[1] if isinstance(x, (list, tuple)) else x) for x in datos["ventas"].get(rid, [])]
        stock = dato_valido(r.get("stock_al_2026_11_10"))
        transito = dato_valido(r.get("en_transito_al_2026_11_10")) or 0
        smax = dato_valido(r.get("nivel_maximo_S"))
        pv = redondear(num(r["precio_venta_usd"]) * tc, 2)
        cp = num(r["costo_puesto_usd"]) * tc
        validos = [x for x in v if x is not None]
        if len(validos) < 12 or stock is None:
            filas.append({"id": rid, "sin_datos": True,
                          "motivo": "no tiene 12 meses de ventas" if len(validos) < 12 else "no tiene stock registrado",
                          "u12": None, "valor12_bs": 0, "stock": stock, "transito": transito, "nivel_maximo": smax})
            continue
        u12 = sum(ultimos(validos, 12))
        sin = 0
        for x in reversed(validos):
            if x != 0:
                break
            sin += 1
        cob = stock / (u12 / 12) if u12 > 0 else None
        rot = u12 / stock if stock > 0 else None
        if u12 == 0:
            clase = "baja"
        elif cob <= ROT_ALTA_MESES + EPS:
            clase = "alta"
        elif cob <= ROT_MEDIA_MESES + EPS:
            clase = "media"
        else:
            clase = "baja"
        motivos = []
        if smax is not None and stock + transito > smax:
            motivos.append("stock y tránsito superan el nivel máximo")
        if cob is not None and cob > ACUM_MESES + EPS:
            motivos.append(f"stock para más de {ACUM_MESES} meses")
        if u12 == 0 and stock > 0:
            motivos.append("sin ventas en 12 meses y con stock")
        filas.append({"id": rid, "sin_datos": False, "u12": u12, "valor12_bs": u12 * pv, "stock": stock,
                      "transito": transito, "nivel_maximo": smax, "cobertura_meses": cob, "rotacion_anual": rot,
                      "meses_sin_venta": sin, "clase_rot": clase,
                      "baja_rotacion": u12 == 0 or (rot is not None and rot < 1 - EPS),
                      "acumulacion": len(motivos) > 0, "motivos_acumulacion": motivos, "valor_stock_bs": stock * cp})
    total = sum(f["valor12_bs"] for f in filas)
    acum = 0
    for f in sorted(filas, key=lambda f: (-f["valor12_bs"], f["id"])):
        if f["sin_datos"]:
            f["clase_abc"] = None
            continue
        previo = acum / total if total > 0 else 1
        f["clase_abc"] = "A" if previo < ABC_CORTES[0] - EPS else "B" if previo < ABC_CORTES[1] - EPS else "C"
        f["pct_valor"] = f["valor12_bs"] / total * 100 if total > 0 else 0
        acum += f["valor12_bs"]
        f["pct_acumulado"] = acum / total * 100 if total > 0 else 0
    matriz = {a: {"alta": 0, "media": 0, "baja": 0} for a in "ABC"}
    for f in filas:
        if not f["sin_datos"]:
            matriz[f["clase_abc"]][f["clase_rot"]] += 1
    orden = {"A": 0, "B": 1, "C": 2}
    filas.sort(key=lambda f: (f["sin_datos"], orden.get(f["clase_abc"], 0), -f["valor12_bs"], f["id"]))
    con = [f for f in filas if not f["sin_datos"]]
    return {"repuestos": filas, "matriz": matriz, "valor12_total_bs": total,
            "acumulacion": sum(1 for f in con if f["acumulacion"]),
            "baja_rotacion": sum(1 for f in con if f["baja_rotacion"]),
            "valor_acumulado_bs": sum(f["valor_stock_bs"] for f in con if f["acumulacion"]),
            "umbrales": {"rot_alta_meses": ROT_ALTA_MESES, "rot_media_meses": ROT_MEDIA_MESES,
                         "acum_meses": ACUM_MESES, "abc": ABC_CORTES}}
