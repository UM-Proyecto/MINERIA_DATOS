"""SCRUM-80: probabilidad de que cada repuesto se venda el mes que viene (clasificación con regresión logística).

La pregunta es de sí o no, como la de la materia sobre si un videojuego iba a ser exitoso: ¿el repuesto se vende
(al menos una unidad) el mes siguiente? El modelo responde con una probabilidad entre 0 y 1.

Datos: las ventas mensuales REALES de carparts de los 30 repuestos (SCRUM-55), de ago-2022 a oct-2026. Los meses
están re-fechados, así que el patrón es el de carparts y no el de Santa Cruz.

Cada caso es un repuesto en un mes. Las variables salen solo de los meses ANTERIORES al mes que se predice, para no
mirar el futuro:
- vendio_mes_anterior: 1 si vendió algo el mes anterior;
- unidades_3m: unidades vendidas en los 3 meses anteriores;
- frecuencia_12m: en qué parte de los 12 meses anteriores vendió (0 a 1);
- vendio_hace_12m: 1 si vendió el mismo mes del año anterior (temporada);
- meses_sin_venta: meses seguidos sin vender hasta el mes anterior (tope 12).

Corte: con 50 % la clase es «se vende». Como solo se vende en uno de cada cuatro meses, ese corte deja pasar muchas
ventas; por eso se calcula también el corte que equilibra aciertos en las dos clases (índice de Youden), elegido con
los datos de entrenamiento. Cada repuesto queda en un nivel: alta (desde 50 %), media (desde el corte de Youden) o
baja.

Validación temporal: se entrena con los meses hasta oct-2025 y se prueba con los 12 meses siguientes, que el
modelo no vio. Se compara con una regla simple: «se vende si se vendió el mes anterior». Después se vuelve a
entrenar con todos los meses y se predice nov-2026.

El ajuste es por Newton-Raphson con una penalización L2 pequeña (LAMBDA), sobre variables estandarizadas con la
media y el desvío del entrenamiento. Es determinista: no hay sorteo.

Uso, desde cualquier carpeta:
    python3 src/scrum-80/predecir_venta.py

Solo usa la biblioteca estándar.
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
VENTAS = BASE / "data/processed/scrum-55/ventas_mensuales.csv"
SALIDA = BASE / "data/processed/scrum-80/prediccion.json"

VARIABLES = ["vendio_mes_anterior", "unidades_3m", "frecuencia_12m", "vendio_hace_12m", "meses_sin_venta"]
NOMBRES = {
    "vendio_mes_anterior": "Vendió el mes anterior",
    "unidades_3m": "Unidades de los últimos 3 meses",
    "frecuencia_12m": "Meses con venta en los últimos 12",
    "vendio_hace_12m": "Vendió el mismo mes del año pasado",
    "meses_sin_venta": "Meses seguidos sin vender",
}
HISTORIA = 12            # meses de historia que necesita cada caso
ULTIMO_ENTRENO = "2025-10"
CORTE = 0.5
LAMBDA = 1.0
ITERACIONES = 50


def leer_series():
    series = defaultdict(dict)
    with open(VENTAS, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            series[fila["repuesto_id"]][fila["mes"]] = int(fila["unidades"])
    meses = sorted({m for s in series.values() for m in s})
    for rid, s in series.items():
        if sorted(s) != meses:
            raise SystemExit(f"{rid} no tiene los {len(meses)} meses: el modelo necesita la serie completa")
    return meses, {rid: [s[m] for m in meses] for rid, s in sorted(series.items())}


def siguiente_mes(mes):
    a, m = int(mes[:4]), int(mes[5:7])
    return f"{a + (m == 12)}-{m % 12 + 1:02d}"


def variables(serie, t):
    """Variables para predecir el mes t usando solo serie[:t]."""
    prev = serie[:t]
    sin = 0
    for u in reversed(prev):
        if u > 0:
            break
        sin += 1
    return [
        1.0 if prev[-1] > 0 else 0.0,
        float(sum(prev[-3:])),
        sum(1 for u in prev[-12:] if u > 0) / 12,
        1.0 if prev[-12] > 0 else 0.0,
        float(min(sin, 12)),
    ]


def casos(meses, series):
    filas = []
    for rid, s in series.items():
        for t in range(HISTORIA, len(meses)):
            filas.append({"rep": rid, "mes": meses[t], "x": variables(s, t), "y": 1 if s[t] > 0 else 0})
    return filas


def escala(X):
    k = len(X[0])
    medias = [sum(x[j] for x in X) / len(X) for j in range(k)]
    desvios = []
    for j in range(k):
        v = sum((x[j] - medias[j]) ** 2 for x in X) / len(X)
        desvios.append(math.sqrt(v) if v > 0 else 1.0)
    return medias, desvios


def estandarizar(x, medias, desvios):
    return [1.0] + [(x[j] - medias[j]) / desvios[j] for j in range(len(x))]


def sigmoide(z):
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def resolver(A, b):
    """Gauss con pivoteo parcial."""
    n = len(b)
    M = [fila[:] + [b[i]] for i, fila in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
    return x


def ajustar(Z, y):
    """Regresión logística con L2 (sin penalizar la constante), por Newton-Raphson."""
    k = len(Z[0])
    w = [0.0] * k
    for _ in range(ITERACIONES):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for z, yi in zip(Z, y):
            p = sigmoide(sum(a * b for a, b in zip(w, z)))
            for i in range(k):
                g[i] += (p - yi) * z[i]
                for j in range(k):
                    H[i][j] += p * (1 - p) * z[i] * z[j]
        for i in range(1, k):
            g[i] += LAMBDA * w[i]
            H[i][i] += LAMBDA
        paso = resolver(H, g)
        w = [a - b for a, b in zip(w, paso)]
        if max(abs(d) for d in paso) < 1e-10:
            break
    return w


def auc(puntajes, y):
    """Probabilidad de que un caso positivo tenga más puntaje que uno negativo (empates cuentan medio)."""
    pos = [p for p, yi in zip(puntajes, y) if yi == 1]
    neg = [p for p, yi in zip(puntajes, y) if yi == 0]
    if not pos or not neg:
        return None
    gana = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg)
    return gana / (len(pos) * len(neg))


def metricas(pred, y, puntajes=None):
    vp = sum(1 for p, yi in zip(pred, y) if p == 1 and yi == 1)
    fp = sum(1 for p, yi in zip(pred, y) if p == 1 and yi == 0)
    fn = sum(1 for p, yi in zip(pred, y) if p == 0 and yi == 1)
    vn = sum(1 for p, yi in zip(pred, y) if p == 0 and yi == 0)
    n = len(y)
    m = {
        "n": n, "vp": vp, "fp": fp, "fn": fn, "vn": vn,
        "exactitud": (vp + vn) / n,
        "precision": vp / (vp + fp) if vp + fp else None,
        "sensibilidad": vp / (vp + fn) if vp + fn else None,
        "especificidad": vn / (vn + fp) if vn + fp else None,
    }
    if puntajes is not None:
        m["auc"] = auc(puntajes, y)
        m["brier"] = sum((p - yi) ** 2 for p, yi in zip(puntajes, y)) / n
    return m


def calibracion(probs, y):
    tramos = []
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        idx = [k for k, p in enumerate(probs) if lo <= p < hi or (i == 9 and p == 1.0)]
        if idx:
            tramos.append({"desde": lo, "hasta": hi, "n": len(idx),
                           "prob_media": sum(probs[k] for k in idx) / len(idx),
                           "vendidos": sum(y[k] for k in idx) / len(idx)})
    return tramos


def corte_youden(probs, y):
    """Corte que maximiza sensibilidad + especificidad − 1 (índice de Youden), buscado en pasos de 0,01.
    Se elige con los datos de ENTRENAMIENTO; la prueba solo lo mide."""
    mejor = None
    for i in range(5, 96):
        c = i / 100
        m = metricas([1 if p >= c else 0 for p in probs], y)
        j = (m["sensibilidad"] or 0) + (m["especificidad"] or 0) - 1
        if mejor is None or j > mejor[0] + 1e-12:
            mejor = (j, c)
    return mejor[1]


def r(x, d=4):
    return None if x is None else round(x, d)


def redondear_dict(m):
    return {k: (r(v) if isinstance(v, float) else v) for k, v in m.items()}


def modelo():
    meses, series = leer_series()
    filas = casos(meses, series)
    entreno = [f for f in filas if f["mes"] <= ULTIMO_ENTRENO]
    prueba = [f for f in filas if f["mes"] > ULTIMO_ENTRENO]

    medias, desvios = escala([f["x"] for f in entreno])
    w = ajustar([estandarizar(f["x"], medias, desvios) for f in entreno], [f["y"] for f in entreno])
    prob_ent = [sigmoide(sum(a * b for a, b in zip(w, estandarizar(f["x"], medias, desvios)))) for f in entreno]
    corte_bajo = corte_youden(prob_ent, [f["y"] for f in entreno])
    probs = [sigmoide(sum(a * b for a, b in zip(w, estandarizar(f["x"], medias, desvios)))) for f in prueba]
    y = [f["y"] for f in prueba]
    pred = [1 if p >= CORTE else 0 for p in probs]
    base_rate = sum(f["y"] for f in entreno) / len(entreno)
    m_modelo = metricas(pred, y, probs)
    m_youden = metricas([1 if p >= corte_bajo else 0 for p in probs], y)
    m_regla = metricas([int(f["x"][0]) for f in prueba], y, [f["x"][0] for f in prueba])
    brier_base = sum((base_rate - yi) ** 2 for yi in y) / len(y)

    # Modelo final: todos los meses; predice el mes siguiente al último dato.
    medias_f, desvios_f = escala([f["x"] for f in filas])
    w_f = ajustar([estandarizar(f["x"], medias_f, desvios_f) for f in filas], [f["y"] for f in filas])
    mes_pred = siguiente_mes(meses[-1])
    predicciones = []
    for rid, s in series.items():
        x = variables(s, len(s))
        p = sigmoide(sum(a * b for a, b in zip(w_f, estandarizar(x, medias_f, desvios_f))))
        nivel = "alta" if p >= CORTE else "media" if p >= corte_bajo else "baja"
        predicciones.append({"repuesto_id": rid, "probabilidad": r(p), "se_vende": p >= CORTE, "nivel": nivel,
                             "variables": dict(zip(VARIABLES, [r(v) for v in x]))})
    predicciones.sort(key=lambda q: (-q["probabilidad"], q["repuesto_id"]))

    return {
        "tecnica": "Regresión logística (clasificación supervisada binaria)",
        "pregunta": "¿El repuesto vende al menos una unidad el mes siguiente?",
        "variables": [{"clave": v, "nombre": NOMBRES[v]} for v in VARIABLES],
        "corte": CORTE, "corte_youden": corte_bajo, "lambda_l2": LAMBDA,
        "validacion": {
            "tipo": "temporal",
            "entreno": {"desde": entreno[0]["mes"] if entreno else None, "hasta": ULTIMO_ENTRENO, "casos": len(entreno),
                        "positivos": sum(f["y"] for f in entreno)},
            "prueba": {"desde": min(f["mes"] for f in prueba), "hasta": max(f["mes"] for f in prueba),
                       "casos": len(prueba), "positivos": sum(y)},
            "modelo": redondear_dict(m_modelo),
            "modelo_corte_youden": redondear_dict(m_youden),
            "regla_mes_anterior": redondear_dict(m_regla),
            "brier_tasa_base": r(brier_base), "tasa_base_entreno": r(base_rate),
            "calibracion": [redondear_dict(t) for t in calibracion(probs, y)],
            "casos_prueba": [[f["rep"], f["mes"], r(p), f["y"]] for f, p in zip(prueba, probs)],
        },
        "coeficientes": {
            "constante": r(w_f[0]),
            "estandarizados": [{"clave": v, "coef": r(c)} for v, c in zip(VARIABLES, w_f[1:])],
            "medias": [r(v) for v in medias_f], "desvios": [r(v) for v in desvios_f],
        },
        "mes_predicho": mes_pred,
        "ultimo_mes_con_dato": meses[-1],
        "predicciones": predicciones,
        "origen_dato": "Ventas REALES de carparts (Hyndman et al., 2008), meses re-fechados (SCRUM-55)",
    }


def main():
    res = modelo()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    v = res["validacion"]
    m, b = v["modelo"], v["regla_mes_anterior"]
    print(f"{SALIDA.relative_to(BASE)}: entreno {v['entreno']['casos']} casos, prueba {v['prueba']['casos']}")
    print(f"  modelo: exactitud {m['exactitud']}, AUC {m['auc']}, Brier {m['brier']}, "
          f"precisión {m['precision']}, sensibilidad {m['sensibilidad']}")
    y_ = v["modelo_corte_youden"]
    print(f"  corte Youden {res['corte_youden']}: exactitud {y_['exactitud']}, sensibilidad {y_['sensibilidad']}, precisión {y_['precision']}")
    print(f"  regla «vendió el mes anterior»: exactitud {b['exactitud']}, AUC {b['auc']}")
    print(f"  Brier con la tasa base ({v['tasa_base_entreno']}): {v['brier_tasa_base']}")
    print(f"  {res['mes_predicho']}: {sum(p['se_vende'] for p in res['predicciones'])} de 30 se venden (corte {CORTE})")


if __name__ == "__main__":
    main()
