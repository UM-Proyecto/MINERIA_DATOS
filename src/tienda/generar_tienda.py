"""Arma la tienda pública del portal de MULTIPARTES en un solo HTML (reports/tienda/MULTIPARTES_Tienda.html).

Es la mejora del sitio www.multipartes.com.bo aprobada por Sam el 14-11-2026. Incrusta en plantilla_tienda.html:
- el contenido real del sitio (data/raw/tienda/contenido_sitio.json) y sus imágenes (data/raw/tienda/imagenes/);
- el catálogo de SCRUM-74 (nombres ILUSTRATIVOS, fotos con licencia libre) con lo justo para cotizar: precio de
  venta, costo, stock y proveedor de cada repuesto (SINTÉTICOS, SCRUM-55);
- el dólar oficial del BCB (SCRUM-54) y el motor del simulador (motor.js), del que usa solo Motor.cotizar.
No incluye ventas, clientes ni nada de la parte de la empresa.

Uso, desde la raíz del repositorio (después de preparar_datos.py):
    python3 src/tienda/generar_tienda.py [--salida RUTA]

Solo usa la biblioteca estándar.
"""
import argparse
import base64
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
PLANTILLA = BASE / "src/tienda/plantilla_tienda.html"
CONTENIDO = BASE / "data/raw/tienda/contenido_sitio.json"
IMG_SITIO = BASE / "data/raw/tienda/imagenes"
IMG_CATALOGO = BASE / "data/raw/scrum-74/imagenes"
DATOS = BASE / "data/processed/simulador/datos_app.json"
MOTOR = BASE / "src/simulador/motor.js"
COTDOC = BASE / "src/portal/cotizacion_doc.js"  # cotización imprimible y correo simulado (SCRUM-83), va después del motor
SALIDA = BASE / "reports/tienda/MULTIPARTES_Tienda.html"

# Categoría ILUSTRATIVA del catálogo (SCRUM-74) → rubro del sitio de MULTIPARTES.
RUBRO_DE_CATEGORIA = {
    "Bujía de encendido": "Sistema eléctrico",
    "Filtro de aceite": "Filtros",
    "Pastillas de freno": "Frenos y embrague",
    "Disco de freno": "Frenos y embrague",
    "Kit de embrague": "Frenos y embrague",
    "Correa de distribución": "Retenes, rodamientos, crucetas y correas",
    "Cubo y rodamiento de rueda": "Retenes, rodamientos, crucetas y correas",
    "Amortiguador": "Suspensión/Dirección",
}
CAMPOS_REP = ("repuesto_id", "proveedor_id", "precio_venta_usd", "costo_unitario_usd", "stock_al_2026_11_10")
CAMPOS_PROV = ("proveedor_id", "incoterm", "flete_pct_aplicado", "gastos_pct_cif", "plazo_normal_dias")


def uri(ruta):
    return "data:image/jpeg;base64," + base64.b64encode(ruta.read_bytes()).decode()


def seguro_en_script(texto):
    return re.sub(r"</(script)", r"<\\/\1", texto, flags=re.IGNORECASE)


def datos_tienda():
    contenido = json.loads(CONTENIDO.read_text(encoding="utf-8"))
    d = json.loads(DATOS.read_text(encoding="utf-8"))
    catalogo = sorted(d["catalogo"]["repuestos"], key=lambda c: c["repuesto_id"])
    faltan = {c["categoria"] for c in catalogo} - set(RUBRO_DE_CATEGORIA)
    if faltan:
        raise SystemExit(f"Categorías sin rubro del sitio: {sorted(faltan)}")
    rubros = {r[0] for r in contenido["rubros"]}
    if not set(RUBRO_DE_CATEGORIA.values()) <= rubros:
        raise SystemExit("RUBRO_DE_CATEGORIA usa un rubro que no está en el sitio")
    imagenes = {"logo_multipartes.jpg": uri(IMG_SITIO / "logo_multipartes.jpg")}
    for _, f in contenido["rubros"]:
        imagenes[f] = uri(IMG_SITIO / f)
    for f in sorted({c["imagen"] for c in catalogo}):
        imagenes[f] = uri(IMG_CATALOGO / f)
    return {
        "contenido": contenido,
        "imagenes": imagenes,
        "catalogo": [{k: c[k] for k in ("repuesto_id", "nombre", "categoria", "descripcion", "imagen")} for c in catalogo],
        "repuestos": [{k: r[k] for k in CAMPOS_REP} for r in d["repuestos"]],
        "proveedores": [{k: p[k] for k in CAMPOS_PROV} for p in d["proveedores"]],
        "tc": {"valor": d["tc"]["oficial"]["valor"], "fecha": d["tc"]["oficial"]["fecha"]},
        "rubro_de_categoria": RUBRO_DE_CATEGORIA,
    }


def generar(salida=SALIDA):
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    for m in ("__TIENDA__", "__MOTOR__"):
        if plantilla.count(m) != 1:
            raise SystemExit(f"La plantilla debe tener una única marca {m}")
    motor = MOTOR.read_text(encoding="utf-8")
    if "module.exports = Motor" not in motor:
        raise SystemExit("motor.js no tiene la forma esperada")
    t = seguro_en_script(json.dumps(datos_tienda(), ensure_ascii=False, separators=(",", ":")))
    html = plantilla.replace("__TIENDA__", t).replace("__MOTOR__", seguro_en_script(motor + "\n" + COTDOC.read_text(encoding="utf-8")))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    return html


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args(argv)
    generar(a.salida.resolve())
    print(f"{a.salida}: {a.salida.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
