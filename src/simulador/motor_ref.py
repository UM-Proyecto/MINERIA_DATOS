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

Z_CLASE = {"A": 1.65, "B": 1.28, "C": 0.84}
ALFA_SBA = 0.1
ALTERNATIVAS = ["A", "B", "C", "D"]
ORDEN_CLASE = {"A": 0, "B": 1, "C": 2}
ETIQUETAS = ["Pedir ya", "Vigilar", "Cubierto"]
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

def alertas(datos, tc):
    filas = []
    for rep in datos["repuestos"]:
        prov = buscar_proveedor(datos, rep["proveedor_id"])
        pr = pronostico(datos["ventas"][rep["repuesto_id"]], rep["tipo_demanda"])
        tasa = pr["unidades_mes"] / 30
        stock, camino = num(rep["stock_al_2026_11_10"]), num(rep["en_transito_al_2026_11_10"])
        s, S = num(rep["punto_pedido_s"]), num(rep["nivel_maximo_S"])
        plazo = num(prov["plazo_normal_dias"])
        pos = stock + camino
        margen = (pos - s) / tasa if tasa > 0 else None
        est = 0 if pos <= s else (1 if margen is not None and margen < plazo else 2)
        cantidad = max(math.floor(S - pos + 0.5), 0)
        if est < 2:
            cantidad = max(cantidad, 1)
        cp = costo_puesto(rep, prov, tc)
        filas.append({
            "id": rep["repuesto_id"], "est": est, "etiqueta": ETIQUETAS[est], "stock": stock, "en_camino": camino,
            "punto_pedido": s, "nivel_maximo": S, "plazo": plazo,
            "margen_dias": None if margen is None else math.floor(margen + EPS),
            "cantidad_sugerida": cantidad, "costo_bs": redondear(cantidad * cp["total_bs"], 2),
            "clase": rep["clase_abc"], "tipo_demanda": rep["tipo_demanda"], "proveedor_id": prov["proveedor_id"],
            "venta_mes": pr["unidades_mes"], "_m": margen})
    filas.sort(key=lambda x: (x["est"], x["_m"] is None, x["_m"] if x["_m"] is not None else 0, x["id"]))
    for x in filas:
        del x["_m"]
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
