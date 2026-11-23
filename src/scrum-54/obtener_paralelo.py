#!/usr/bin/env python3
"""Dólar paralelo diario (referencia privada): lee una fuente pública y agrega el valor del día a la serie.

El dólar paralelo NO entra en ningún cálculo del simulador: se muestra solo como referencia junto al oficial del BCB
(SCRUM-54 y SCRUM-71). Antes era un punto fijo del 23-10-2026; ahora se lee cada día con la misma regla que el
oficial: si ninguna fuente responde, el CSV no se toca y la app sigue con el último valor, diciendo de qué fecha es.

Fuentes, en este orden (las dos públicas y sin credenciales, alcanzables desde GitHub Actions):
  1. dolarbolivia.net: el valor «paralelo» de venta que la página publica en sus datos estructurados (JSON-LD),
     promedio de varias plataformas P2P.
  2. Binance P2P, USDT/BOB: promedio de los 10 primeros avisos de quien vende dólares (lo que paga quien compra),
     es decir, el precio de venta.

Salida: data/processed/scrum-54/dolar_paralelo_diario.csv, una fila por día (fecha de Bolivia), con fuente, momento
de lectura y marca PRIVADO. Si el día ya tiene fila, se reemplaza por la lectura más nueva.

Uso:
    python3 src/scrum-54/obtener_paralelo.py
    python3 src/scrum-54/obtener_paralelo.py --url-principal URL --url-respaldo URL   # para probar fuentes caídas
Sale con 0 si guardó un valor y con 1 si ninguna fuente respondió (el CSV queda igual, byte a byte).
Solo usa la biblioteca estándar.
"""
import argparse
import csv
import io
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data/processed/scrum-54/dolar_paralelo_diario.csv"
URL_PRINCIPAL = "https://dolarbolivia.net/"
URL_RESPALDO = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
COLUMNAS = ["fecha", "paralelo_bs_por_usd", "fuente", "fecha_lectura", "marca"]
MINIMO, MAXIMO = 6.0, 30.0   # fuera de este rango la lectura se descarta (página cambiada o dato roto)
BOLIVIA = timezone(timedelta(hours=-4))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class SinDato(Exception):
    """La fuente no respondió o no trajo un valor creíble."""


def pedir(url, cuerpo=None, timeout=20):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, headers={"User-Agent": UA, **({"Content-Type": "application/json"} if datos else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def creible(v):
    if not (MINIMO <= v <= MAXIMO):
        raise SinDato(f"valor fuera de rango: {v}")
    return round(v, 2)


def de_dolarbolivia(texto):
    """Busca en el JSON-LD la especificación «rate-paralelo» y devuelve su precio."""
    for bloque in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', texto, re.S):
        try:
            d = json.loads(bloque)
        except ValueError:
            continue
        for nodo in d.get("@graph", [d]) if isinstance(d, dict) else []:
            if isinstance(nodo, dict) and "paralelo" in str(nodo.get("@id", "")).lower():
                return creible(float(nodo["currentExchangeRate"]["price"]))
    raise SinDato("la página no trae el valor paralelo en su JSON-LD")


def de_binance(texto):
    """Promedio de los precios de los avisos devueltos (venta de USDT por bolivianos)."""
    try:
        precios = [float(a["adv"]["price"]) for a in json.loads(texto)["data"]]
    except (ValueError, KeyError, TypeError) as e:
        raise SinDato(f"respuesta de Binance inesperada: {e}")
    if len(precios) < 3:
        raise SinDato(f"Binance devolvió {len(precios)} avisos")
    return creible(sum(precios) / len(precios))


def leer_fuentes(url_principal=URL_PRINCIPAL, url_respaldo=URL_RESPALDO, pedir=pedir):
    """Devuelve (valor, fuente) de la primera fuente que responda. `pedir` se reemplaza en las pruebas."""
    errores = []
    try:
        return de_dolarbolivia(pedir(url_principal)), "dolarbolivia.net, promedio de venta en plataformas P2P"
    except Exception as e:   # red caída, página cambiada o valor raro: se prueba la siguiente
        errores.append(f"dolarbolivia.net: {e}")
    try:
        cuerpo = {"asset": "USDT", "fiat": "BOB", "tradeType": "BUY", "page": 1, "rows": 10, "payTypes": [], "publisherType": None}
        return de_binance(pedir(url_respaldo, cuerpo)), "Binance P2P USDT/BOB, promedio de venta de los 10 primeros avisos"
    except Exception as e:
        errores.append(f"Binance P2P: {e}")
    raise SinDato("; ".join(errores))


def actualizar(valor, fuente, ahora, salida=SALIDA):
    """Agrega o reemplaza la fila del día y reescribe el CSV ordenado por fecha."""
    filas = []
    if salida.exists():
        with open(salida, encoding="utf-8", newline="") as f:
            filas = list(csv.DictReader(f))
    hoy = ahora.astimezone(BOLIVIA).date().isoformat()
    filas = [r for r in filas if r["fecha"] != hoy]
    filas.append({"fecha": hoy, "paralelo_bs_por_usd": f"{valor:.2f}", "fuente": fuente,
                  "fecha_lectura": ahora.astimezone(BOLIVIA).strftime("%Y-%m-%d %H:%M"), "marca": "PRIVADO"})
    filas.sort(key=lambda r: r["fecha"])
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNAS, lineterminator="\n")
    w.writeheader(); w.writerows(filas)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(buf.getvalue(), encoding="utf-8")
    return next(r for r in filas if r["fecha"] == hoy)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url-principal", default=URL_PRINCIPAL)
    ap.add_argument("--url-respaldo", default=URL_RESPALDO)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args(argv)
    try:
        valor, fuente = leer_fuentes(a.url_principal, a.url_respaldo)
    except SinDato as e:
        print(f"Ninguna fuente respondió; el CSV queda como estaba. {e}", file=sys.stderr)
        return 1
    fila = actualizar(valor, fuente, datetime.now(timezone.utc), a.salida)
    print(f"{fila['fecha']}: {fila['paralelo_bs_por_usd']} Bs ({fila['fuente']}) -> {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
