"""Datos FICTICIOS (pseudoaleatorios, semilla fija) para SCRUM-6 y SCRUM-7, a pedido de Fiorella.

Se adapta al flujo del equipo (repo UM-Proyecto/MINERIA_DATOS):
  - los movimientos de septiembre de Sabrina (HU-17) quedan intactos, solo se les agrega el precio;
  - el historial anterior termina EXACTAMENTE en su stock_inicial (HU-18);
  - repuestos, descripciones, fecha de corte, proveedores, clientes y usuarios se leen de sus archivos.

Sin argumentos usa las carpetas que están junto a este archivo, así que corre igual en cualquier
máquina y sistema operativo. Solo necesita Python 3.8 o superior, sin librerías extra.
Todo lo generado es SINTETICO: no representa precios, ventas ni proveedores reales de MultiPartes.
"""
import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
FUENTE = "Datos ficticios generados por el equipo (pendiente del dato real de MultiPartes)"
DISPONIBILIDAD = ["En stock", "En stock", "Bajo pedido", "Limitada"]
CONDICIONES = ["Contado", "Credito 15 dias", "Credito 30 dias", "50% anticipo"]
PLAZOS = [3, 7, 15, 30, 45]


def leer(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        sys.exit(f"No se encontró el archivo requerido: {ruta}")
    with ruta.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def escribir(ruta, campos, filas):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def repuestos(catalogo, equiv, parametros):
    """codigo_unico -> (codigo principal, descripcion, costo base, proveedor principal).
    El principal es la primera fila del catálogo de cada código único, igual que en conciliacion.py de HU-18."""
    base = {}
    for fila in sorted(catalogo, key=lambda r: int(r["id_registro"])):
        cu = equiv.get(fila["codigo_repuesto"])
        if cu and cu not in base:
            base[cu] = (fila["codigo_repuesto"], fila["descripcion"])
    out = {}
    for p in parametros:
        cu = p["codigo_unico"]
        if cu not in base:
            sys.exit(f"parametros_sinteticos.csv trae {cu}, que no está en el catálogo ni en el reporte de HU-17")
        out[cu] = (base[cu][0], base[cu][1], float(p["costo_base_usd"]), p["proveedor_principal"])
    faltan = sorted(set(base) - set(out))
    if faltan:
        sys.exit(f"Faltan parámetros de costo y proveedor para: {', '.join(faltan)}")
    return out


def historial(rng, rep, stock_ini, corte, meses, usuarios, clientes):
    """Simula hacia atrás desde el corte para que el stock final sea exactamente el stock_inicial del equipo."""
    inicio = corte - timedelta(days=30 * meses - 1)
    filas, n = [], 100001
    for cu, (codigo, _, costo, prov) in rep.items():
        objetivo = int(stock_ini[cu])
        demanda = max(6, objetivo * 1.5)  # unidades por mes
        alto = max(objetivo * 2.5, demanda)
        stock, dia, evs = objetivo, corte, []
        while dia >= inicio:
            if dia.weekday() < 5 and stock > alto and rng.random() < 0.6:  # deshace una entrada (reposición)
                cant = min(stock, max(1, int(demanda * rng.uniform(1.0, 2.0))))
                if stock - cant >= 0:
                    evs.append((dia, 1, "ENTRADA", cant, round(costo * rng.uniform(0.92, 1.10), 2), prov, rng.choice(usuarios)))
                    stock -= cant
            if dia.weekday() < 6 and rng.random() < 0.35:  # deshace una salida (venta)
                est = 1.15 if dia.month in (11, 12, 1) else 1.0
                cant = max(1, int(rng.gauss(demanda / 8 * est, demanda / 25 + 1)))
                evs.append((dia, 0, "SALIDA", cant, round(costo * 1.35 * rng.uniform(0.95, 1.08), 2), rng.choice(clientes), rng.choice(usuarios)))
                stock += cant
            dia -= timedelta(days=1)
        if stock > 0:  # saldo con el que arranca el periodo
            evs.append((inicio, -1, "ENTRADA", stock, round(costo, 2), "Saldo inicial", usuarios[0]))
        for dia, orden, tipo, cant, precio, contraparte, usuario in evs:
            filas.append(dict(fecha=dia.isoformat(), orden=orden, codigo_repuesto=codigo, codigo_unico=cu, tipo_movimiento=tipo,
                              cantidad=cant, precio_unitario_usd=precio, proveedor_cliente=contraparte, usuario=usuario))
    filas.sort(key=lambda r: (r["fecha"], r["codigo_unico"], r["orden"]))
    ctr = {"ENTRADA": 5000 - 1, "SALIDA": 1000 - 1}
    for r in filas:
        r["id_movimiento"] = n
        n += 1
        if r["proveedor_cliente"] == "Saldo inicial":
            r["documento"] = "SI-" + r["codigo_unico"]
        else:
            ctr[r["tipo_movimiento"]] -= 1
            r["documento"] = "%s-%d" % ("OC" if r["tipo_movimiento"] == "ENTRADA" else "VT", ctr[r["tipo_movimiento"]])
        r["origen"] = "SINTETICO"
        del r["orden"]
    return filas


def septiembre(movs, equiv, rep, rng):
    """Los movimientos del equipo, intactos, con precio (el duplicado lleva el mismo precio que su original)."""
    precios, filas = {}, []
    for m in movs:
        cu = equiv[m["codigo_repuesto"]]
        costo = rep[cu][2]
        clave = (cu, m["fecha"], m["tipo_movimiento"], m["documento"])
        if clave not in precios:
            f = 1.35 * rng.uniform(0.95, 1.08) if m["tipo_movimiento"] == "SALIDA" else rng.uniform(0.92, 1.10)
            precios[clave] = round(costo * f, 2)
        filas.append(dict(m, codigo_unico=cu, precio_unitario_usd=precios[clave], origen="EQUIPO_FICTICIO"))
    return filas


def cotizaciones(rng, rep, proveedores, base, hoy):
    filas = []
    for cu, (codigo, desc, costo, prov) in rep.items():
        otros = rng.sample([p for p in proveedores if p != prov], 2)
        for p in [prov] + otros:
            f = base + timedelta(days=rng.randint(0, 25))
            filas.append(dict(proveedor=p, codigo_unico=cu, codigo_repuesto=codigo, descripcion=desc,
                              precio=round(costo * rng.uniform(0.9, 1.15), 2), moneda="USD", fecha=f.isoformat(),
                              vigencia=(f + timedelta(days=rng.choice([15, 30, 45]))).isoformat(),
                              disponibilidad=rng.choice(DISPONIBILIDAD), condiciones_pago=rng.choice(CONDICIONES),
                              plazo_entrega_dias=rng.choice(PLAZOS), tipo_dato="SINTETICO", fuente=FUENTE, fecha_actualizacion=hoy))
    return filas


def costos(rng, base, hoy):
    datos = [("seguro de carga", "% del CIF", rng.uniform(0.4, 0.9)),
             ("nacionalizacion y agente aduanero", "% del CIF", rng.uniform(2.5, 4.0)),
             ("comision de gestion de importacion", "% del CIF", rng.uniform(1.0, 2.5)),
             ("flete terrestre Arica/Iquique -> Santa Cruz", "USD por kg", rng.uniform(0.08, 0.16))]
    return [dict(concepto=c, valor=round(v, 3), unidad=u, fecha_dato=base.strftime("%Y-%m"), tipo_dato="SINTETICO",
                 respaldo="ninguno: valor pseudoaleatorio de prueba, pendiente de factura real",
                 fuente=FUENTE, fecha_actualizacion=hoy) for c, u, v in datos]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--insumos", default=RAIZ / "data" / "raw" / "hu-30-31" / "insumos_equipo", help="carpeta con los archivos del equipo")
    ap.add_argument("--parametros", default=RAIZ / "data" / "raw" / "hu-30-31" / "parametros_sinteticos.csv")
    ap.add_argument("--salida", default=RAIZ / "data" / "processed" / "hu-30-31" / "sintetico")
    ap.add_argument("--semilla", type=int, default=20261019)
    ap.add_argument("--meses", type=int, default=12, help="meses de historial anteriores al corte")
    ap.add_argument("--fecha-actualizacion", default=date.today().isoformat())
    a = ap.parse_args()

    ins = Path(a.insumos)
    rng = random.Random(a.semilla)
    ini = leer(ins / "stock_inicial.csv")
    cortes = {r["fecha_corte"] for r in ini}
    if len(cortes) != 1:
        sys.exit(f"stock_inicial.csv debe tener una sola fecha_corte y trae {sorted(cortes)}")
    corte = date.fromisoformat(cortes.pop())
    stock_ini = {r["codigo_unico"]: r["stock_inicial"] for r in ini}
    equiv = {r["codigo_repuesto"]: r["codigo_unico"] for r in leer(ins / "reporte_depuracion_final.csv")}
    rep = repuestos(leer(ins / "catalogo_repuestos.csv"), equiv, leer(a.parametros))
    if set(stock_ini) != set(rep):
        sys.exit("El stock inicial y los parámetros no cubren los mismos repuestos")
    movs = leer(ins / "movimientos_inventario.csv")
    sin_equiv = sorted({m["codigo_repuesto"] for m in movs} - set(equiv))
    if sin_equiv:
        sys.exit(f"Códigos sin equivalencia en el reporte de HU-17: {', '.join(sin_equiv)}")
    usuarios = sorted({m["usuario"] for m in movs if m.get("usuario")})
    clientes = sorted({m["proveedor_cliente"] for m in movs if m["tipo_movimiento"] == "SALIDA"})
    proveedores = sorted({m["proveedor_cliente"] for m in movs if m["tipo_movimiento"] == "ENTRADA"} | {v[3] for v in rep.values()})
    if not usuarios or not clientes:
        sys.exit("movimientos_inventario.csv no trae usuarios o clientes para tomar como modelo")

    hist = historial(rng, rep, stock_ini, corte, a.meses, usuarios, clientes)
    sep = septiembre(movs, equiv, rep, rng)
    todos = hist + sep
    for r in todos:
        r["fuente"], r["fecha_actualizacion"] = FUENTE, a.fecha_actualizacion
    salida = Path(a.salida)
    escribir(salida / "movimientos_inventario_sintetico.csv",
             ["id_movimiento", "fecha", "codigo_repuesto", "codigo_unico", "tipo_movimiento", "cantidad", "precio_unitario_usd",
              "documento", "proveedor_cliente", "usuario", "origen", "fuente", "fecha_actualizacion"], todos)
    base = corte + timedelta(days=1)
    escribir(salida / "hu31_cotizaciones_proveedor_sintetico.csv",
             ["proveedor", "codigo_unico", "codigo_repuesto", "descripcion", "precio", "moneda", "fecha", "vigencia", "disponibilidad",
              "condiciones_pago", "plazo_entrega_dias", "tipo_dato", "fuente", "fecha_actualizacion"],
             cotizaciones(rng, rep, proveedores, base, a.fecha_actualizacion))
    escribir(salida / "hu31_costos_complementarios_sintetico.csv",
             ["concepto", "valor", "unidad", "fecha_dato", "tipo_dato", "respaldo", "fuente", "fecha_actualizacion"],
             costos(rng, base, a.fecha_actualizacion))
    print("semilla=%d historial=%d movimientos_del_equipo=%d total=%d corte=%s" % (a.semilla, len(hist), len(sep), len(todos), corte))


if __name__ == "__main__":
    main()
