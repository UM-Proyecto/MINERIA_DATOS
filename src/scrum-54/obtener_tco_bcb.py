#!/usr/bin/env python3
"""SCRUM-54: obtiene el tipo de cambio oficial (TCO) diario del BCB y regenera el CSV.

Lee la página pública del Banco Central de Bolivia, guarda la captura cruda con su
fecha y su sha256, y reescribe data/processed/scrum-54/tco_bcb_diario.csv.
Solo usa la biblioteca estándar.

Uso:
    python3 src/scrum-54/obtener_tco_bcb.py                     # descarga la página de hoy
    python3 src/scrum-54/obtener_tco_bcb.py --desde-archivo RUTA  # sin red, desde una captura
    python3 src/scrum-54/obtener_tco_bcb.py --inseguro           # solo si falla el certificado SSL
"""
import argparse
import csv
import hashlib
import html
import re
import ssl
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
URL = "https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php"
RAW = RAIZ / "data/raw/scrum-54"
SALIDA = RAIZ / "data/processed/scrum-54/tco_bcb_diario.csv"
FUENTE = ("BCB, tabla Tipo de cambio oficial diario "
          "(bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php)")
COLUMNAS = ["fecha", "tco_bs_por_usd", "fuente", "fecha_lectura"]
MINIMO, MAXIMO = 5.0, 20.0
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
MESES = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"], 1)}
FECHA_ES = r"(\d{1,2}) de ([a-záéíóú]+) de (\d{4})"


class ErrorTCO(Exception):
    """La página no cumple lo esperado; no se escribe nada."""


def a_texto(crudo):
    """Quita <style> y <script>, luego las etiquetas, y devuelve líneas de texto."""
    t = re.sub(r"(?is)<(style|script)\b.*?</\1\s*>", " ", crudo)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t).replace("\xa0", " ")
    return [re.sub(r"\s+", " ", l).strip() for l in t.split("\n") if l.strip()]


def fecha_es(texto):
    m = re.search(FECHA_ES, texto, re.I)
    if not m or m.group(2).lower() not in MESES:
        raise ErrorTCO("No se pudo leer la fecha en: %r" % texto)
    return date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))


def numero(texto):
    return float(texto.replace(".", "").replace(",", "."))


def parsear(crudo):
    """Devuelve (filas [(date, float)], vigencia date, ultima_cotizacion float)."""
    lineas = a_texto(crudo)
    # Encabezado: «Última cotización» + «VIGENCIA: …» y «Bs 11,75/$us».
    vig = next((l for l in lineas if l.upper().startswith("VIGENCIA:")), None)
    if vig is None:
        raise ErrorTCO("No se encontró el encabezado «VIGENCIA: …» en la página.")
    vigencia = fecha_es(vig)
    ultima = None
    for l in lineas:
        m = re.search(r"Bs\s*([\d.,]+)\s*/\s*\$us", l)
        if m:
            ultima = numero(m.group(1))
            break
    # Tabla diaria: línea con fecha larga seguida de una línea con el valor.
    try:
        inicio = next(i for i, l in enumerate(lineas)
                      if l.upper().startswith("TIPO DE CAMBIO OFICIAL - DIARIO"))
    except StopIteration:
        raise ErrorTCO("No se encontró la tabla «TIPO DE CAMBIO OFICIAL - DIARIO».")
    filas = []
    i = inicio + 1
    while i < len(lineas) - 1:
        if re.fullmatch(r"[a-záéíóú]+ " + FECHA_ES, lineas[i], re.I) and \
                re.fullmatch(r"[\d.,]+", lineas[i + 1]):
            filas.append((fecha_es(lineas[i]), numero(lineas[i + 1])))
            i += 2
        else:
            i += 1
    if not filas:
        raise ErrorTCO("La tabla diaria no tiene filas.")
    return filas, vigencia, ultima


def validar(filas, vigencia, ultima):
    fechas = [f for f, _ in filas]
    if len(set(fechas)) != len(fechas):
        raise ErrorTCO("Hay fechas repetidas en la tabla.")
    if fechas != sorted(fechas):
        raise ErrorTCO("Las fechas de la tabla no están en orden creciente.")
    esperadas = (fechas[-1] - fechas[0]).days + 1
    if len(fechas) != esperadas:
        d = fechas[0]
        faltan = []
        presentes = set(fechas)
        while d <= fechas[-1]:
            if d not in presentes:
                faltan.append(d.isoformat())
            d += timedelta(days=1)
        raise ErrorTCO("Faltan días entre %s y %s: %s" % (
            fechas[0], fechas[-1], ", ".join(faltan[:10])))
    for f, v in filas:
        if not MINIMO <= v <= MAXIMO:
            raise ErrorTCO("Valor fuera de rango (%s a %s) el %s: %s" % (
                MINIMO, MAXIMO, f, v))
    if vigencia != fechas[-1]:
        raise ErrorTCO("La vigencia del encabezado (%s) no coincide con la última "
                       "fila (%s)." % (vigencia, fechas[-1]))
    if ultima is not None and abs(ultima - filas[-1][1]) > 1e-9:
        raise ErrorTCO("La última cotización del encabezado (%s) no coincide con la "
                       "última fila (%s)." % (ultima, filas[-1][1]))


def descargar(inseguro=False):
    ctx = None
    if inseguro:
        print("AVISO: --inseguro desactiva la verificación del certificado SSL.",
              file=sys.stderr)
        ctx = ssl._create_unverified_context()
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            return r.read()
    except ssl.SSLError as e:
        raise ErrorTCO("Falló el certificado SSL (%s). Use --inseguro solo si "
                       "acepta el riesgo." % e)
    except OSError as e:
        raise ErrorTCO("No se pudo descargar %s: %s" % (URL, e))


def registrar_sha(ruta):
    """Guarda sha256 de la captura en SHA256SUMS.txt (una línea por archivo)."""
    h = hashlib.sha256(ruta.read_bytes()).hexdigest()
    suma = ruta.parent / "SHA256SUMS.txt"
    lineas = []
    if suma.exists():
        lineas = [l for l in suma.read_text(encoding="utf-8").splitlines()
                  if l.strip() and not l.endswith("  " + ruta.name)]
    lineas.append("%s  %s" % (h, ruta.name))
    suma.write_text("\n".join(sorted(lineas, key=lambda l: l.split("  ")[1])) + "\n",
                    encoding="utf-8")
    return h


def escribir_csv(filas, salida, fecha_lectura):
    previas = {}
    if salida.exists():
        with salida.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                previas[r["fecha"]] = (r["tco_bs_por_usd"], r["fecha_lectura"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(COLUMNAS)
        for fch, v in filas:
            k = fch.isoformat()
            texto = "%.2f" % v
            lectura = fecha_lectura
            # Si el día ya estaba con el mismo valor, se conserva su fecha de lectura.
            if k in previas and abs(float(previas[k][0]) - v) < 1e-9:
                lectura = previas[k][1]
            w.writerow([k, texto, FUENTE, lectura])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--desde-archivo", help="captura HTML local; no usa la red")
    p.add_argument("--inseguro", action="store_true",
                   help="no verifica el certificado SSL (solo si falla)")
    p.add_argument("--salida", default=str(SALIDA), help="CSV de salida")
    p.add_argument("--raw", default=str(RAW), help="carpeta de capturas")
    a = p.parse_args(argv)
    try:
        if a.desde_archivo:
            ruta = Path(a.desde_archivo)
            crudo = ruta.read_bytes()
            m = re.search(r"(\d{4}-\d{2}-\d{2})", ruta.name)
            lectura = m.group(1) if m else date.today().isoformat()
        else:
            crudo = descargar(a.inseguro)
            lectura = date.today().isoformat()
            Path(a.raw).mkdir(parents=True, exist_ok=True)
            ruta = Path(a.raw) / ("tco_bcb_%s.html" % lectura)
            ruta.write_bytes(crudo)
            print("Captura: %s sha256=%s" % (ruta, registrar_sha(ruta)))
        filas, vigencia, ultima = parsear(crudo.decode("utf-8", errors="replace"))
        validar(filas, vigencia, ultima)
    except ErrorTCO as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    escribir_csv(filas, Path(a.salida), lectura)
    print("OK: %d filas, %s a %s, último valor %.2f -> %s" % (
        len(filas), filas[0][0], filas[-1][0], filas[-1][1], a.salida))
    return 0


if __name__ == "__main__":
    sys.exit(main())
