"""HU-30 (SCRUM-6): importa el historial de movimientos de inventario y deja la trazabilidad.

Sin argumentos usa los archivos que están junto a este script, así que corre igual en cualquier máquina.
Escribe en la carpeta de salida: original/ (copia byte a byte), movimientos_importados.csv,
campos_faltantes.csv y registro_carga.json.
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CAMPOS = ["codigo_repuesto", "fecha", "cantidad", "precio"]  # criterio 2 de la HU
ALIAS_PRECIO = "precio_unitario_usd"


def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def leer(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        sys.exit(f"No se encontró el archivo requerido: {ruta}")
    with ruta.open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def relativa(ruta):
    """Ruta relativa a esta carpeta cuando se puede, para que el registro no dependa de la máquina."""
    try:
        return Path(ruta).resolve().relative_to(AQUI).as_posix()
    except ValueError:
        return Path(ruta).name


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--movimientos", default=AQUI / "sintetico" / "movimientos_inventario_sintetico.csv")
    ap.add_argument("--catalogo", default=AQUI / "insumos_equipo" / "catalogo_repuestos.csv")
    ap.add_argument("--salida", default=AQUI / "sintetico" / "hu30")
    a = ap.parse_args()
    mov, out = Path(a.movimientos), Path(a.salida)

    cols, filas = leer(mov)
    _, catalogo = leer(a.catalogo)
    codigos = {c["codigo_repuesto"] for c in catalogo}
    (out / "original").mkdir(parents=True, exist_ok=True)
    copia = out / "original" / mov.name
    shutil.copyfile(mov, copia)
    if sha256(copia) != sha256(mov):
        sys.exit("La copia del original no coincide con la fuente")

    # acepta precio_unitario_usd como alias de precio
    alias = {"precio": ALIAS_PRECIO} if "precio" not in cols and ALIAS_PRECIO in cols else {}
    campos = [alias.get(c, c) for c in CAMPOS]
    faltantes = []
    for campo in campos:
        if campo not in cols:
            faltantes.append({"campo": campo, "id_movimiento": "*", "motivo": "columna ausente en toda la fuente"})
            continue
        for fila in filas:
            if not (fila[campo] or "").strip():
                faltantes.append({"campo": campo, "id_movimiento": fila["id_movimiento"], "motivo": "valor vacío"})
    sin_catalogo = sorted({f["codigo_repuesto"] for f in filas} - codigos)

    extra = [] if "precio" in cols or alias else ["precio"]
    with (out / "movimientos_importados.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols + extra + ["origen_archivo"])
        w.writeheader()
        for fila in filas:
            w.writerow(dict(fila, **{"precio": ""} if extra else {}, origen_archivo=mov.name))
    with (out / "campos_faltantes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["campo", "id_movimiento", "motivo"])
        w.writeheader()
        w.writerows(faltantes)

    fechas = sorted(f["fecha"] for f in filas)
    registro = {
        "fuente": relativa(mov),
        "fecha_extraccion_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registros": len(filas),
        "sha256_original": sha256(mov),
        "copia_original": relativa(copia),
        "periodo": [fechas[0], fechas[-1]] if fechas else [],
        "campos_requeridos": campos,
        "campos_faltantes_total": len(faltantes),
        "campos_faltantes_por_campo": {c: sum(1 for x in faltantes if x["campo"] == c) for c in campos},
        "codigos_sin_catalogo": sin_catalogo,
    }
    (out / "registro_carga.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print("registros=%d periodo=%s faltantes=%d codigos_sin_catalogo=%d" % (
        len(filas), "%s a %s" % (fechas[0], fechas[-1]) if fechas else "-", len(faltantes), len(sin_catalogo)))


if __name__ == "__main__":
    main()
