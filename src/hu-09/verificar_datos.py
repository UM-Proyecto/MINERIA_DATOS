"""HU-09: verificación de datos de inventario y plazo, con fuentes explícitas y sin imputar datos ausentes.

Autora: Sabrina Adrian Zelaya. Era la primera mitad de su generador de alertas de HU-09; el 12-11-2026 las alertas
pasaron a la lógica única del motor del simulador (src/hu-09/generar_alertas.py) y esta parte quedó aparte como
verificación de datos. Reconstruye el stock de cada repuesto con HU-17 y HU-18 (apertura, movimientos depurados,
ajustes del mismo corte, conteo físico, reservas y bloqueos confirmados) y el plazo vigente de HU-31, y dice qué se
pudo verificar y qué no, con su motivo. No calcula alertas.

Python >= 3.8; solo biblioteca estándar. No ejecuta ni modifica otras historias.
"""
import argparse
import calendar
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONFIGURACION = RAIZ / "data/raw/hu-09/configuracion.json"
CAMPOS_DEMANDA = ["sistema_codigos", "codigo_repuesto", "proveedor", "metodo", "validado", "fecha_emision",
                  "inicio_horizonte", "fin_horizonte", "tipo_pronostico", "fecha_objetivo", "demanda",
                  "unidad_temporal", "distribucion", "tipo_dato", "fuente"]
FUENTES = {
    "depuracion": ("data/processed/hu-17/reporte_depuracion_final.csv", "id_movimiento fecha codigo_repuesto codigo_unico tipo_movimiento cantidad documento estado"),
    "conciliacion": ("data/processed/hu-18/conciliacion_inventario.csv", "fecha_conteo codigo_unico descripcion stock_inicial entradas salidas ajustes_previos stock_registrado conteo_fisico diferencia estado_ajuste movimientos_pendientes_en_calculo"),
    "stock_inicial": ("data/raw/hu-18/stock_inicial.csv", "codigo_unico fecha_corte stock_inicial"),
    "ajustes": ("data/processed/hu-18/ajustes_inventario.csv", "id_ajuste fecha_conteo codigo_unico cantidad_ajuste motivo fecha_hora"),
    "historial": ("data/processed/hu-18/historial_ajustes.csv", "codigo_unico fecha_conteo accion cantidad_ajuste stock_antes stock_despues fecha_hora"),
    "cotizaciones": ("data/processed/hu-30-31/sintetico/hu31_cotizaciones_proveedor_sintetico.csv", "codigo_unico proveedor fecha vigencia plazo_entrega_dias tipo_dato fuente fecha_actualizacion"),
}


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def texto(valor, nombre):
    exigir(isinstance(valor, str) and bool(valor.strip()), nombre + ": texto obligatorio")
    return valor.strip()


def claves(objeto, permitidas, requeridas=()):
    exigir(isinstance(objeto, dict), "Se esperaba un objeto JSON")
    exigir(not set(objeto) - set(permitidas), "Campos desconocidos: " + ", ".join(sorted(set(objeto) - set(permitidas))))
    exigir(set(requeridas) <= set(objeto), "Faltan campos: " + ", ".join(sorted(set(requeridas) - set(objeto))))


def numero(valor, nombre, negativo=False, entero=False):
    exigir(not isinstance(valor, (bool, float)), nombre + ": use texto decimal o entero, sin float")
    try:
        n = Decimal(valor)
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError(nombre + ": número inválido") from None
    exigir(n.is_finite() and (negativo or n >= 0), nombre + ": número finito no negativo requerido")
    exigir(n.adjusted() <= 15 and n.as_tuple().exponent >= -8, nombre + ": fuera de precisión admitida (16 enteros, 8 decimales)")
    exigir(not entero or n == n.to_integral_value(), nombre + ": debe ser entero")
    return n


def fecha(valor, nombre):
    try:
        exigir(isinstance(valor, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor), "Fecha inválida")
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        raise ValueError(nombre + ": fecha ISO AAAA-MM-DD inválida") from None


def fecha_registro(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S").date()
    except (ValueError, TypeError):
        raise ValueError("fecha_hora de ajuste inválida") from None


def leer_csv(ruta, campos):
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        cabecera = lector.fieldnames or []
        exigir(len(cabecera) == len(set(cabecera)), str(ruta) + ": columnas repetidas")
        exigir(set(campos) <= set(cabecera), str(ruta) + ": faltan columnas requeridas")
        filas = list(lector)
    exigir(all(None not in r and all(v is not None for v in r.values()) for r in filas), str(ruta) + ": fila CSV mal formada")
    return filas


def unico(filas, nombre):
    exigir(len(filas) == 1, nombre + ": se esperaba una única fila")
    return filas[0]


def equivalencias_hu17(filas):
    equivalencias, ids = {}, set()
    for r in filas:
        exigir(r["id_movimiento"] not in ids, "ID de movimiento duplicado en HU-17")
        ids.add(r["id_movimiento"])
        exigir(r["estado"] in {"ORIGINAL", "DUPLICADO", "PENDIENTE_REVISION"}, "Estado HU-17 desconocido")
        codigo = texto(r["codigo_unico"], "codigo_unico")
        exigir(re.fullmatch(r"REP-\d{4}", codigo), "Código HU-17 incompatible")
        alias = texto(r["codigo_repuesto"], "codigo_repuesto")
        exigir(alias not in equivalencias or equivalencias[alias] == codigo, "Equivalencia contradictoria")
        equivalencias[alias] = codigo
        equivalencias[codigo] = codigo
        numero(r["cantidad"], "cantidad HU-17", entero=True)
        fecha(r["fecha"], "fecha HU-17")
        exigir(r["tipo_movimiento"] in {"ENTRADA", "SALIDA"}, "Tipo de movimiento inválido")
    return equivalencias


def normalizar(codigo, sistema, equivalencias):
    exigir(sistema == "REP", "Catálogo incompatible: RPxxx/HU-34 requiere una equivalencia documentada")
    exigir(isinstance(codigo, str) and codigo in equivalencias, "Código sin equivalencia HU-17: " + str(codigo))
    return equivalencias[codigo]


def cargar_demanda(ruta, equivalencias):
    """CSV vacío con cabecera es válido: falta previsión, no equivale a cero."""
    grupos = {}
    for r in leer_csv(ruta, CAMPOS_DEMANDA):
        codigo = normalizar(r["codigo_repuesto"], r["sistema_codigos"], equivalencias)
        exigir(r["validado"] in {"true", "false"}, "validado debe ser true o false")
        exigir(r["tipo_dato"] in {"DOCUMENTADO", "ESTIMACION", "SINTETICO"}, "Naturaleza de pronóstico inválida")
        for campo in ("metodo", "fuente"):
            texto(r[campo], campo)
        emision = fecha(r["fecha_emision"], "fecha_emision")
        inicio = fecha(r["inicio_horizonte"], "inicio_horizonte")
        fin = fecha(r["fin_horizonte"], "fin_horizonte")
        exigir(emision < inicio <= fin, "El horizonte debe ser futuro a la emisión y no estar invertido")
        exigir(r["tipo_pronostico"] in {"TASA_CONSTANTE", "SERIE_DIARIA"}, "Tipo de pronóstico inválido")
        exigir(r["unidad_temporal"] in {"unidades/dia", "unidades/semana", "unidades/mes"}, "Unidad temporal incompatible")
        valor = numero(r["demanda"], "demanda") if r["demanda"].strip() else None
        metadata = {k: r[k] for k in CAMPOS_DEMANDA if k not in {"codigo_repuesto", "fecha_objetivo", "demanda"}}
        if codigo not in grupos:
            grupos[codigo] = dict(metadata, codigo_unico=codigo, validado=r["validado"] == "true", valores={}, tasa=None)
        g = grupos[codigo]
        exigir(all((g[k] == (r[k] == "true") if k == "validado" else g[k] == r[k]) for k in metadata), "Pronósticos ambiguos para " + codigo)
        if r["tipo_pronostico"] == "TASA_CONSTANTE":
            exigir(not g["valores"] and "fila_constante" not in g and not r["fecha_objetivo"], "Tasa constante duplicada o fecha_objetivo incompatible")
            g["fila_constante"] = True
            g["tasa"] = valor
        else:
            exigir(r["unidad_temporal"] == "unidades/dia", "Serie diaria debe usar unidades/dia")
            objetivo = fecha(r["fecha_objetivo"], "fecha_objetivo")
            exigir(inicio <= objetivo <= fin, "Fecha objetivo fuera del horizonte")
            exigir(r["fecha_objetivo"] not in g["valores"], "Fecha de pronóstico duplicada para " + codigo)
            g["valores"][r["fecha_objetivo"]] = valor
    return grupos


def validar_ajustes(tablas):
    ajustes = tablas["ajustes"]
    exigir(len({a["id_ajuste"] for a in ajustes}) == len(ajustes), "ID de ajuste duplicado")
    exigir(len({(a["codigo_unico"], a["fecha_conteo"]) for a in ajustes}) == len(ajustes), "Ajuste del mismo repuesto/corte duplicado")
    for a in ajustes:
        cantidad = numero(a["cantidad_ajuste"], "ajuste", negativo=True)
        exigir(fecha(a["fecha_conteo"], "fecha ajuste") <= fecha_registro(a["fecha_hora"]), "Ajuste registrado antes de su conteo")
        texto(a["motivo"], "motivo ajuste")
        h = unico([h for h in tablas["historial"] if h["codigo_unico"] == a["codigo_unico"]
                   and h["fecha_conteo"] == a["fecha_conteo"] and h["fecha_hora"] == a["fecha_hora"]
                   and h["accion"] == "AJUSTE_APLICADO"
                   and numero(h["cantidad_ajuste"], "ajuste historial", negativo=True) == cantidad], "Respaldo del ajuste " + a["id_ajuste"])
        exigir(numero(h["stock_despues"], "stock después") == numero(h["stock_antes"], "stock antes") + cantidad, "Historial de ajuste inconsistente")


def stock_de_corte(codigo, config, tablas):
    """Reconstruye el registrado con HU-17 y añade SOLO ajustes del mismo corte."""
    corte = fecha(config["fecha_stock"], "fecha_stock")
    evaluacion = fecha(config["fecha_evaluacion"], "fecha_evaluacion")
    exigir(corte <= evaluacion, "Stock posterior a la evaluación")
    filas = [r for r in tablas["conciliacion"] if r["codigo_unico"] == codigo and r["fecha_conteo"] == corte.isoformat()]
    if not filas:
        return {"stock_registrado": None, "conteo_fisico": None, "stock_ajustado": None, "stock_disponible": None,
                "stock_verificable": False, "motivos": ["STOCK_DE_CORTE_FALTANTE"], "ajustes_mismo_corte": "",
                "duplicados_excluidos": "", "pendientes_hu17": "", "ajustes_rechazados": "", "descripcion": codigo,
                "reservas": None, "bloqueos": None, "naturaleza_disponibilidad": "NO_CONFIRMADA", "fuente_disponibilidad": "", "fecha_disponibilidad": ""}
    r = unico(filas, "Conciliación " + codigo)
    ini = unico([f for f in tablas["stock_inicial"] if f["codigo_unico"] == codigo], "Stock inicial " + codigo)
    desde = fecha(ini["fecha_corte"], "fecha_corte inicial")
    exigir(desde < corte, "El stock de apertura debe ser anterior al corte")
    movs = [m for m in tablas["depuracion"] if m["codigo_unico"] == codigo and desde < fecha(m["fecha"], "fecha movimiento") <= corte]
    duplicados = [m for m in movs if m["estado"] == "DUPLICADO"]
    pendientes = [m for m in movs if m["estado"] == "PENDIENTE_REVISION"]
    validos = [m for m in movs if m["estado"] != "DUPLICADO"]  # misma política HU-18
    entradas = sum((numero(m["cantidad"], "cantidad", entero=True) for m in validos if m["tipo_movimiento"] == "ENTRADA"), Decimal(0))
    salidas = sum((numero(m["cantidad"], "cantidad", entero=True) for m in validos if m["tipo_movimiento"] == "SALIDA"), Decimal(0))
    ajustes_anteriores = [a for a in tablas["ajustes"] if a["codigo_unico"] == codigo and desde < fecha(a["fecha_conteo"], "fecha ajuste") < corte]
    motivos = []
    if any(fecha_registro(a["fecha_hora"]) > evaluacion for a in ajustes_anteriores):
        motivos.append("AJUSTE_POSTERIOR_A_EVALUACION")
    previos = sum((numero(a["cantidad_ajuste"], "ajuste previo", negativo=True) for a in ajustes_anteriores), Decimal(0))
    registrado = numero(ini["stock_inicial"], "stock inicial") + entradas - salidas + previos
    exigir(registrado >= 0, "Stock registrado reconstruido negativo")
    exigir(registrado == numero(r["stock_registrado"], "stock registrado") and entradas == numero(r["entradas"], "entradas")
           and salidas == numero(r["salidas"], "salidas") and previos == numero(r["ajustes_previos"], "ajustes previos", negativo=True)
           and numero(ini["stock_inicial"], "stock inicial") == numero(r["stock_inicial"], "stock inicial conciliación"), "HU-17 y HU-18 no concuerdan para " + codigo)
    aplicados, ajuste = [], Decimal(0)
    for a in tablas["ajustes"]:
        if a["codigo_unico"] != codigo or a["fecha_conteo"] != corte.isoformat():
            continue
        cantidad = numero(a["cantidad_ajuste"], "ajuste aplicado", negativo=True)
        coincidencias = [h for h in tablas["historial"] if h["codigo_unico"] == codigo and h["fecha_conteo"] == a["fecha_conteo"]
                         and h["fecha_hora"] == a["fecha_hora"] and h["accion"] == "AJUSTE_APLICADO"
                         and numero(h["cantidad_ajuste"], "ajuste historial", negativo=True) == cantidad]
        h = unico(coincidencias, "Respaldo del ajuste " + a["id_ajuste"])
        exigir(numero(h["stock_antes"], "stock antes") == registrado
               and numero(h["stock_despues"], "stock después") == registrado + cantidad, "Historial de ajuste inconsistente con conciliación")
        if fecha_registro(a["fecha_hora"]) > evaluacion:
            motivos.append("AJUSTE_POSTERIOR_A_EVALUACION")
        else:
            aplicados.append(a["id_ajuste"])
            ajuste += cantidad
    if r["estado_ajuste"] == "AJUSTADO" and not aplicados:
        motivos.append("AJUSTE_NO_VERIFICADO_A_EVALUACION")
    ajustado = registrado + ajuste
    exigir(ajustado >= 0, "Stock ajustado negativo")
    fisico = numero(r["conteo_fisico"], "conteo físico")
    if ajustado != fisico:
        motivos.append("DIFERENCIA_CONTEO_PENDIENTE")
    if pendientes and not config["permitir_pendientes_con_conteo_coincidente"]:
        motivos.append("MOVIMIENTOS_PENDIENTES_REVISION")
    politica = config["disponibilidad"]["politica"]
    reservas, bloqueos = None, None
    naturaleza, fuente_disponibilidad, fecha_disponibilidad = "NO_CONFIRMADA", "", ""
    if politica == "no_confirmada":
        motivos.append("RESERVAS_Y_BLOQUEOS_DESCONOCIDOS")
    else:
        confirmacion = config["disponibilidad"].get("confirmaciones", {}).get(codigo)
        if confirmacion is None:
            motivos.append("RESERVAS_Y_BLOQUEOS_DESCONOCIDOS")
        else:
            claves(confirmacion, {"reservas", "bloqueos", "fecha", "fuente", "tipo_dato"}, {"reservas", "bloqueos", "fecha", "fuente", "tipo_dato"})
            reservas = numero(confirmacion["reservas"], "reservas")
            bloqueos = numero(confirmacion["bloqueos"], "bloqueos")
            fecha_disponibilidad = fecha(confirmacion["fecha"], "fecha reservas").isoformat()
            exigir(confirmacion["tipo_dato"] in {"DOCUMENTADO", "ESTIMACION", "SINTETICO"}, "Naturaleza de disponibilidad inválida")
            naturaleza, fuente_disponibilidad = confirmacion["tipo_dato"], texto(confirmacion["fuente"], "fuente reservas")
            if fecha_disponibilidad != corte.isoformat():
                motivos.append("RESERVAS_DE_OTRO_CORTE")
    disponible = None
    if reservas is not None and bloqueos is not None:
        if reservas + bloqueos > ajustado:
            motivos.append("RESERVAS_Y_BLOQUEOS_SUPERAN_STOCK")
        elif not motivos:
            disponible = ajustado - reservas - bloqueos
    rechazados = [h for h in tablas["historial"] if h["codigo_unico"] == codigo and h["fecha_conteo"] == corte.isoformat()
                  and h["accion"] == "AJUSTE_RECHAZADO" and fecha_registro(h["fecha_hora"]) <= evaluacion]
    return {"descripcion": r["descripcion"], "stock_registrado": registrado, "conteo_fisico": fisico,
            "stock_ajustado": ajustado, "stock_disponible": disponible, "stock_verificable": disponible is not None,
            "ajustes_mismo_corte": "|".join(aplicados), "duplicados_excluidos": "|".join(m["id_movimiento"] for m in duplicados),
            "pendientes_hu17": "|".join(m["id_movimiento"] for m in pendientes), "ajustes_rechazados": len(rechazados), "motivos": motivos,
            "reservas": reservas, "bloqueos": bloqueos, "naturaleza_disponibilidad": naturaleza,
            "fuente_disponibilidad": fuente_disponibilidad, "fecha_disponibilidad": fecha_disponibilidad}


def plazo_de_proveedor(codigo, proveedor, config, tablas):
    filas = [r for r in tablas["cotizaciones"] if r["codigo_unico"] == codigo and r["proveedor"] == proveedor]
    vacio = {"plazo_dias": None, "plazo_referencia_dias": None, "fecha_plazo": "", "vigencia_plazo": "",
             "naturaleza_plazo": "", "fuente_plazo": "", "fecha_actualizacion_plazo": "", "motivos": []}
    if not filas:
        return dict(vacio, motivos=["COTIZACION_FALTANTE"])
    r = unico(filas, "Cotización seleccionada " + codigo + "/" + proveedor)
    exigir(r["tipo_dato"] in {"SINTETICO", "DOCUMENTADO", "ESTIMACION"}, "Naturaleza de plazo inválida")
    valor = numero(r["plazo_entrega_dias"], "plazo de cotización", entero=True) if r["plazo_entrega_dias"].strip() else None
    inicio, fin = fecha(r["fecha"], "fecha cotización"), fecha(r["vigencia"], "vigencia cotización")
    exigir(inicio <= fin, "Vigencia de cotización invertida")
    evaluacion = fecha(config["fecha_evaluacion"], "fecha_evaluacion")
    motivos = []
    if evaluacion < inicio:
        motivos.append("COTIZACION_POSTERIOR_A_EVALUACION")
    elif evaluacion > fin:
        motivos.append("COTIZACION_VENCIDA")
    return dict(vacio, plazo_dias=None if motivos else valor, plazo_referencia_dias=valor,
                fecha_plazo=r["fecha"], vigencia_plazo=r["vigencia"], naturaleza_plazo=r["tipo_dato"],
                fuente_plazo=texto(r["fuente"], "fuente plazo"), fecha_actualizacion_plazo=r["fecha_actualizacion"], motivos=motivos)


def objeto_json(pares):
    resultado = {}
    for k, v in pares:
        exigir(k not in resultado, "Campo JSON repetido: " + k)
        resultado[k] = v
    return resultado


def cargar_integracion(configuracion=CONFIGURACION, raiz=RAIZ):
    """Carga fuentes sin escribir y conserva las huellas de sus bytes originales."""
    raiz, configuracion = Path(raiz).resolve(), Path(configuracion).resolve()
    with configuracion.open(encoding="utf-8-sig") as f:
        config = json.load(f, parse_float=str, object_pairs_hook=objeto_json)
    requeridas = {"version", "modo", "fecha_evaluacion", "fecha_stock", "max_antiguedad_stock_dias", "disponibilidad",
                  "permitir_pendientes_con_conteo_coincidente", "tipo_dias_plazo", "motivo_calendario", "calendario_laboral",
                  "proveedores", "demanda", "supuestos"}
    claves(config, requeridas | {"fuentes"}, requeridas)
    if "fuentes" in config:
        claves(config["fuentes"], FUENTES, FUENTES)
    exigir(type(config["version"]) is int and config["version"] == 1, "Versión no soportada")
    exigir(config["modo"] == "INTEGRACION", "Modo inválido: el modo de demostración se retiró el 12-11-2026")
    fecha(config["fecha_evaluacion"], "fecha_evaluacion")
    fecha(config["fecha_stock"], "fecha_stock")
    numero(config["max_antiguedad_stock_dias"], "max_antiguedad_stock_dias", entero=True)
    exigir(type(config["permitir_pendientes_con_conteo_coincidente"]) is bool, "Política de pendientes debe ser booleana")
    claves(config["disponibilidad"], {"politica", "motivo", "confirmaciones"}, {"politica", "motivo"})
    exigir(config["disponibilidad"]["politica"] in {"no_confirmada", "confirmadas"}, "Política de disponibilidad inválida")
    if "confirmaciones" in config["disponibilidad"]:
        exigir(config["disponibilidad"]["politica"] == "confirmadas" and isinstance(config["disponibilidad"]["confirmaciones"], dict), "Confirmaciones requieren política confirmadas")
    texto(config["disponibilidad"]["motivo"], "motivo de disponibilidad")
    exigir(config["tipo_dias_plazo"] in {"naturales", "habiles", "no_definido"}, "Tipo de días inválido")
    texto(config["motivo_calendario"], "motivo_calendario")
    exigir(isinstance(config["supuestos"], list) and bool(config["supuestos"]), "Declare los supuestos")
    for s in config["supuestos"]:
        texto(s, "supuesto")
    exigir(isinstance(config["proveedores"], dict) and bool(config["proveedores"]), "Seleccione proveedores por código")
    tablas, huellas = {}, {}
    for nombre, (ruta_rel, campos) in FUENTES.items():
        ruta_rel = texto(config.get("fuentes", {}).get(nombre, ruta_rel), "archivo " + nombre)
        ruta = raiz / ruta_rel
        tablas[nombre] = leer_csv(ruta, campos.split())
        huellas[nombre] = {"archivo": ruta_rel, "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()}
    # Identificadores y hechos aplicados deben ser únicos; rechazos repetidos nunca se suman.
    validar_ajustes(tablas)
    eq = equivalencias_hu17(tablas["depuracion"])
    exigir(set(config["disponibilidad"].get("confirmaciones", {})) <= set(config["proveedores"]), "Confirmaciones de códigos fuera de la selección")
    ruta_demanda = (raiz / texto(config["demanda"], "archivo de demanda")).resolve()
    demandas = cargar_demanda(ruta_demanda, eq)
    huellas["demanda"] = {"archivo": config["demanda"], "sha256": hashlib.sha256(ruta_demanda.read_bytes()).hexdigest()}
    huellas["configuracion"] = {"archivo": str(configuracion.relative_to(raiz)) if raiz in configuracion.parents else str(configuracion),
                                 "sha256": hashlib.sha256(configuracion.read_bytes()).hexdigest()}
    registros = []
    for codigo, proveedor in sorted(config["proveedores"].items()):
        exigir(normalizar(codigo, "REP", eq) == codigo, "Seleccione códigos canónicos en proveedores")
        texto(proveedor, "proveedor")
        stock = stock_de_corte(codigo, config, tablas)
        plazo = plazo_de_proveedor(codigo, proveedor, config, tablas)
        motivos = stock.pop("motivos") + plazo.pop("motivos")
        d = demandas.get(codigo)
        r = dict(stock, **plazo, codigo_unico=codigo, sistema_codigos="REP", proveedor=proveedor, motivos=motivos,
                 fecha_stock=config["fecha_stock"], fecha_evaluacion=config["fecha_evaluacion"],
                 max_antiguedad_stock_dias=config["max_antiguedad_stock_dias"], tipo_dias_plazo=config["tipo_dias_plazo"],
                 naturaleza_stock="FICTICIO", fuente_stock=huellas["conciliacion"]["archivo"],
                 politica_disponibilidad=config["disponibilidad"]["politica"], motivo_disponibilidad=config["disponibilidad"]["motivo"],
                 motivo_calendario=config["motivo_calendario"], modo=config["modo"],
                 naturaleza_demanda=d["tipo_dato"] if d else "", fuente_demanda=d["fuente"] if d else "",
                 fecha_emision_demanda=d["fecha_emision"] if d else "", inicio_horizonte=d["inicio_horizonte"] if d else "",
                 fin_horizonte=d["fin_horizonte"] if d else "", unidad_temporal=d["unidad_temporal"] if d else "",
                 metodo_demanda=d["metodo"] if d else "", demanda_prevista=d["tasa"] if d and d["tipo_pronostico"] == "TASA_CONSTANTE" else None,
                 serie_diaria=json.dumps({k: str(v) if v is not None else None for k, v in d["valores"].items()}, sort_keys=True) if d and d["tipo_pronostico"] == "SERIE_DIARIA" else "")
        registros.append((r, d))
    exigir(set(demandas) <= set(config["proveedores"]), "Hay pronósticos de códigos fuera de la selección")
    return config, registros, huellas


def mostrar(valor):
    if valor is None:
        return ""
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, list):
        return "|".join(valor)
    return str(valor)


def csv_texto(filas):
    campos = list(dict.fromkeys(k for r in filas for k in r))
    salida = io.StringIO(newline="")
    escritor = csv.DictWriter(salida, fieldnames=campos, lineterminator="\n")
    escritor.writeheader()
    escritor.writerows({k: mostrar(v) for k, v in r.items()} for r in filas)
    return salida.getvalue()


CAMPOS_VERIFICACION = ["codigo_unico", "descripcion", "proveedor", "fecha_evaluacion", "fecha_stock", "verificado",
                       "motivos", "stock_registrado", "conteo_fisico", "stock_ajustado", "reservas", "bloqueos",
                       "stock_disponible", "ajustes_mismo_corte", "ajustes_rechazados", "duplicados_excluidos",
                       "pendientes_hu17", "plazo_dias", "plazo_referencia_dias", "fecha_plazo", "vigencia_plazo",
                       "naturaleza_stock", "fuente_stock", "naturaleza_plazo", "fuente_plazo",
                       "politica_disponibilidad", "naturaleza_disponibilidad", "modo"]


def verificar(registros):
    """Una fila por repuesto: verificado solo si el stock disponible y el plazo quedaron sin motivo en contra."""
    filas = []
    for r, _ in registros:
        fila = {k: r.get(k) for k in CAMPOS_VERIFICACION if k != "verificado"}
        fila["motivos"] = sorted(set(r["motivos"]))
        fila["verificado"] = r["stock_disponible"] is not None and r["plazo_dias"] is not None
        filas.append({k: fila[k] for k in CAMPOS_VERIFICACION})
    return filas


def informe(config, filas, huellas):
    total, ok = len(filas), sum(1 for f in filas if f["verificado"])
    motivos = Counter(m for f in filas for m in f["motivos"])
    l = ["# HU-09: verificación de datos de inventario y plazo", "",
         "Generado por `src/hu-09/verificar_datos.py` (Sabrina Adrian Zelaya). Fecha de evaluación {}, corte de stock {}.".format(
             config["fecha_evaluacion"], config["fecha_stock"]), "",
         "## Resultado", "",
         "Repuestos verificados: **{} de {}**. Un repuesto queda verificado solo si su stock disponible y su plazo vigente "
         "se pudieron reconstruir sin ningún motivo en contra.".format(ok, total), "",
         "| Motivo | Repuestos |", "|---|---|"]
    l += ["| {} | {} |".format(m, n) for m, n in sorted(motivos.items())]
    l += ["", "## Detalle", "",
          "| Repuesto | Registrado | Conteo físico | Ajustado | Disponible | Plazo | Motivos |", "|---|---|---|---|---|---|---|"]
    for f in filas:
        l.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            f["codigo_unico"], mostrar(f["stock_registrado"]), mostrar(f["conteo_fisico"]), mostrar(f["stock_ajustado"]),
            mostrar(f["stock_disponible"]), mostrar(f["plazo_dias"]), ", ".join(f["motivos"]) or "ninguno"))
    l += ["", "## Supuestos", ""] + ["- " + s for s in config["supuestos"]]
    l += ["", "## Huellas de las entradas", "", "| Entrada | Archivo | SHA-256 |", "|---|---|---|"]
    l += ["| {} | `{}` | `{}` |".format(k, v["archivo"], v["sha256"]) for k, v in sorted(huellas.items())]
    l += ["", "Las fuentes de HU-17, HU-18 y HU-31 son FICTICIAS o SINTÉTICAS. Las alertas de reposición no usan esta "
          "verificación: salen de la lógica única del simulador (ver `docs/hu-09/LEEME.md`).", ""]
    return "\n".join(l)


def ejecutar(configuracion=CONFIGURACION, salida=None, reporte=None, raiz=RAIZ):
    raiz = Path(raiz).resolve()
    config, registros, huellas = cargar_integracion(configuracion, raiz)
    filas = verificar(registros)
    datos_base, reportes_base = raiz / "data/processed/hu-09", raiz / "reports/hu-09"
    salida = Path(salida).resolve() if salida is not None else datos_base
    reporte = Path(reporte).resolve() if reporte is not None else reportes_base / "VERIFICACION_DATOS_HU09.md"
    exigir(reporte.suffix.lower() == ".md", "El informe debe tener extensión .md")
    artefactos = {salida / "dataset_consolidado.csv": csv_texto(filas), reporte: informe(config, filas, huellas)}
    protegidos = {(raiz / h["archivo"]).resolve() for h in huellas.values()}
    for ruta in artefactos:
        exigir(ruta not in protegidos and ruta.with_name(ruta.name + ".tmp") not in protegidos, "La salida sobrescribiría una entrada")
        if raiz in ruta.parents:
            exigir(datos_base in ruta.parents or reportes_base in ruta.parents, "Salida fuera de HU-09")
    for ruta, contenido in artefactos.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(ruta.name + ".tmp")
        try:
            with temporal.open("w", encoding="utf-8", newline="") as f:
                f.write(contenido)
            temporal.replace(ruta)
        finally:
            if temporal.exists():
                temporal.unlink()
    return {"config": config, "filas": filas, "huellas": huellas, "artefactos": list(artefactos)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=CONFIGURACION)
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--reporte", type=Path)
    args = ap.parse_args()
    try:
        resultado = ejecutar(args.config, args.salida, args.reporte)
    except (ValueError, OSError, csv.Error, InvalidOperation) as error:
        print("HU-09: " + str(error), file=sys.stderr)
        return 1
    ok = sum(1 for f in resultado["filas"] if f["verificado"])
    print("Verificación de datos: {} de {} repuestos verificados".format(ok, len(resultado["filas"])))
    for ruta in resultado["artefactos"]:
        print(ruta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
