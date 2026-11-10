"""HU-06: comparar una canasta fija bajo escenarios cambiarios y logísticos.

Python >= 3.8, solo biblioteca estándar. No ejecuta ni altera otras historias.
Los importes se redondean por línea/componente con Decimal y ROUND_HALF_UP.
"""
import argparse
import copy
import csv
import hashlib
import io
import json
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "data/raw/hu-06/escenarios.json"
CENTAVO = Decimal("0.01")
COBERTURAS = {"flete_internacional", "seguro", "nacionalizacion", "comision", "flete_local"}
TIPOS_DATO = {"DOCUMENTADO", "ESTIMACION", "SINTETICO"}
ARCHIVOS = {
    "movimientos": {"id_movimiento", "fecha", "codigo_unico", "codigo_repuesto", "documento",
                    "cantidad", "precio_unitario_usd", "tipo_movimiento", "proveedor_cliente",
                    "origen", "fuente", "fecha_actualizacion"},
    "depuracion": {"id_movimiento", "fecha", "codigo_unico", "documento", "cantidad", "tipo_movimiento", "estado"},
    "cotizaciones": {"codigo_unico", "descripcion"},
    "costos_importacion": {"concepto", "valor_min", "valor_max", "unidad", "fecha_dato", "tipo_dato", "respaldo", "nota", "ruta_o_alcance"},
    "costos_complementarios": {"concepto", "valor", "unidad", "fecha_dato", "tipo_dato", "respaldo", "fuente", "fecha_actualizacion"},
    "tipos_cambio": {"id_serie", "fecha", "valor", "unidad", "tipo_dato", "fuente", "url", "nota", "fecha_actualizacion"},
}


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def claves(objeto, permitidas, requeridas=()):
    exigir(isinstance(objeto, dict), "Se esperaba un objeto JSON")
    exigir(not (set(objeto) - set(permitidas)), "Campos desconocidos: " + ", ".join(sorted(set(objeto) - set(permitidas))))
    exigir(set(requeridas) <= set(objeto), "Faltan campos: " + ", ".join(sorted(set(requeridas) - set(objeto))))


def texto(valor, nombre):
    exigir(isinstance(valor, str) and bool(valor.strip()), nombre + ": texto obligatorio")
    return valor.strip()


def numero(valor, nombre, cero=False, entero=False):
    exigir(not isinstance(valor, (bool, float)), nombre + ": use un decimal exacto (texto o entero)")
    try:
        n = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(nombre + ": número inválido") from None
    exigir(n.is_finite() and (n >= 0 if cero else n > 0), nombre + ": debe ser finito y " + ("no negativo" if cero else "positivo"))
    exigir(n.adjusted() <= 15 and n.as_tuple().exponent >= -8, nombre + ": máximo 16 dígitos enteros y 8 decimales")
    exigir(not entero or n == n.to_integral_value(), nombre + ": debe ser entero")
    return n


def dinero(valor):
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def fecha(valor, nombre):
    try:
        exigir(isinstance(valor, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor), nombre + ": fecha ISO AAAA-MM-DD requerida")
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ValueError(nombre + ": fecha ISO AAAA-MM-DD inválida") from None


def fecha_referencia(valor, limite):
    """Admite las fechas mensuales y rangos usados por HU-31, sin imputarlos."""
    texto(valor, "fecha_dato")
    partes = valor.split(" a ")
    exigir(len(partes) <= 2, "Rango de fecha inválido")
    limites = []
    for parte in partes:
        if re.fullmatch(r"\d{4}-\d{2}", parte):
            limites.append(fecha(parte + "-01", "fecha_dato"))
        else:
            limites.append(fecha(parte, "fecha_dato"))
    exigir(limites == sorted(limites) and limites[-1] <= limite, "Referencia posterior a la fecha de análisis o rango invertido")


def cargar_csv(ruta, requeridas):
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        exigir(requeridas <= set(lector.fieldnames or []), str(ruta) + ": faltan columnas requeridas")
        filas = list(lector)
    exigir(bool(filas), str(ruta) + ": archivo sin registros")
    exigir(all(None not in r and all(v is not None for v in r.values()) for r in filas), str(ruta) + ": fila CSV mal formada")
    return filas


def unico(filas, mensaje):
    exigir(len(filas) == 1, mensaje + ": se esperaba exactamente una referencia")
    return filas[0]


def nombre_archivo(ruta, raiz):
    try:
        return ruta.relative_to(raiz).as_posix()
    except ValueError:
        return str(ruta)


def parametro(especificacion, nombre, limite):
    claves(especificacion, {"valor", "motivo", "fecha_dato"}, {"valor", "motivo", "fecha_dato"})
    texto(especificacion["motivo"], nombre + ".motivo")
    fecha_referencia(especificacion["fecha_dato"], limite)
    return numero(especificacion["valor"], nombre, entero=nombre == "contenedores")


def construir_canasta(config, tablas):
    seleccion = config["canasta"]
    claves(seleccion, {"documentos", "incluir_pendientes"}, {"documentos", "incluir_pendientes"})
    docs = seleccion["documentos"]
    exigir(isinstance(docs, list) and bool(docs) and all(isinstance(d, str) and d.startswith("OC-") and len(d) > 3 for d in docs), "Seleccione documentos OC- de compra")
    exigir(len(set(docs)) == len(docs), "Documentos repetidos en la selección")
    exigir(type(seleccion["incluir_pendientes"]) is bool, "incluir_pendientes debe ser booleano")
    estados = {}
    for fila in tablas["depuracion"]:
        ident = texto(fila["id_movimiento"], "id_movimiento HU-17")
        exigir(ident not in estados, "id_movimiento repetido en HU-17: " + ident)
        exigir(fila["estado"] in {"ORIGINAL", "DUPLICADO", "PENDIENTE_REVISION"}, "Estado de depuración desconocido")
        estados[ident] = fila
    descripciones = {}
    for r in tablas["cotizaciones"]:
        codigo = texto(r["codigo_unico"], "codigo_unico cotización")
        descripcion = texto(r["descripcion"], "descripcion cotización")
        exigir(codigo not in descripciones or descripciones[codigo] == descripcion, "Descripciones contradictorias para " + codigo)
        descripciones[codigo] = descripcion
    filas, excluidos, vistos = [], [], set()
    for r in tablas["movimientos"]:
        if r["documento"] not in docs:
            continue
        ident = texto(r["id_movimiento"], "id_movimiento")
        exigir(ident not in vistos, "id_movimiento repetido en HU-30: " + ident)
        vistos.add(ident)
        exigir(r["tipo_movimiento"] == "ENTRADA", "Documento de compra con movimiento que no es ENTRADA")
        exigir(fecha(r["fecha"], "fecha compra") <= fecha(config["fecha_analisis"], "fecha_analisis"), "Compra posterior al análisis")
        cantidad = numero(r["cantidad"], "cantidad", entero=True)
        precio = numero(r["precio_unitario_usd"], "precio_unitario_usd")
        exigir(r["codigo_unico"] in descripciones, "Repuesto sin descripción en HU-31: " + r["codigo_unico"])
        if ident in estados:
            dep = estados[ident]
            exigir(all(r[c] == dep[c] for c in ("fecha", "codigo_unico", "documento", "tipo_movimiento"))
                   and cantidad == numero(dep["cantidad"], "cantidad HU-17", entero=True), "HU-17 y HU-30 no coinciden para " + ident)
            estado = dep["estado"]
        else:
            exigir(r["origen"] == "SINTETICO", "Movimiento del equipo sin clasificación HU-17: " + ident)
            estado = "SINTETICO_SIN_CLASIFICACION_HU17"
        if estado == "DUPLICADO" or (estado == "PENDIENTE_REVISION" and not seleccion["incluir_pendientes"]):
            excluidos.append({"id_movimiento": ident, "documento": r["documento"], "estado": estado})
            continue
        exigir(r["origen"] in {"SINTETICO", "EQUIPO_FICTICIO"}, "Naturaleza del movimiento no soportada: " + r["origen"])
        filas.append({"id_movimiento": ident, "documento": r["documento"], "codigo_unico": r["codigo_unico"],
                      "descripcion": descripciones[r["codigo_unico"]], "proveedor": texto(r["proveedor_cliente"], "proveedor"),
                      "fecha": r["fecha"], "cantidad": cantidad, "precio_unitario_usd": precio,
                      "mercancia_usd": dinero(cantidad * precio), "unidad": "USD por unidad", "tipo_dato": "SINTETICO",
                      "estado_hu17": estado, "fuente": texto(r["fuente"], "fuente compra"),
                      "fecha_actualizacion": r["fecha_actualizacion"], "origen": r["origen"]})
    exigir(bool(filas), "La canasta quedó vacía después de excluir movimientos")
    exigir(set(docs) == {r["documento"] for r in filas}, "Hay documentos inexistentes o sin líneas válidas en la selección")
    return sorted(filas, key=lambda r: (r["documento"], r["id_movimiento"])), excluidos


def cobertura(concepto):
    if concepto.startswith("flete y seguro implícito (CIF-FOB), origen China, medio "):
        return {"flete_internacional", "seguro"}
    if concepto in {"FCL 20GP maritimo", "FCL 40GP maritimo", "LCL maritimo", "aereo", "express"}:
        return {"flete_internacional"}
    mapa = {"seguro de carga": "seguro", "nacionalizacion y agente aduanero": "nacionalizacion",
            "comision de gestion de importacion": "comision",
            "flete terrestre Arica/Iquique -> Santa Cruz": "flete_local"}
    exigir(concepto in mapa, "Concepto sin cobertura monetaria soportada (posible índice): " + concepto)
    return {mapa[concepto]}


def unidad(valor):
    """La anotación (% del FOB) del INE es informativa, no otra tarifa."""
    normalizada = re.sub(r" \(\d+(?:\.\d+)?% del FOB\)$", "", valor)
    if normalizada == "% del CIF":
        return "USD", "CIF"
    m = re.fullmatch(r"(USD|BOB)(?: por (kg|m3|contenedor))?", normalizada)
    exigir(m is not None, "Unidad incompatible o no monetaria: " + valor)
    return m[1], {None: "importe", "kg": "peso_kg", "m3": "volumen_m3", "contenedor": "contenedores"}[m[2]]


def referencia(spec, tablas, limite):
    claves(spec, {"id", "origen", "concepto", "campo", "valor", "unidad", "cubre", "motivo", "fecha_dato"}, {"id", "origen", "concepto"})
    texto(spec["id"], "id logístico")
    concepto = texto(spec["concepto"], "concepto")
    origen = spec["origen"]
    if origen == "supuesto":
        claves(spec, {"id", "origen", "concepto", "valor", "unidad", "cubre", "motivo", "fecha_dato"},
               {"valor", "unidad", "cubre", "motivo", "fecha_dato"})
        cubre = spec["cubre"]
        exigir(isinstance(cubre, list) and bool(cubre) and all(isinstance(c, str) for c in cubre)
               and len(cubre) == len(set(cubre)) and set(cubre) <= COBERTURAS, "Cobertura de supuesto inválida")
        r = {"valor": spec["valor"], "unidad": spec["unidad"], "cubre": set(cubre), "tipo_dato": "SINTETICO",
             "fuente": "Supuesto explícito de configuración HU-06", "respaldo": "Sin comprobante real",
             "fecha_dato": spec["fecha_dato"], "fecha_actualizacion": "", "nota": texto(spec["motivo"], "motivo del supuesto"),
             "archivo": "configuracion"}
    else:
        exigir(origen in {"importacion", "complementario"}, "Origen logístico desconocido")
        claves(spec, {"id", "origen", "concepto", "campo"}, {"id", "origen", "concepto"})
        archivo = "costos_importacion" if origen == "importacion" else "costos_complementarios"
        fuente = unico([r for r in tablas[archivo] if r["concepto"] == concepto], concepto)
        exigir(fuente["tipo_dato"] in TIPOS_DATO, "Referencia pendiente o naturaleza inválida: " + concepto)
        campo = spec.get("campo", "valor_min" if origen == "importacion" else "valor")
        exigir(campo in ({"valor_min", "valor_max"} if origen == "importacion" else {"valor"}), "Campo de tarifa inválido")
        if origen == "importacion":
            exigir(numero(fuente["valor_min"], "valor_min", cero=True) <= numero(fuente["valor_max"], "valor_max", cero=True), "Rango de tarifa invertido")
        r = {"valor": fuente[campo], "unidad": fuente["unidad"], "cubre": cobertura(concepto), "tipo_dato": fuente["tipo_dato"],
             "fuente": fuente.get("fuente") or fuente["respaldo"], "respaldo": fuente["respaldo"],
             "fecha_dato": fuente["fecha_dato"], "fecha_actualizacion": fuente.get("fecha_actualizacion", ""),
             "nota": fuente.get("nota", "") + ("; alcance: " + fuente["ruta_o_alcance"] if origen == "importacion" else ""),
             "archivo": archivo}
    fecha_referencia(r["fecha_dato"], limite)
    texto(r["fuente"], "fuente logística")
    r.update(id=spec["id"], concepto=concepto, tarifa=numero(r.pop("valor"), "tarifa", cero=True))
    r["moneda"], r["factor"] = unidad(r["unidad"])
    if r["factor"] == "CIF":
        exigir(not (r["cubre"] & {"flete_internacional", "flete_local"}), "Un flete no puede ser un porcentaje del CIF en este modelo")
        if "seguro" in r["cubre"]:
            exigir(r["cubre"] == {"seguro"} and r["tarifa"] < 100, "Seguro sobre CIF debe ser independiente y menor al 100%")
    return r


def cambio(spec, tablas, limite):
    claves(spec, {"origen", "id_serie", "fecha", "valor", "motivo"}, {"origen"})
    if spec["origen"] == "serie":
        claves(spec, {"origen", "id_serie", "fecha"}, {"id_serie", "fecha"})
        exigir(fecha(spec["fecha"], "fecha cambio") <= limite, "Tipo de cambio posterior al análisis")
        r = dict(unico([r for r in tablas["tipos_cambio"] if r["id_serie"] == spec["id_serie"] and r["fecha"] == spec["fecha"]], "Tipo de cambio sin observación exacta"))
        exigir(r["unidad"] == "Bs por 1 USD", "Unidad incompatible del tipo de cambio")
        exigir(r["tipo_dato"] in TIPOS_DATO, "Tipo de cambio pendiente o naturaleza inválida")
        r["archivo"] = "tipos_cambio"
    else:
        exigir(spec["origen"] == "supuesto", "Origen de tipo de cambio desconocido")
        claves(spec, {"origen", "fecha", "valor", "motivo"}, {"fecha", "valor", "motivo"})
        exigir(fecha(spec["fecha"], "fecha cambio") <= limite, "Tipo de cambio supuesto posterior al análisis")
        r = {"id_serie": "SUPUESTO", "fecha": spec["fecha"], "valor": spec["valor"], "unidad": "Bs por 1 USD",
             "tipo_dato": "SINTETICO", "fuente": "Supuesto explícito de configuración HU-06", "url": "",
             "nota": texto(spec["motivo"], "motivo cambio"), "fecha_actualizacion": "", "archivo": "configuracion"}
    texto(r["fuente"], "fuente cambio")
    r["valor"] = numero(r["valor"], "tipo de cambio")
    return r


def aplicar_modificaciones(canasta, modificaciones):
    exigir(isinstance(modificaciones, list), "modificaciones debe ser una lista")
    lineas = {r["id_movimiento"]: dict(r, cantidad_base=r["cantidad"], precio_base_usd=r["precio_unitario_usd"], motivo_modificacion="") for r in canasta}
    vistos = set()
    for m in modificaciones:
        claves(m, {"id_movimiento", "cantidad", "precio_unitario_usd", "motivo"}, {"id_movimiento", "motivo"})
        ident = m["id_movimiento"]
        exigir(isinstance(ident, str) and ident in lineas and ident not in vistos, "Modificación repetida o línea inexistente")
        exigir("cantidad" in m or "precio_unitario_usd" in m, "Modificación sin precio ni cantidad")
        vistos.add(ident)
        r = lineas[ident]
        r["motivo_modificacion"] = texto(m["motivo"], "motivo de modificación")
        if "cantidad" in m:
            r["cantidad"] = numero(m["cantidad"], "cantidad modificada", entero=True)
        if "precio_unitario_usd" in m:
            r["precio_unitario_usd"] = numero(m["precio_unitario_usd"], "precio modificado")
        r["mercancia_usd"] = dinero(r["cantidad"] * r["precio_unitario_usd"])
    return list(lineas.values())


def calcular_logistica(refs, parametros, mercancia, incluidos):
    cubiertos = set(incluidos)
    exigir(len(cubiertos) == len(incluidos) and cubiertos <= COBERTURAS, "Componentes incluidos en precio inválidos")
    for r in refs:
        exigir(not (cubiertos & r["cubre"]), "Doble contabilización: " + ", ".join(sorted(cubiertos & r["cubre"])))
        cubiertos.update(r["cubre"])
    exigir(cubiertos == COBERTURAS, "Faltan componentes del alcance: " + ", ".join(sorted(COBERTURAS - cubiertos)))
    exigir(not (set(incluidos) & {"nacionalizacion", "comision", "flete_local"}) or not any(r["factor"] == "CIF" for r in refs),
           "CIF no identificable: hay gastos posteriores al CIF incluidos en precio sin desglose")
    fijos = []
    for r in refs:
        if r["factor"] == "CIF":
            continue
        factor = Decimal(1)
        if r["factor"] != "importe":
            exigir(r["factor"] in parametros, "Falta parámetro explícito: " + r["factor"])
            factor = parametros[r["factor"]]
        fijos.append(dict(r, base_calculo=factor, importe_origen=dinero(r["tarifa"] * factor)))
    internacionales = [r for r in fijos if r["cubre"] & {"flete_internacional", "seguro"}]
    exigir(all(r["moneda"] == "USD" for r in internacionales) or not any(r["factor"] == "CIF" for r in refs), "CIF requiere flete y seguro en USD; no mezcle bases monetarias")
    cif = mercancia + sum((r["importe_origen"] for r in internacionales), Decimal(0))
    porcentuales = [r for r in refs if r["factor"] == "CIF"]
    seguro = next((r for r in porcentuales if "seguro" in r["cubre"]), None)
    importes = {}
    if seguro:
        # S = tasa * (M + F + S), no tasa * (M + F).
        importes[seguro["id"]] = dinero(cif * seguro["tarifa"] / (Decimal(100) - seguro["tarifa"]))
        cif += importes[seguro["id"]]
    calculados = {r["id"]: r for r in fijos}
    for r in porcentuales:
        importe = importes.get(r["id"], dinero(cif * r["tarifa"] / 100))
        calculados[r["id"]] = dict(r, base_calculo=cif, importe_origen=importe)
    return [calculados[r["id"]] for r in refs], cif


def evaluar(config, raiz=RAIZ, configuracion=None):
    """Evalúa sin escribir. Devuelve datos, CSV e informe con trazabilidad."""
    with localcontext() as contexto:
        contexto.prec = 50
        return _evaluar(config, Path(raiz).resolve(), configuracion)


def _evaluar(config, raiz, configuracion):
    claves(config, {"version", "fecha_analisis", "descripcion", "archivos", "canasta", "incluidos_en_precio", "parametros_logisticos", "supuestos", "escenarios"},
           {"version", "fecha_analisis", "descripcion", "archivos", "canasta", "incluidos_en_precio", "parametros_logisticos", "supuestos", "escenarios"})
    exigir(type(config["version"]) is int and config["version"] == 1, "Versión de configuración no soportada")
    limite = fecha(config["fecha_analisis"], "fecha_analisis")
    texto(config["descripcion"], "descripcion")
    exigir(isinstance(config["supuestos"], list) and bool(config["supuestos"]), "Declare los supuestos del modelo")
    for s in config["supuestos"]:
        texto(s, "supuesto")
    exigir(isinstance(config["incluidos_en_precio"], list) and all(isinstance(c, str) for c in config["incluidos_en_precio"]), "incluidos_en_precio debe ser una lista de componentes")
    claves(config["archivos"], ARCHIVOS, ARCHIVOS)
    tablas, fuentes = {}, {}
    for nombre, requeridas in ARCHIVOS.items():
        ruta = (raiz / texto(config["archivos"][nombre], "archivo " + nombre)).resolve()
        tablas[nombre] = cargar_csv(ruta, requeridas)
        fuentes[nombre] = {"ruta": ruta, "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest(), "archivo": config["archivos"][nombre]}
    # El JSON normalizado hace que evaluar() también sea reproducible sin archivo.
    contenido_config = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fuentes["configuracion"] = {"ruta": Path(configuracion).resolve() if configuracion else None,
                                 "archivo": nombre_archivo(Path(configuracion).resolve(), raiz) if configuracion else "configuracion en memoria",
                                 "sha256": hashlib.sha256(contenido_config).hexdigest()}
    canasta, excluidos = construir_canasta(config, tablas)
    escenarios = config["escenarios"]
    exigir(isinstance(escenarios, list) and len(escenarios) >= 3, "Se requiere un base y al menos dos alternativas")
    ids = set()
    for s in escenarios:
        claves(s, {"id", "tipo", "descripcion", "tipo_cambio", "logistica", "cambios_logistica", "parametros_logisticos", "modificaciones"}, {"id", "tipo", "descripcion"})
        ident = texto(s["id"], "id escenario")
        exigir(re.fullmatch(r"[A-Z][A-Z0-9_]*", ident) and ident not in ids, "ID de escenario inválido o repetido")
        ids.add(ident)
        exigir(s["tipo"] in {"BASE", "CAMBIARIA", "LOGISTICA", "COMBINADO"}, "Tipo de escenario desconocido")
        texto(s["descripcion"], "descripcion escenario")
    bases = [s for s in escenarios if s["tipo"] == "BASE"]
    exigir(len(bases) == 1 and {"CAMBIARIA", "LOGISTICA"} <= {s["tipo"] for s in escenarios}, "Se requiere exactamente un BASE y alternativas CAMBIARIA y LOGISTICA")
    base = bases[0]
    exigir("tipo_cambio" in base and "logistica" in base and not (set(base) & {"modificaciones", "cambios_logistica", "parametros_logisticos"}), "BASE debe declarar cambio y logística, con cantidades y precios originales")
    exigir(isinstance(base["logistica"], list) and bool(base["logistica"]), "Logística base vacía")
    parametros_base = config["parametros_logisticos"]
    claves(parametros_base, {"peso_kg", "volumen_m3", "contenedores"})
    detalle, comparacion, evaluados = [], [], []
    for s in [base] + [s for s in escenarios if s is not base]:
        tipo = s["tipo"]
        if tipo == "CAMBIARIA":
            exigir("tipo_cambio" in s and not (set(s) & {"logistica", "cambios_logistica", "parametros_logisticos", "modificaciones"}), "CAMBIARIA solo puede modificar el tipo de cambio")
        if tipo == "LOGISTICA":
            exigir(not (set(s) & {"tipo_cambio", "modificaciones", "logistica"}), "LOGISTICA conserva cambio, cantidades y precios; use cambios_logistica")
        exigir(s is base or "logistica" not in s, "Las alternativas heredan logística; use cambios_logistica")
        tc = cambio(s.get("tipo_cambio", base["tipo_cambio"]), tablas, limite)
        specs = copy.deepcopy(base["logistica"])
        exigir(all(isinstance(r, dict) for r in specs), "Cada referencia logística debe ser un objeto JSON")
        base_ids = [r.get("id") for r in specs]
        exigir(all(isinstance(i, str) for i in base_ids) and len(set(base_ids)) == len(base_ids), "IDs logísticos repetidos o inválidos")
        cambios = s.get("cambios_logistica", [])
        exigir(isinstance(cambios, list), "cambios_logistica debe ser una lista")
        reemplazos = set()
        for reemplazo in cambios:
            exigir(isinstance(reemplazo, dict) and isinstance(reemplazo.get("id"), str), "Reemplazo logístico inválido")
            ident = reemplazo["id"]
            exigir(ident in base_ids and ident not in reemplazos, "Reemplazo logístico repetido o desconocido")
            reemplazos.add(ident)
            specs[base_ids.index(ident)] = reemplazo
        parametros_spec = copy.deepcopy(parametros_base)
        claves(s.get("parametros_logisticos", {}), {"peso_kg", "volumen_m3", "contenedores"})
        parametros_spec.update(s.get("parametros_logisticos", {}))
        parametros = {k: parametro(v, k, limite) for k, v in parametros_spec.items()}
        lineas = aplicar_modificaciones(canasta, s.get("modificaciones", []))
        refs = [referencia(r, tablas, limite) for r in specs]
        if any(r["cantidad"] != r["cantidad_base"] for r in lineas):
            factores = {r["factor"] for r in refs} & {"peso_kg", "volumen_m3", "contenedores"}
            exigir(factores <= set(s.get("parametros_logisticos", {})), "Al modificar cantidades declare de nuevo los parámetros físicos utilizados")
        mercancia = sum((r["mercancia_usd"] for r in lineas), Decimal(0))
        logistica, cif = calcular_logistica(refs, parametros, mercancia, config["incluidos_en_precio"])
        for r in lineas:
            detalle.append({"escenario_id": s["id"], "tipo_escenario": tipo, "clase": "MERCANCIA", "componente": r["descripcion"],
                            "id_linea": r["id_movimiento"], "documento": r["documento"], "codigo_unico": r["codigo_unico"],
                            "cantidad": r["cantidad"], "precio_unitario_usd": r["precio_unitario_usd"],
                            "cantidad_base": r["cantidad_base"], "precio_base_usd": r["precio_base_usd"],
                            "unidad": r["unidad"], "tarifa": r["precio_unitario_usd"], "base_calculo": r["cantidad"], "moneda": "USD",
                            "importe_origen": r["mercancia_usd"], "importe_bob": dinero(r["mercancia_usd"] * tc["valor"]),
                            "fuente": r["fuente"], "archivo": "movimientos", "fecha_dato": r["fecha"],
                            "fecha_actualizacion": r["fecha_actualizacion"], "tipo_dato": "SINTETICO", "cubre": "mercancia",
                            "nota": "estado HU-17: " + r["estado_hu17"], "motivo_modificacion": r["motivo_modificacion"]})
        for r in logistica:
            nota = r["nota"]
            if r["factor"] in parametros_spec:
                p = parametros_spec[r["factor"]]
                nota += "; parámetro SINTETICO " + r["factor"] + "=" + str(parametros[r["factor"]]) + ": " + p["motivo"] + " (" + p["fecha_dato"] + ")"
            detalle.append({"escenario_id": s["id"], "tipo_escenario": tipo, "clase": "LOGISTICA", "componente": r["concepto"],
                            "id_linea": r["id"], "unidad": r["unidad"], "tarifa": r["tarifa"], "base_calculo": r["base_calculo"],
                            "moneda": r["moneda"], "importe_origen": r["importe_origen"],
                            "importe_bob": dinero(r["importe_origen"] * tc["valor"]) if r["moneda"] == "USD" else r["importe_origen"],
                            "fuente": r["fuente"], "respaldo": r["respaldo"], "archivo": r["archivo"], "fecha_dato": r["fecha_dato"],
                            "fecha_actualizacion": r["fecha_actualizacion"], "tipo_dato": r["tipo_dato"], "cubre": "|".join(sorted(r["cubre"])),
                            "nota": nota, "motivo_modificacion": ""})
        detalle.append({"escenario_id": s["id"], "tipo_escenario": tipo, "clase": "TIPO_CAMBIO", "componente": tc["id_serie"],
                        "unidad": tc["unidad"], "tarifa": tc["valor"], "moneda": "BOB/USD", "fuente": tc["fuente"],
                        "respaldo": tc["url"], "archivo": tc["archivo"], "fecha_dato": tc["fecha"],
                        "fecha_actualizacion": tc["fecha_actualizacion"], "tipo_dato": tc["tipo_dato"], "nota": tc["nota"]})
        filas = [r for r in detalle if r["escenario_id"] == s["id"]]
        mercancia_bob = sum((r["importe_bob"] for r in filas if r["clase"] == "MERCANCIA"), Decimal(0))
        logistica_bob = sum((r["importe_bob"] for r in filas if r["clase"] == "LOGISTICA"), Decimal(0))
        total = mercancia_bob + logistica_bob
        exigir(total > 0, "El total base y los escenarios deben ser positivos después del redondeo")
        fila = {"escenario_id": s["id"], "tipo": tipo, "descripcion": s["descripcion"], "lineas": len(lineas),
                "unidades": sum(r["cantidad"] for r in lineas), "mercancia_usd": mercancia,
                "logistica_usd": sum((r["importe_origen"] for r in logistica if r["moneda"] == "USD"), Decimal(0)),
                "logistica_bob_origen": sum((r["importe_origen"] for r in logistica if r["moneda"] == "BOB"), Decimal(0)),
                "cif_simulado_usd": cif if all(r["moneda"] == "USD" for r in logistica if r["cubre"] & {"flete_internacional", "seguro"}) else "",
                "tipo_cambio": tc["valor"], "serie_cambio": tc["id_serie"], "fecha_cambio": tc["fecha"],
                "mercancia_bob": mercancia_bob, "logistica_convertida_bob": logistica_bob, "total_bob": total,
                "diferencia_bob": Decimal("0.00"), "diferencia_pct": Decimal("0.00"), "naturaleza_resultado": "MIXTO_SIMULADO"}
        if comparacion:
            fila["diferencia_bob"] = total - comparacion[0]["total_bob"]
            fila["diferencia_pct"] = dinero(fila["diferencia_bob"] / comparacion[0]["total_bob"] * 100)
            if tipo == "CAMBIARIA":
                exigir(tc["valor"] != comparacion[0]["tipo_cambio"], "La alternativa CAMBIARIA debe cambiar el valor del tipo de cambio")
            if tipo == "LOGISTICA":
                exigir(specs != base["logistica"] or parametros_spec != parametros_base, "La alternativa LOGISTICA debe cambiar la logística")
                firma = lambda gastos: [(r["id"], r["moneda"], r["importe_origen"]) for r in gastos]
                exigir(firma(logistica) != firma(evaluados[0]["logistica"]), "La alternativa LOGISTICA debe cambiar algún costo efectivo")
        comparacion.append(fila)
        evaluados.append({"escenario": s, "lineas": lineas, "logistica": logistica, "parametros": parametros_spec})
    for r in canasta:
        r["archivo_fuente"] = fuentes["movimientos"]["archivo"]
        r["sha256_fuente"] = fuentes["movimientos"]["sha256"]
    for r in detalle:
        f = fuentes[r.pop("archivo")]
        r["archivo_fuente"], r["sha256_fuente"] = f["archivo"], f["sha256"]
    return {"config": copy.deepcopy(config), "canasta": canasta, "excluidos": excluidos, "comparacion": comparacion,
            "detalle": detalle, "fuentes": fuentes, "evaluados": evaluados}


def csv_texto(filas):
    campos = list(dict.fromkeys(k for r in filas for k in r))
    salida = io.StringIO(newline="")
    escritor = csv.DictWriter(salida, fieldnames=campos, lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(filas)
    return salida.getvalue()


def grafico(resultado):
    filas = resultado["comparacion"]
    maximo = max(r["total_bob"] for r in filas)
    partes = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{}" viewBox="0 0 900 {}" role="img" aria-labelledby="titulo desc">'.format(100 + len(filas) * 65, 100 + len(filas) * 65),
              '<title id="titulo">HU-06: costo total simulado por escenario (BOB)</title>',
              '<desc id="desc">' + escape("; ".join(r["escenario_id"] + ": " + str(r["total_bob"]) + " BOB" for r in filas)) + '</desc>',
              '<rect width="100%" height="100%" fill="white"/>',
              '<g font-family="sans-serif" font-size="15" fill="#172b4d"><text x="20" y="30">Costo total simulado (BOB) · datos mixtos y supuestos</text>']
    for i, r in enumerate(filas):
        y = 60 + i * 65
        ancho = dinero(r["total_bob"] / maximo * 500)
        partes.append('<text x="20" y="{}">{}</text><rect x="175" y="{}" width="{}" height="28" fill="{}"/><text x="690" y="{}">{} BOB</text>'.format(
            y + 20, escape(r["escenario_id"]), y, ancho, "#245b85" if r["tipo"] == "BASE" else "#37806b", y + 20, r["total_bob"]))
    partes.append('</g></svg>\n')
    return "\n".join(partes)


def celda(valor):
    return str(valor).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def informe(resultado):
    c = resultado["config"]
    base = resultado["comparacion"][0]
    lineas = ["# HU-06: comparar escenarios cambiarios y logísticos", "", "Fecha de análisis: " + c["fecha_analisis"], "",
              "**Resultado MIXTO_SIMULADO.** Los precios y cantidades son ficticios. Las referencias conservan la clasificación de HU-31/HU-32; los parámetros físicos y gastos complementarios son supuestos o datos sintéticos.",
              "", "## Pedido analizado", "", c["descripcion"], "",
              "Se conservan {} líneas válidas, {} productos distintos y {} unidades; mercancía: {} USD.".format(len(resultado["canasta"]), len({r["codigo_unico"] for r in resultado["canasta"]}), base["unidades"], base["mercancia_usd"]),
              "", "| Orden | Movimiento | Repuesto | Cantidad | Precio USD | Mercancía USD |", "|---|---|---|---:|---:|---:|"]
    for r in resultado["canasta"]:
        lineas.append("| " + " | ".join(celda(r[k]) for k in ("documento", "id_movimiento", "codigo_unico", "cantidad", "precio_unitario_usd", "mercancia_usd")) + " |")
    lineas += ["", "Exclusiones por HU-17: " + ("; ".join(r["id_movimiento"] + " (" + r["documento"] + ", " + r["estado"] + ")" for r in resultado["excluidos"]) or "ninguna") + ".",
               "", "## Comparación", "", "| Escenario | TC BOB/USD | Mercancía USD | Logística USD | Logística BOB de origen | Total BOB | Diferencia BOB | Diferencia % |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in resultado["comparacion"]:
        lineas.append("| " + " | ".join(celda(r[k]) for k in ("escenario_id", "tipo_cambio", "mercancia_usd", "logistica_usd", "logistica_bob_origen", "total_bob", "diferencia_bob", "diferencia_pct")) + " |")
    lineas += ["", "![Comparación de costos totales](comparacion_escenarios.svg)", ""]
    for r in resultado["comparacion"]:
        lineas.append("- **{} ({}):** {} Referencia {} del {}.".format(r["escenario_id"], r["tipo"], r["descripcion"], r["serie_cambio"], r["fecha_cambio"]))
    lineas += ["", "## Impacto cambiario", ""]
    for r in resultado["comparacion"]:
        if r["tipo"] == "CAMBIARIA":
            lineas.append("{} mantiene mercancía y parámetros logísticos del base. Cambiar de {} a {} BOB/USD produce una diferencia de {} BOB ({}%). Los gastos originalmente en BOB permanecen sin conversión.".format(r["escenario_id"], base["tipo_cambio"], r["tipo_cambio"], r["diferencia_bob"], r["diferencia_pct"]))
    lineas += ["", "## Impacto logístico", ""]
    for r in resultado["comparacion"]:
        if r["tipo"] == "LOGISTICA":
            lineas.append("{} mantiene productos, cantidades, precios y cambio del base. La logística en USD pasa de {} a {}; el efecto total es {} BOB ({}%). Los porcentajes sobre CIF se recalculan cuando cambia su base.".format(r["escenario_id"], base["logistica_usd"], r["logistica_usd"], r["diferencia_bob"], r["diferencia_pct"]))
    lineas += ["", "## Desglose logístico y trazabilidad", "", "| Escenario | Concepto | Tarifa | Unidad original | Base aplicada | Moneda | Importe | Naturaleza de referencia | Fecha del dato |", "|---|---|---:|---|---:|---|---:|---|---|"]
    for r in resultado["detalle"]:
        if r["clase"] == "LOGISTICA":
            lineas.append("| " + " | ".join(celda(r[k]) for k in ("escenario_id", "componente", "tarifa", "unidad", "base_calculo", "moneda", "importe_origen", "tipo_dato", "fecha_dato")) + " |")
    lineas += ["", "La naturaleza corresponde a la referencia: un importe derivado de tarifa DOCUMENTADO/ESTIMACION y peso supuesto sigue siendo una simulación. El detalle CSV conserva fuente, respaldo, alcance, fecha, unidad y SHA-256 del archivo de entrada.",
               "", "## Parámetros físicos y modificaciones expresas", ""]
    for e in resultado["evaluados"]:
        lineas.append("- **" + e["escenario"]["id"] + ":** " + ("; ".join(k + "=" + str(v["valor"]) + " [SINTETICO, " + v["fecha_dato"] + "]: " + v["motivo"] for k, v in e["parametros"].items()) or "sin parámetros físicos"))
        for r in e["lineas"]:
            if r["motivo_modificacion"]:
                lineas.append("  - Movimiento {}: cantidad {} → {}; precio USD {} → {}. Motivo: {}.".format(r["id_movimiento"], r["cantidad_base"], r["cantidad"], r["precio_base_usd"], r["precio_unitario_usd"], r["motivo_modificacion"]))
    lineas += ["", "Componentes declarados incluidos en el precio: " + (", ".join(c["incluidos_en_precio"]) or "ninguno") + ".", "", "## Fórmulas y redondeo", "",
               "Mercancía USD = suma de cantidad × precio de cada línea. Cada línea y cada gasto se redondean a 0,01 en su moneda con Decimal y ROUND_HALF_UP. Cada importe USD se convierte y redondea individualmente a BOB; los importes BOB no se convierten. El total es la suma de esas líneas en BOB, por lo que coincide exactamente con el detalle y puede diferir en centavos de convertir el agregado USD una sola vez.", "",
               "CIF simulado = mercancía + flete internacional + seguro. Si el seguro es s% del propio CIF: seguro = (mercancía + flete) × s / (100 − s), redondeado antes de calcular los demás porcentajes. El transporte local se agrega después del CIF. No se permite sumar otro seguro cuando el flete ya lo incluye.", "",
               "Diferencia BOB = total del escenario − total base (positiva: mayor costo; negativa: ahorro). Diferencia % = diferencia / total base × 100, redondeada a dos decimales. El base tiene diferencia cero.", "", "## Supuestos y limitaciones", ""]
    lineas.extend("- " + s for s in c["supuestos"])
    lineas += ["- No se rellenan tipos de cambio faltantes ni se usan índices como importes. Un costo pendiente o un parámetro físico ausente impide generar resultados nuevos.",
               "- Se cubren los cinco componentes del modelo (flete internacional, seguro, nacionalización/agente, comisión y flete local). Eso no certifica que estén cubiertos todos los gastos o tributos de una importación real.",
               "- Los escenarios obligatorios conservan la canasta. Las modificaciones expresas se admiten en COMBINADO y quedan registradas; modificar cantidades exige redeclarar los parámetros físicos usados.",
               "", "## Fuentes utilizadas", ""]
    usados = {(r["archivo_fuente"], r.get("fuente", ""), r.get("respaldo", ""), r["fecha_dato"]) for r in resultado["detalle"]}
    for archivo, fuente, respaldo, fecha_dato in sorted(usados):
        lineas.append("- `{}`; dato: {}; {}{}".format(archivo, fecha_dato, fuente, "; " + respaldo if respaldo and respaldo != fuente else ""))
    lineas += ["", "## Huellas de entradas", "", "El SHA-256 de configuración corresponde a su JSON normalizado (claves ordenadas, UTF-8, sin espacios); las demás huellas corresponden a los bytes originales.", ""]
    for nombre, f in sorted(resultado["fuentes"].items()):
        lineas.append("- {}: `{}` — `{}`".format(nombre, f["archivo"], f["sha256"]))
    return "\n".join(lineas) + "\n"


def objeto_json(pares):
    objeto = {}
    for clave, valor in pares:
        exigir(clave not in objeto, "Campo JSON repetido: " + clave)
        objeto[clave] = valor
    return objeto


def ejecutar(configuracion=CONFIG, salida=None, reporte=None, raiz=RAIZ):
    configuracion = Path(configuracion).resolve()
    raiz = Path(raiz).resolve()
    with configuracion.open(encoding="utf-8-sig") as archivo:
        config = json.load(archivo, parse_float=str, object_pairs_hook=objeto_json)
    resultado = evaluar(config, raiz, configuracion)
    salida = Path(salida) if salida is not None else raiz / "data/processed/hu-06"
    reporte = Path(reporte) if reporte is not None else raiz / "reports/hu-06/REPORTE_HU06.md"
    exigir(reporte.suffix.lower() == ".md", "El informe debe usar extensión .md")
    artefactos = {salida / "canasta_base.csv": csv_texto(resultado["canasta"]),
                  salida / "comparacion_escenarios.csv": csv_texto(resultado["comparacion"]),
                  salida / "detalle_costos.csv": csv_texto(resultado["detalle"]),
                  reporte: informe(resultado), reporte.parent / "comparacion_escenarios.svg": grafico(resultado)}
    protegidos = {f["ruta"] for f in resultado["fuentes"].values() if f["ruta"] is not None}
    for ruta in artefactos:
        destino = ruta.resolve()
        exigir(destino not in protegidos, "La salida sobrescribiría un archivo de entrada")
        if raiz in destino.parents:
            exigir(any(p in destino.parents for p in (raiz / "data/processed/hu-06", raiz / "reports/hu-06")),
                   "La salida debe pertenecer a HU-06, sin alterar otras historias")
    for ruta, contenido in artefactos.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(ruta.name + ".tmp")
        try:
            with temporal.open("w", encoding="utf-8", newline="") as archivo:
                archivo.write(contenido)
            temporal.replace(ruta)
        finally:
            if temporal.exists():
                temporal.unlink()
    return resultado


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--salida", type=Path, help="carpeta de los CSV (por defecto data/processed/hu-06)")
    ap.add_argument("--reporte", type=Path, help="ruta del informe Markdown")
    args = ap.parse_args()
    try:
        resultado = ejecutar(args.config, args.salida, args.reporte)
    except (ValueError, OSError, csv.Error, InvalidOperation) as error:
        print("HU-06: " + str(error), file=sys.stderr)
        return 1
    for r in resultado["comparacion"]:
        print("{}: {} BOB; diferencia {} BOB ({}%)".format(r["escenario_id"], r["total_bob"], r["diferencia_bob"], r["diferencia_pct"]))
    print("HU-06: {} líneas válidas; {} movimientos excluidos. Resultados MIXTO_SIMULADO.".format(len(resultado["canasta"]), len(resultado["excluidos"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
