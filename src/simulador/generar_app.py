"""Arma la app del simulador de compras de MULTIPARTES en un solo archivo HTML (SCRUM-64).

Incrusta en `plantilla_app.html` tres cosas, igual que `src/hu-12/generar_panel.py`:
- `datos_app.json` (lo genera `preparar_datos.py`),
- el motor de cálculo `motor.js` (frente A; se puede indicar otro con --motor),
- el logotipo de MULTIPARTES.

El resultado abre con doble clic, sin servidor y sin conexión (sin conexión la letra pasa a la del sistema).

Uso, desde la raíz del repositorio:
    python3 src/simulador/preparar_datos.py
    python3 src/simulador/generar_app.py [--motor RUTA] [--salida RUTA]

Solo usa la biblioteca estándar. Las rutas salen de la ubicación de este archivo.
"""
import argparse
import base64
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DATOS = BASE / "data/processed/simulador/datos_app.json"
PLANTILLA = BASE / "src/simulador/plantilla_app.html"
MOTOR = BASE / "src/simulador/motor.js"
IMAGENES = BASE / "data/raw/scrum-74/imagenes"  # fotos del catálogo (SCRUM-74), con licencia libre
LOGO = BASE / "src/hu-12/logo_multipartes.jpg"  # logotipo publicado en multipartes.com.bo
SALIDA = BASE / "reports/simulador/MULTIPARTES_Simulador_Compras.html"

MARCAS = ("__LOGO__", "__DATA__", "__MOTOR__")


def seguro_en_script(texto):
    """Evita que un '</script' dentro del texto cierre el bloque antes de tiempo.

    Solo se toca '</script' (sin distinguir mayúsculas): reemplazar todo '</' rompería código como `i</n`.
    """
    return re.sub(r"</(script)", r"<\\/\1", texto, flags=re.IGNORECASE)


def generar(motor, salida):
    if not motor.is_file():
        raise SystemExit(f"No existe el motor de cálculo: {motor}\n"
                         "El motor es src/simulador/motor.js (ver docs/simulador/MOTOR.md); con --motor se puede indicar otra ruta.")
    if not DATOS.is_file():
        raise SystemExit(f"Falta {DATOS.relative_to(BASE)}: corra antes python3 src/simulador/preparar_datos.py")
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    for marca in MARCAS:
        if plantilla.count(marca) != 1:
            raise SystemExit(f"La plantilla debe tener una única marca {marca}")
    codigo = motor.read_text(encoding="utf-8")
    if "module.exports = Motor" not in codigo:
        raise SystemExit(f"{motor} no parece el motor del contrato (falta «module.exports = Motor»)")
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    # Las fotos del catálogo van dentro del HTML para que abra sin conexión. Si falta una, se corta aquí.
    fotos = {f["imagen"] for f in datos["catalogo"]["repuestos"]}
    datos["imagenes"] = {}
    for nombre in sorted(fotos):
        ruta = IMAGENES / nombre
        if not ruta.is_file():
            raise SystemExit(f"Falta la foto del catálogo {ruta.relative_to(BASE)}")
        datos["imagenes"][nombre] = "data:image/jpeg;base64," + base64.b64encode(ruta.read_bytes()).decode()
    texto = seguro_en_script(json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    logo = "data:image/jpeg;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    # El motor va al final: si se reemplazara antes, un '__DATA__' dentro de su código se tocaría.
    html = plantilla.replace("__LOGO__", logo).replace("__DATA__", texto).replace("__MOTOR__", seguro_en_script(codigo))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    return datos, html


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--motor", type=Path, default=MOTOR, help="motor.js a incrustar (por defecto src/simulador/motor.js)")
    ap.add_argument("--salida", type=Path, default=SALIDA, help="HTML a escribir")
    a = ap.parse_args(argv)
    motor = a.motor if a.motor.is_absolute() else (Path.cwd() / a.motor)
    datos, _ = generar(motor.resolve(), a.salida.resolve())
    print(f"{a.salida}: {len(datos['repuestos'])} repuestos, motor {motor.name}, {a.salida.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
