"""HU-09 y SCRUM-66: exporta las alertas de reposición de los 30 repuestos del simulador.

La lógica es una sola y vive en el motor del simulador (src/simulador/motor.js, con su referencia en Python
src/simulador/motor_ref.py). Este script no calcula nada por su cuenta: llama a motor_ref.alertas con los datos de
data/processed/simulador/datos_app.json y deja tres salidas para revisar sin abrir la app:

- data/processed/hu-09/alertas_faltantes.csv: una fila por repuesto, en orden de prioridad;
- reports/hu-09/REPORTE_HU09.md: conteos, criterios y la tabla;
- reports/hu-09/prioridades.svg: los repuestos que hay que pedir o vigilar, con su venta en el plazo y su stock.

Criterios que vienen de la primera versión de HU-09 (Sabrina Adrian Zelaya): un dato que falta no se reemplaza por
cero, sino que deja el repuesto en NO_CALCULABLE con su motivo y con las cifras calculadas vacías; la igualdad entre
la venta durante la entrega y el stock no es alerta; no se redondea antes de comparar; y si algo falla, las salidas
anteriores no se tocan.

Uso, desde cualquier carpeta:
    python src/hu-09/generar_alertas.py [--tc 11.70] [--salida CARPETA] [--reporte ARCHIVO.md]
Sin --tc usa el dólar oficial más reciente que trae datos_app.json. Solo biblioteca estándar.
"""
import argparse
import csv
import io
import json
import os
import sys
import tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(RAIZ, "src", "simulador"))
import motor_ref  # noqa: E402

DATOS = os.path.join(RAIZ, "data", "processed", "simulador", "datos_app.json")
SALIDA = os.path.join(RAIZ, "data", "processed", "hu-09")
REPORTE = os.path.join(RAIZ, "reports", "hu-09", "REPORTE_HU09.md")

COLUMNAS = ["prioridad", "repuesto_id", "estado", "alerta_faltante", "motivos", "stock", "en_camino",
            "punto_pedido", "nivel_maximo", "plazo_dias", "venta_mes_pronosticada", "venta_durante_entrega",
            "faltante_previsto", "margen_dias", "cantidad_sugerida", "costo_bs", "clase_abc", "tipo_demanda",
            "proveedor_id", "tc_bs_por_usd", "tc_fecha", "origen_dato"]


def alerta_faltante(fila):
    """El criterio de HU-09 en sus tres valores: ALERTA solo si la venta durante la entrega supera lo disponible."""
    if fila["est"] == 3:
        return "NO_CALCULABLE"
    return "ALERTA" if fila["faltante_previsto"] > 0 else "SIN_ALERTA"


def celda(valor, decimales=None):
    """Vacío para lo que no se calculó (nunca cero); números sin notación científica."""
    if valor is None:
        return ""
    if decimales is not None:
        return "{:.{}f}".format(valor, decimales)
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def construir(datos, tc, tc_fecha):
    filas = motor_ref.alertas(datos, tc)
    salida = []
    for i, f in enumerate(filas, 1):
        salida.append({
            "prioridad": i, "repuesto_id": f["id"], "estado": f["etiqueta"], "alerta_faltante": alerta_faltante(f),
            "motivos": "|".join(f["motivos"]), "stock": celda(f["stock"]), "en_camino": celda(f["en_camino"]),
            "punto_pedido": celda(f["punto_pedido"]), "nivel_maximo": celda(f["nivel_maximo"]),
            "plazo_dias": celda(f["plazo"]), "venta_mes_pronosticada": celda(f["venta_mes"], 4),
            "venta_durante_entrega": celda(f["demanda_entrega"], 4),
            "faltante_previsto": celda(f["faltante_previsto"], 4), "margen_dias": celda(f["margen_dias"]),
            "cantidad_sugerida": f["cantidad_sugerida"], "costo_bs": celda(f["costo_bs"], 2),
            "clase_abc": f["clase"], "tipo_demanda": f["tipo_demanda"], "proveedor_id": f["proveedor_id"],
            "tc_bs_por_usd": "{:.2f}".format(tc), "tc_fecha": tc_fecha,
            "origen_dato": "ventas REALES de carparts; stock, plazo y costo SINTÉTICOS (SCRUM-55)"})
    return filas, salida


def csv_texto(salida):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNAS, lineterminator="\n")
    w.writeheader()
    w.writerows(salida)
    return buf.getvalue()


def svg_texto(filas):
    """Barras horizontales: venta durante la entrega contra stock más lo que viene en camino."""
    urgentes = [f for f in filas if f["est"] in (0, 1)]
    alto = 70 + 34 * max(len(urgentes), 1)
    tope = max([max(f["demanda_entrega"], f["stock"] + f["en_camino"]) for f in urgentes] + [1])
    escala = 420 / tope
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="720" height="{}" viewBox="0 0 720 {}" '
         'font-family="sans-serif" font-size="13" role="img" '
         'aria-label="Repuestos para pedir o vigilar: venta durante la entrega contra stock y en camino">'.format(alto, alto),
         '<rect width="720" height="{}" fill="#ffffff"/>'.format(alto),
         '<text x="20" y="26" font-size="15" font-weight="bold" fill="#18201b">Pedir ya y vigilar: venta durante la entrega frente a lo disponible</text>',
         '<rect x="20" y="38" width="12" height="10" fill="#01863e"/><text x="38" y="47" fill="#4b564f">stock + en camino</text>',
         '<rect x="170" y="38" width="12" height="10" fill="#c0392b"/><text x="188" y="47" fill="#4b564f">venta promedio durante la entrega</text>']
    if not urgentes:
        p.append('<text x="20" y="90" fill="#4b564f">Ningún repuesto para pedir o vigilar.</text>')
    for i, f in enumerate(urgentes):
        y = 70 + 34 * i
        disp = f["stock"] + f["en_camino"]
        p.append('<text x="20" y="{}" fill="#18201b">{} · {}</text>'.format(y + 12, f["id"], f["etiqueta"]))
        p.append('<rect x="200" y="{}" width="{:.1f}" height="11" fill="#01863e"/>'.format(y, max(disp * escala, 1)))
        p.append('<rect x="200" y="{}" width="{:.1f}" height="11" fill="#c0392b"/>'.format(y + 13, max(f["demanda_entrega"] * escala, 1)))
        p.append('<text x="{:.1f}" y="{}" fill="#4b564f">{:g} u · {:.1f} u</text>'.format(
            210 + max(disp, f["demanda_entrega"]) * escala, y + 17, disp, f["demanda_entrega"]))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def informe_texto(filas, salida, tc, tc_fecha):
    cuenta = {k: sum(1 for s in salida if s["alerta_faltante"] == k) for k in ("ALERTA", "SIN_ALERTA", "NO_CALCULABLE")}
    estados = {k: sum(1 for f in filas if f["etiqueta"] == k) for k in motor_ref.ETIQUETAS}
    l = ["# HU-09 y SCRUM-66: alertas de reposición", "",
         "Generado por `src/hu-09/generar_alertas.py` con la lógica única del motor del simulador "
         "(`motor_ref.alertas`). Dólar: {} Bs por dólar ({}).".format("{:.2f}".format(tc).replace(".", ","), tc_fecha), "",
         "## Resultado", "",
         "Estados de reposición: Pedir ya **{}**, Vigilar **{}**, Cubierto **{}**, Sin datos **{}**.".format(
             estados["Pedir ya"], estados["Vigilar"], estados["Cubierto"], estados["Sin datos"]), "",
         "Faltante previsto con la venta promedio: ALERTA **{}**, SIN_ALERTA **{}**, NO_CALCULABLE **{}**.".format(
             cuenta["ALERTA"], cuenta["SIN_ALERTA"], cuenta["NO_CALCULABLE"]), "",
         "Que la venta promedio no supere lo disponible no quiere decir que no haya riesgo: el simulador prueba 1.500 "
         "futuros de venta y de plazo y cuenta en cuántos se pierde alguna venta. Por eso un repuesto puede estar en "
         "«Pedir ya» sin faltante promedio.", "",
         "![Prioridades](prioridades.svg)", "",
         "## Criterios", "",
         "- **Pedir ya:** stock más lo que viene en camino es igual o menor que el punto de pedido.",
         "- **Vigilar:** llega al punto de pedido, a la venta pronosticada, antes de que el proveedor pueda entregar.",
         "- **Cubierto:** el resto.",
         "- **Sin datos:** falta el stock, el plazo, el historial de venta o el punto de pedido. Las cifras calculadas "
         "quedan vacías, no en cero, y el motivo se informa.",
         "- **Venta durante la entrega** = venta diaria pronosticada (SBA o media) × plazo del proveedor, sin redondear.",
         "- **Faltante previsto** = máximo entre cero y la venta durante la entrega menos stock y en camino. "
         "La igualdad no es alerta.",
         "- **Orden:** estado, faltante de mayor a menor, días hasta el punto de pedido y código.", "",
         "## Tabla", "",
         "| # | Repuesto | Estado | Faltante (HU-09) | Stock | En camino | Punto de pedido | Plazo | Venta en el plazo | Cantidad sugerida | Costo Bs |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in salida:
        venta = "" if s["venta_durante_entrega"] == "" else "{:.2f}".format(float(s["venta_durante_entrega"]))
        l.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            s["prioridad"], s["repuesto_id"], s["estado"], s["alerta_faltante"], s["stock"], s["en_camino"],
            s["punto_pedido"], s["plazo_dias"], venta, s["cantidad_sugerida"], s["costo_bs"]))
    l += ["", "Ventas REALES de carparts (Hyndman y otros, 2008) con el mes adaptado; stock, plazo, punto de pedido y "
          "costo SINTÉTICOS (SCRUM-55). No hay datos de reservas ni bloqueos: el stock disponible es el registrado.", ""]
    return "\n".join(l)


def escribir_atomico(ruta, texto):
    """Escribe en un temporal de la misma carpeta y lo renombra: un error no deja el archivo a medias."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def ejecutar(datos_ruta=DATOS, salida=SALIDA, reporte=REPORTE, tc=None):
    with open(datos_ruta, encoding="utf-8") as f:
        datos = json.load(f)
    tc_fecha = datos["tc"]["oficial"]["fecha"]
    if tc is None:
        tc = float(datos["tc"]["oficial"]["valor"])
    else:
        tc_fecha = "supuesto, no es el oficial"
    filas, filas_csv = construir(datos, tc, tc_fecha)
    textos = {os.path.join(salida, "alertas_faltantes.csv"): csv_texto(filas_csv),
              reporte: informe_texto(filas, filas_csv, tc, tc_fecha),
              os.path.join(os.path.dirname(reporte), "prioridades.svg"): svg_texto(filas)}
    for ruta, texto in textos.items():
        escribir_atomico(ruta, texto)
    return filas, filas_csv


def main(argv=None):
    ap = argparse.ArgumentParser(description="Alertas de reposición (HU-09 y SCRUM-66)")
    ap.add_argument("--datos", default=DATOS, help="datos_app.json del simulador")
    ap.add_argument("--salida", default=SALIDA, help="carpeta del CSV")
    ap.add_argument("--reporte", default=REPORTE, help="archivo .md del informe; el SVG va a su lado")
    ap.add_argument("--tc", type=float, default=None, help="dólar para el costo; sin esto, el oficial más reciente")
    a = ap.parse_args(argv)
    try:
        filas, filas_csv = ejecutar(os.path.abspath(a.datos), os.path.abspath(a.salida), os.path.abspath(a.reporte), a.tc)
    except (OSError, ValueError, KeyError) as e:
        print("ERROR: no se generaron alertas: {}".format(e), file=sys.stderr)
        return 1
    cuenta = {}
    for f in filas:
        cuenta[f["etiqueta"]] = cuenta.get(f["etiqueta"], 0) + 1
    print("Alertas: " + ", ".join("{}={}".format(k, cuenta.get(k, 0)) for k in motor_ref.ETIQUETAS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
