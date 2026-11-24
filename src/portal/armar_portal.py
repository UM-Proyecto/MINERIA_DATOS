"""Arma el servidor del portal (SCRUM-73, 77 y 78) en un solo archivo _worker.js para Cloudflare Pages.

Junta, en este orden:
  1. el motor del simulador (src/simulador/motor.js), el mismo que usa la app;
  2. DATOS_INCLUIDOS (datos_app.json), APP_INCLUIDA (la app de la empresa) y TIENDA_INCLUIDA (la tienda pública);
  3. src/portal/worker_api.js, con las rutas de la API.
Así el servidor recalcula cada cotización con el mismo motor y los mismos datos que ve el cliente.

Con --liviano se omite el paso 2 (unos 50 KB en vez de 850): el servidor lee los datos y la app del repositorio en
GitHub, en la rama o commit de la variable FUENTE_REF. Es la versión publicada en Cloudflare.

Uso, desde la raíz del repositorio (después de preparar_datos.py y generar_app.py):
    python3 src/portal/armar_portal.py [--salida build/portal] [--liviano]

La publicación en Cloudflare está en docs/portal/LEEME.md. Solo usa la biblioteca estándar.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
MOTOR = BASE / "src/simulador/motor.js"
API = BASE / "src/portal/worker_api.js"
DATOS = BASE / "data/processed/simulador/datos_app.json"
APP = BASE / "reports/simulador/MULTIPARTES_Simulador_Compras.html"
TIENDA = BASE / "reports/tienda/MULTIPARTES_Tienda.html"
SALIDA = BASE / "build/portal"
# Catálogos PDF de MULTIPARTES servidos por el propio portal: el sitio original tiene el certificado vencido desde el
# 5-10-2026 y el navegador mostraba una advertencia de seguridad (auditoría del 24-11-2026, error E3).
CATALOGOS = BASE / "reports/tienda/catalogos"


def armar(liviano=False):
    for f in (MOTOR, API, DATOS, APP, TIENDA):
        if not f.is_file():
            raise SystemExit(f"Falta {f.relative_to(BASE)}")
    motor = MOTOR.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    html = APP.read_text(encoding="utf-8")
    tienda = TIENDA.read_text(encoding="utf-8")
    if "module.exports = Motor" not in motor or "export default" not in api or "</head>" not in html:
        raise SystemExit("Alguna de las piezas no tiene la forma esperada (motor, API o app).")
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    partes = ["// Generado por src/portal/armar_portal.py. No editar a mano.", motor]
    if not liviano:
        partes += ["const DATOS_INCLUIDOS = " + json.dumps(datos, ensure_ascii=False, separators=(",", ":")) + ";",
                   "const APP_INCLUIDA = " + json.dumps(html, ensure_ascii=False) + ";",
                   "const TIENDA_INCLUIDA = " + json.dumps(tienda, ensure_ascii=False) + ";"]
    return "\n".join(partes + [api])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--liviano", action="store_true", help="sin datos ni app: el servidor los lee de GitHub")
    a = ap.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    destino = a.salida / "_worker.js"
    destino.write_text(armar(a.liviano), encoding="utf-8")
    print(f"{destino}: {destino.stat().st_size // 1024} KB")
    if CATALOGOS.is_dir():
        dest_cat = a.salida / "catalogos"
        dest_cat.mkdir(exist_ok=True)
        for pdf in sorted(CATALOGOS.glob("*.pdf")):
            shutil.copyfile(pdf, dest_cat / pdf.name)
            print(f"{dest_cat / pdf.name}: {pdf.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
