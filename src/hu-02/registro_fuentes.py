"""HU-02 (SCRUM-12): fuente y fecha de actualización de cada conjunto de datos.

Uso:
    python registro_fuentes.py consultar
    python registro_fuentes.py actualizar --todos
    python registro_fuentes.py actualizar stock_inicial conteos_fisicos

conjuntos.csv dice qué archivo, fuente y columnas tiene cada conjunto. registro_actualizaciones.csv
guarda la última actualización válida de cada uno, y historial_cargas.csv cada intento, bueno o malo.
Si una carga falla, se conserva la fecha válida anterior y queda anotado el fallo.
Las rutas de conjuntos.csv son relativas a la raíz del repositorio. El catálogo vive en data/raw/hu-02 y el
registro y el historial en data/processed/hu-02.
"""
import argparse
import csv
import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
CAMPOS_REGISTRO = ["conjunto", "fuente", "tipo_dato", "responsable", "archivo", "ultima_actualizacion",
                   "fecha_corte_datos", "registros", "sha256", "estado_ultima_carga",
                   "fecha_ultimo_intento", "detalle_fallo"]
CAMPOS_HISTORIAL = ["fecha_intento", "conjunto", "resultado", "registros", "fecha_corte_datos", "detalle"]
FECHA_ISO = re.compile(r"^\d{4}-\d{2}(-\d{2})?([ T]\d{2}:\d{2}(:\d{2})?)?$")


def leer_csv(ruta):
    with Path(ruta).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def escribir_csv(ruta, campos, filas):
    """Escribe a un temporal y lo reemplaza de una vez, para no dejar el registro a medias."""
    ruta = Path(ruta)
    tmp = ruta.with_name(ruta.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    os.replace(tmp, ruta)


def validar(raiz, conjunto):
    """Devuelve (registros, fecha_corte, sha256) si el archivo sirve; si no, lanza ValueError con el motivo."""
    ruta = Path(raiz) / conjunto["archivo"]
    if not ruta.is_file():
        raise ValueError("no se encontró el archivo " + conjunto["archivo"])
    contenido = ruta.read_bytes()
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("el archivo no se puede leer como texto UTF-8")
    lector = csv.DictReader(texto.splitlines())
    columnas = lector.fieldnames or []
    faltan = [c for c in conjunto["columnas_requeridas"].split("|") if c not in columnas]
    if faltan:
        raise ValueError("faltan columnas: " + ", ".join(faltan))
    filas = list(lector)
    if not filas:
        raise ValueError("el archivo no tiene registros")
    fecha_corte = ""
    col = conjunto["columna_fecha"]
    if col:
        # una celda vacía es un dato pendiente; un rango "2025-09 a 2026-08" cuenta por su final
        fechas, malas = [], []
        for i, f in enumerate(filas):
            valor = (f[col] or "").strip()
            if not valor:
                continue
            final = valor.split(" a ")[-1].strip()
            if all(FECHA_ISO.match(p.strip()) for p in valor.split(" a ")):
                fechas.append(final)
            else:
                malas.append(i + 2)
        if malas:
            raise ValueError("fecha con formato inválido en '%s' (fila %d%s)" % (
                col, malas[0], " y %d más" % (len(malas) - 1) if len(malas) > 1 else ""))
        if not fechas:
            raise ValueError("ninguna fila tiene fecha en '%s'" % col)
        fecha_corte = max(fechas)
    return len(filas), fecha_corte, hashlib.sha256(contenido).hexdigest()


def actualizar(nombres, raiz, conjuntos, registro, historial, ahora):
    """Intenta cargar cada conjunto. Devuelve la lista de (conjunto, motivo) de las cargas que fallaron."""
    previo = {f["conjunto"]: f for f in leer_csv(registro)} if Path(registro).is_file() else {}
    nuevos_historial, fallos = [], []
    for nombre in nombres:
        c = conjuntos[nombre]
        fila = dict(previo.get(nombre) or {k: "" for k in CAMPOS_REGISTRO})
        fila.update(conjunto=nombre, fuente=c["fuente"], tipo_dato=c["tipo_dato"],
                    responsable=c["responsable"], archivo=c["archivo"], fecha_ultimo_intento=ahora)
        try:
            registros, fecha_corte, huella = validar(raiz, c)
        except ValueError as e:
            # criterio 3: no se toca ultima_actualizacion ni lo que se cargó bien antes
            fila.update(estado_ultima_carga="FALLO", detalle_fallo=str(e))
            fallos.append((nombre, str(e)))
            nuevos_historial.append(dict(fecha_intento=ahora, conjunto=nombre, resultado="FALLO",
                                         registros="", fecha_corte_datos="", detalle=str(e)))
        else:
            fila.update(ultima_actualizacion=ahora, fecha_corte_datos=fecha_corte, registros=registros,
                        sha256=huella, estado_ultima_carga="OK", detalle_fallo="")
            nuevos_historial.append(dict(fecha_intento=ahora, conjunto=nombre, resultado="OK",
                                         registros=registros, fecha_corte_datos=fecha_corte, detalle=""))
        previo[nombre] = fila
    orden = [n for n in conjuntos if n in previo] + [n for n in previo if n not in conjuntos]
    escribir_csv(registro, CAMPOS_REGISTRO, [previo[n] for n in orden])
    anteriores = leer_csv(historial) if Path(historial).is_file() else []
    escribir_csv(historial, CAMPOS_HISTORIAL, anteriores + nuevos_historial)
    return fallos


def consultar(conjuntos, registro):
    """Arma la tabla de consulta: un renglón por conjunto, con su fuente y su última actualización válida."""
    estado = {f["conjunto"]: f for f in leer_csv(registro)} if Path(registro).is_file() else {}
    renglones = []
    for nombre, c in conjuntos.items():
        e = estado.get(nombre, {})
        if not e.get("ultima_actualizacion"):
            vigente = "SIN CARGA VÁLIDA"
        else:
            vigente = e["ultima_actualizacion"] + (" (datos al %s)" % e["fecha_corte_datos"]
                                                   if e.get("fecha_corte_datos") else "")
        aviso = ""
        if e.get("estado_ultima_carga") == "FALLO":
            aviso = "FALLÓ la carga del %s: %s" % (e["fecha_ultimo_intento"], e["detalle_fallo"])
        renglones.append((nombre, c["fuente"] + " [" + c["tipo_dato"] + "]", vigente, aviso))
    return renglones


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("accion", choices=["consultar", "actualizar"])
    ap.add_argument("conjuntos", nargs="*", help="nombres de conjunto (ver conjuntos.csv)")
    ap.add_argument("--todos", action="store_true", help="actualizar todos los conjuntos")
    ap.add_argument("--raiz", default=RAIZ, help="raíz del repositorio (por defecto, dos carpetas arriba de src/hu-02)")
    ap.add_argument("--catalogo", default=RAIZ / "data" / "raw" / "hu-02" / "conjuntos.csv")
    ap.add_argument("--registro", default=RAIZ / "data" / "processed" / "hu-02" / "registro_actualizaciones.csv")
    ap.add_argument("--historial", default=RAIZ / "data" / "processed" / "hu-02" / "historial_cargas.csv")
    ap.add_argument("--fecha", help="fecha y hora a registrar (por defecto, ahora en UTC)")
    a = ap.parse_args()

    conjuntos = {c["conjunto"]: c for c in leer_csv(a.catalogo)}
    if a.accion == "actualizar":
        nombres = list(conjuntos) if a.todos else a.conjuntos
        if not nombres:
            sys.exit("Indicá uno o más conjuntos, o --todos")
        desconocidos = [n for n in nombres if n not in conjuntos]
        if desconocidos:
            sys.exit("Conjuntos que no están en conjuntos.csv: " + ", ".join(desconocidos))
        if not any((Path(a.raiz) / conjuntos[n]["archivo"]).is_file() for n in conjuntos):
            sys.exit("En %s no está ningún archivo de conjuntos.csv; indicá la raíz del repositorio con --raiz" % a.raiz)
        ahora = a.fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        fallos = actualizar(nombres, a.raiz, conjuntos, a.registro, a.historial, ahora)
        print("cargas correctas=%d fallidas=%d" % (len(nombres) - len(fallos), len(fallos)))
        for nombre, motivo in fallos:
            print("  FALLO %s: %s (se conserva la última fecha válida)" % (nombre, motivo))

    for nombre, fuente, vigente, aviso in consultar(conjuntos, a.registro):
        print("%-24s %-52s %s" % (nombre, vigente, fuente))
        if aviso:
            print("%-24s >> %s" % ("", aviso))
    if a.accion == "actualizar" and fallos:
        sys.exit(1)


if __name__ == "__main__":
    main()
