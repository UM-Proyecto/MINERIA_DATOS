"""Genera docs/GUIA_ESTUDIO_PORTAL.md: la plantilla src/guia/plantilla_guia.md con cada {{clave}} reemplazada por la cifra
que calcula src/guia/hechos.js (el mismo motor y los mismos datos del portal). Ninguna cifra de la guía se escribe a
mano: si la plantilla nombra una clave que no existe, o queda un {{...}} sin reemplazar, el script se detiene.

Uso, desde cualquier carpeta:
    python3 src/guia/generar_guia.py            # escribe docs/GUIA_ESTUDIO_PORTAL.md
    python3 src/guia/generar_guia.py --salida RUTA

Necesita Node (el motor está en JavaScript) y solo la biblioteca estándar de Python.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
PLANTILLA = BASE / "src/guia/plantilla_guia.md"
HECHOS = BASE / "src/guia/hechos.js"
SALIDA = BASE / "docs/GUIA_ESTUDIO_PORTAL.md"
MARCA = re.compile(r"\{\{([a-z0-9_]+)\}\}", re.I)


def hechos():
    r = subprocess.run(["node", str(HECHOS)], capture_output=True, text=True, cwd=BASE)
    if r.returncode != 0:
        raise SystemExit("hechos.js falló:\n" + r.stderr)
    return json.loads(r.stdout)


def armar(h=None, plantilla=None):
    h = hechos() if h is None else h
    texto = PLANTILLA.read_text(encoding="utf-8") if plantilla is None else plantilla
    faltan = sorted({k for k in MARCA.findall(texto) if k not in h})
    if faltan:
        raise SystemExit("La plantilla usa claves que hechos.js no calcula: " + ", ".join(faltan))
    salida = MARCA.sub(lambda m: h[m.group(1)], texto)
    if "{{" in salida or "}}" in salida:
        raise SystemExit("Quedó una marca {{...}} sin reemplazar")
    return salida


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args(argv)
    texto = armar()
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(texto, encoding="utf-8")
    print(f"{a.salida}: {len(texto.splitlines())} líneas, {len(MARCA.findall(PLANTILLA.read_text(encoding='utf-8')))} cifras calculadas")


if __name__ == "__main__":
    main()
