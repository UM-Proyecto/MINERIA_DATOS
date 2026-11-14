"""Arma el servidor del portal (SCRUM-73, 77 y 78) en un solo archivo _worker.js para Cloudflare Pages.

Junta, en este orden:
  1. el motor del simulador (src/simulador/motor.js), el mismo que usa la app;
  2. const DATOS = datos_app.json y const APP_HTML = la app ya generada (reports/simulador/...html);
  3. src/portal/worker_api.js, con las rutas de la API.
Así el servidor recalcula cada cotización con el mismo motor y los mismos datos que ve el cliente.

Uso, desde la raíz del repositorio (después de preparar_datos.py y generar_app.py):
    python3 src/portal/armar_portal.py [--salida build/portal]

La publicación en Cloudflare está en docs/portal/LEEME.md. Solo usa la biblioteca estándar.
"""
import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
MOTOR = BASE / "src/simulador/motor.js"
API = BASE / "src/portal/worker_api.js"
DATOS = BASE / "data/processed/simulador/datos_app.json"
APP = BASE / "reports/simulador/MULTIPARTES_Simulador_Compras.html"
SALIDA = BASE / "build/portal"


def armar():
    for f in (MOTOR, API, DATOS, APP):
        if not f.is_file():
            raise SystemExit(f"Falta {f.relative_to(BASE)}")
    motor = MOTOR.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    html = APP.read_text(encoding="utf-8")
    if "module.exports = Motor" not in motor or "export default" not in api or "</head>" not in html:
        raise SystemExit("Alguna de las piezas no tiene la forma esperada (motor, API o app).")
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    return "\n".join([
        "// Generado por src/portal/armar_portal.py. No editar a mano.",
        motor,
        "const DATOS = " + json.dumps(datos, ensure_ascii=False, separators=(",", ":")) + ";",
        "const APP_HTML = " + json.dumps(html, ensure_ascii=False) + ";",
        api,
    ])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    destino = a.salida / "_worker.js"
    destino.write_text(armar(), encoding="utf-8")
    print(f"{destino}: {destino.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
