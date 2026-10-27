"""
HU-18 - Conciliar inventario con conteos físicos
Usa los resultados de la HU-17 (reporte_depuracion_final.csv).

Criterio 1: registrar_conteo()      -> registra un conteo físico por repuesto y fecha
Criterio 2: calcular_conciliacion() -> diferencia = conteo físico - stock registrado
Criterio 3: aplicar_ajuste()        -> el ajuste exige motivo y deja historial (usuario y fecha)
"""
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
def ruta(carpeta, nombre): return RAIZ / "data" / carpeta / "hu-18" / nombre

ARCH_REPORTE   = ruta("processed", "reporte_depuracion_final.csv")
ARCH_CATALOGO  = ruta("raw", "catalogo_repuestos.csv")
ARCH_STOCK_INI = ruta("raw", "stock_inicial.csv")
ARCH_CONTEOS   = ruta("raw", "conteos_fisicos.csv")
ARCH_SOLICITUDES = ruta("raw", "ajustes_solicitados.csv")
ARCH_CONCILIACION = ruta("processed", "conciliacion_inventario.csv")
ARCH_AJUSTES   = ruta("processed", "ajustes_inventario.csv")
ARCH_HISTORIAL = ruta("processed", "historial_ajustes.csv")

# Regla de stock: los DUPLICADOS siempre se excluyen. Los PENDIENTE_REVISION
# se cuentan como válidos hasta que alguien confirme lo contrario.
INCLUIR_PENDIENTES = True

COLS_CONTEOS = ["id_conteo", "fecha_conteo", "codigo_unico", "conteo_fisico", "usuario"]
COLS_AJUSTES = ["id_ajuste", "fecha_conteo", "codigo_unico", "cantidad_ajuste", "motivo", "usuario", "fecha_hora"]
COLS_HISTORIAL = ["id_historial", "fecha_hora", "fecha_conteo", "codigo_unico", "accion", "stock_antes",
                  "conteo_fisico", "cantidad_ajuste", "stock_despues", "motivo", "usuario"]

def leer(arch, columnas=None):
    if os.path.exists(arch):
        return pd.read_csv(arch, encoding="utf-8-sig")
    return pd.DataFrame(columns=columnas or [])

def agregar_fila(arch, fila, columnas):
    """Agrega una fila al final del CSV (nunca reescribe lo anterior)."""
    existe = os.path.exists(arch)
    pd.DataFrame([fila], columns=columnas).to_csv(arch, mode="a", header=not existe, index=False, encoding="utf-8-sig")

def siguiente_id(arch, columna, columnas):
    df = leer(arch, columnas)
    return 1 if df.empty else int(df[columna].max()) + 1

def descripciones():
    rep = pd.read_csv(ARCH_REPORTE, encoding="utf-8-sig")[["codigo_repuesto", "codigo_unico"]].drop_duplicates()
    cat = pd.read_csv(ARCH_CATALOGO, encoding="utf-8-sig")
    m = rep.merge(cat, on="codigo_repuesto").sort_values("id_registro")
    return m.drop_duplicates("codigo_unico").set_index("codigo_unico")["descripcion"].to_dict()

# ---------------------------------------------------------------- criterio 1
def registrar_conteo(codigo_unico, fecha_conteo, conteo_fisico, usuario):
    """Registra un conteo físico por repuesto y fecha, con validaciones."""
    if codigo_unico not in descripciones():
        raise ValueError(f"El repuesto {codigo_unico} no existe en el catálogo.")
    try:
        fecha = pd.to_datetime(fecha_conteo, format="%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError("La fecha debe tener el formato AAAA-MM-DD.")
    if int(conteo_fisico) < 0:
        raise ValueError("El conteo físico no puede ser negativo.")
    if not str(usuario).strip():
        raise ValueError("El conteo debe indicar el usuario que lo realizó.")
    conteos = leer(ARCH_CONTEOS, COLS_CONTEOS)
    if ((conteos["codigo_unico"] == codigo_unico) & (conteos["fecha_conteo"] == fecha)).any():
        raise ValueError(f"Ya existe un conteo de {codigo_unico} para {fecha}.")
    fila = [siguiente_id(ARCH_CONTEOS, "id_conteo", COLS_CONTEOS), fecha, codigo_unico, int(conteo_fisico), usuario]
    agregar_fila(ARCH_CONTEOS, fila, COLS_CONTEOS)
    return fila

# ---------------------------------------------------------------- criterio 2
def stock_registrado(codigo_unico, fecha_conteo):
    """Stock inicial + entradas - salidas (hasta la fecha del conteo) + ajustes de conteos anteriores."""
    ini = pd.read_csv(ARCH_STOCK_INI)
    stock_ini = int(ini.loc[ini["codigo_unico"] == codigo_unico, "stock_inicial"].sum())
    mov = pd.read_csv(ARCH_REPORTE, encoding="utf-8-sig")
    estados = ["ORIGINAL", "PENDIENTE_REVISION"] if INCLUIR_PENDIENTES else ["ORIGINAL"]
    mov = mov[(mov["codigo_unico"] == codigo_unico) & (mov["fecha"] <= fecha_conteo) & (mov["estado"].isin(estados))]
    entradas = int(mov.loc[mov["tipo_movimiento"] == "ENTRADA", "cantidad"].sum())
    salidas = int(mov.loc[mov["tipo_movimiento"] == "SALIDA", "cantidad"].sum())
    aj = leer(ARCH_AJUSTES, COLS_AJUSTES)
    # un ajuste de la misma fecha no se cuenta: así la diferencia original sigue visible
    ajustes_previos = int(aj.loc[(aj["codigo_unico"] == codigo_unico) & (aj["fecha_conteo"] < fecha_conteo), "cantidad_ajuste"].sum())
    pendientes = int((mov["estado"] == "PENDIENTE_REVISION").sum())
    return stock_ini, entradas, salidas, ajustes_previos, pendientes, stock_ini + entradas - salidas + ajustes_previos

def pista_pendiente(codigo_unico, fecha_conteo, diferencia):
    """Si la diferencia coincide con un movimiento PENDIENTE_REVISION, lo sugiere como causa probable."""
    if diferencia == 0:
        return ""
    mov = pd.read_csv(ARCH_REPORTE, encoding="utf-8-sig")
    tipo = "ENTRADA" if diferencia < 0 else "SALIDA"   # faltante -> ¿entrada de más? / sobrante -> ¿salida de más?
    c = mov[(mov["codigo_unico"] == codigo_unico) & (mov["fecha"] <= fecha_conteo) &
            (mov["estado"] == "PENDIENTE_REVISION") & (mov["tipo_movimiento"] == tipo) & (mov["cantidad"] == abs(diferencia))]
    if c.empty:
        return ""
    r = c.iloc[0]
    return f"Coincide con movimiento pendiente {r['id_movimiento']} ({r['tipo_movimiento']} {r['cantidad']}, {r['documento']})"

def calcular_conciliacion():
    desc = descripciones()
    filas = []
    for _, c in leer(ARCH_CONTEOS, COLS_CONTEOS).sort_values(["fecha_conteo", "codigo_unico"]).iterrows():
        ini, ent, sal, ajp, pend, reg = stock_registrado(c["codigo_unico"], c["fecha_conteo"])
        dif = int(c["conteo_fisico"]) - reg
        filas.append({
            "fecha_conteo": c["fecha_conteo"], "codigo_unico": c["codigo_unico"], "descripcion": desc.get(c["codigo_unico"], ""),
            "stock_inicial": ini, "entradas": ent, "salidas": sal, "ajustes_previos": ajp,
            "stock_registrado": reg, "conteo_fisico": int(c["conteo_fisico"]), "diferencia": dif,
            "tipo_diferencia": "SIN DIFERENCIA" if dif == 0 else ("FALTANTE" if dif < 0 else "SOBRANTE"),
            "movimientos_pendientes_en_calculo": pend,
            "pista": pista_pendiente(c["codigo_unico"], c["fecha_conteo"], dif),
            "usuario_conteo": c["usuario"],
        })
    out = pd.DataFrame(filas)
    # estado del ajuste, según el historial
    hist = leer(ARCH_HISTORIAL, COLS_HISTORIAL)
    def estado(r):
        if r["diferencia"] == 0:
            return "NO REQUIERE AJUSTE"
        h = hist[(hist["codigo_unico"] == r["codigo_unico"]) & (hist["fecha_conteo"] == r["fecha_conteo"])]
        if (h["accion"] == "AJUSTE_APLICADO").any():
            return "AJUSTADO"
        return "AJUSTE PENDIENTE"
    out["estado_ajuste"] = out.apply(estado, axis=1)
    return out

# ---------------------------------------------------------------- criterio 3
def aplicar_ajuste(codigo_unico, fecha_conteo, motivo, usuario, fecha_hora=None):
    """Aplica el ajuste (conteo físico - stock registrado). Exige motivo y usuario; todo queda en el historial."""
    fecha_hora = fecha_hora or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conc = calcular_conciliacion()
    fila = conc[(conc["codigo_unico"] == codigo_unico) & (conc["fecha_conteo"] == fecha_conteo)]

    def historial(accion, antes, fisico, cant, despues, texto):
        agregar_fila(ARCH_HISTORIAL, [siguiente_id(ARCH_HISTORIAL, "id_historial", COLS_HISTORIAL), fecha_hora, fecha_conteo,
                                      codigo_unico, accion, antes, fisico, cant, despues, texto, usuario], COLS_HISTORIAL)

    if fila.empty:
        return "RECHAZADO: no hay conteo de ese repuesto en esa fecha"
    r = fila.iloc[0]
    motivo = "" if pd.isna(motivo) else str(motivo).strip()
    usuario_ok = bool(str(usuario).strip()) and not pd.isna(usuario)
    if not motivo:
        historial("AJUSTE_RECHAZADO", r["stock_registrado"], r["conteo_fisico"], 0, r["stock_registrado"], "RECHAZADO: el motivo es obligatorio")
        return "RECHAZADO: el motivo es obligatorio"
    if not usuario_ok:
        return "RECHAZADO: el usuario es obligatorio"
    if r["diferencia"] == 0:
        return "RECHAZADO: no hay diferencia que ajustar"
    if r["estado_ajuste"] == "AJUSTADO":
        return "RECHAZADO: esa diferencia ya fue ajustada"
    cant = int(r["diferencia"])
    agregar_fila(ARCH_AJUSTES, [siguiente_id(ARCH_AJUSTES, "id_ajuste", COLS_AJUSTES), fecha_conteo, codigo_unico, cant, motivo, usuario, fecha_hora], COLS_AJUSTES)
    historial("AJUSTE_APLICADO", r["stock_registrado"], r["conteo_fisico"], cant, r["stock_registrado"] + cant, motivo)
    return f"APLICADO: ajuste de {cant:+d} unidades"

# ---------------------------------------------------------------- ejecución
if __name__ == "__main__":
    print("Procesando solicitudes de ajuste...")
    # procesa las solicitudes de ajuste del archivo ajustes_solicitados.csv
    for _, s in leer(ARCH_SOLICITUDES).iterrows():
        res = aplicar_ajuste(s["codigo_unico"], s["fecha_conteo"], s["motivo"], s["usuario"], s.get("fecha_hora"))
        print(f"  {s['codigo_unico']} {s['fecha_conteo']}: {res}")

    conciliacion = calcular_conciliacion()
    conciliacion.to_csv(ARCH_CONCILIACION, index=False, encoding="utf-8-sig")
    print("\nArchivos generados: conciliacion_inventario.csv, ajustes_inventario.csv, historial_ajustes.csv")
    print("\nResumen de la conciliación:")
    print(conciliacion["tipo_diferencia"].value_counts().to_string())
    print("\nEstado de los ajustes:")
    print(conciliacion["estado_ajuste"].value_counts().to_string())
