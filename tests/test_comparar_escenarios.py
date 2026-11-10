import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src/hu-06"))
from comparar_escenarios import CONFIG, evaluar, ejecutar, informe, numero


def escribir_csv(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


class EscenariosTest(unittest.TestCase):
    """Datos pequeños independientes: dos líneas válidas de una misma orden."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.config["canasta"] = {"documentos": ["OC-1"], "incluir_pendientes": False}
        self.config["parametros_logisticos"]["peso_kg"]["valor"] = "10"
        self.config["escenarios"] = self.config["escenarios"][:3]
        movs = []
        for ident, codigo, cantidad, precio, doc in [
            ("1", "REP-A", "10", "2", "OC-1"),
            ("2", "REP-B", "3", "5", "OC-1"),
            ("3", "REP-A", "10", "2", "OC-1"),
            ("4", "REP-A", "1", "2", "OC-2"),
        ]:
            movs.append({"id_movimiento": ident, "fecha": "2026-09-01", "codigo_unico": codigo,
                         "codigo_repuesto": codigo + ("-ALIAS" if ident == "3" else ""), "documento": doc,
                         "cantidad": cantidad, "precio_unitario_usd": precio, "tipo_movimiento": "ENTRADA",
                         "proveedor_cliente": "Proveedor prueba", "origen": "EQUIPO_FICTICIO",
                         "fuente": "Prueba independiente", "fecha_actualizacion": "2026-10-19"})
        dep = [{k: r[k] for k in ("id_movimiento", "fecha", "codigo_unico", "documento", "cantidad", "tipo_movimiento")} for r in movs]
        for r, estado in zip(dep, ["ORIGINAL", "ORIGINAL", "DUPLICADO", "PENDIENTE_REVISION"]):
            r["estado"] = estado
        conceptos = [self.config["escenarios"][0]["logistica"][0]["concepto"],
                     self.config["escenarios"][2]["cambios_logistica"][0]["concepto"]]
        fletes = [{"concepto": concepto, "valor_min": tarifa, "valor_max": tarifa,
                   "unidad": "USD por kg (10.0% del FOB)", "fecha_dato": "2026-08",
                   "tipo_dato": "ESTIMACION", "respaldo": "INE de prueba", "nota": "Incluye seguro",
                   "ruta_o_alcance": "Hasta frontera"} for concepto, tarifa in zip(conceptos, ["2", "3"])]
        complementos = [{"concepto": spec["concepto"], "valor": valor, "unidad": unidad,
                        "fecha_dato": "2026-09", "tipo_dato": "SINTETICO", "respaldo": "Sin factura",
                        "fuente": "Prueba", "fecha_actualizacion": "2026-10-19"}
                       for spec, valor, unidad in zip(self.config["escenarios"][0]["logistica"][1:],
                                                      ["10", "2", "7.50"], ["% del CIF", "% del CIF", "BOB"])]
        tc = [{"id_serie": sid, "fecha": "2026-10-23", "valor": valor, "unidad": "Bs por 1 USD",
               "tipo_dato": "DOCUMENTADO", "fuente": "Serie de prueba", "url": "https://example.org/serie",
               "nota": "Observación", "fecha_actualizacion": "2026-10-25"}
              for sid, valor in [("TCO_BCB", "10"), ("PARALELO_P2P_VENTA", "12")]]
        self.tablas = {"movimientos": movs, "depuracion": dep, "cotizaciones": [
            {"codigo_unico": "REP-A", "descripcion": "Repuesto A"}, {"codigo_unico": "REP-B", "descripcion": "Repuesto B"}],
            "costos_importacion": fletes, "costos_complementarios": complementos, "tipos_cambio": tc}
        self.guardar_tablas()

    def guardar_tablas(self):
        for nombre, filas in self.tablas.items():
            escribir_csv(self.raiz / self.config["archivos"][nombre], filas)

    def evaluar(self):
        return evaluar(self.config, self.raiz)

    def guardar_config(self):
        ruta = self.raiz / "data/raw/hu-06/escenarios.json"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        return ruta

    def supuesto(self, ident, concepto, valor, unidad, cubre):
        return {"id": ident, "origen": "supuesto", "concepto": concepto, "valor": valor, "unidad": unidad,
                "cubre": cubre, "motivo": "Supuesto explícito de prueba", "fecha_dato": "2026-10-23"}

    def test_base_y_dos_alternativas_con_calculo_independiente(self):
        resultado = self.evaluar()
        base, cambiaria, logistica = resultado["comparacion"]
        # Mercancía = 10*2 + 3*5 = 35. Flete/seguro = 2*10 = 20.
        # CIF=55; nacionalización=5.50; comisión=1.10; gasto BOB=7.50.
        self.assertEqual(base["mercancia_usd"], Decimal("35.00"))
        self.assertEqual(base["logistica_usd"], Decimal("26.60"))
        self.assertEqual(base["logistica_bob_origen"], Decimal("7.50"))
        self.assertEqual(base["total_bob"], Decimal("623.50"))
        self.assertEqual(base["diferencia_bob"], 0)
        self.assertEqual(base["diferencia_pct"], 0)
        self.assertEqual(cambiaria["total_bob"], Decimal("746.70"))
        self.assertEqual(cambiaria["diferencia_bob"], Decimal("123.20"))
        self.assertEqual(cambiaria["diferencia_pct"], Decimal("19.76"))
        # Logística alternativa: CIF=65; gastos USD=30+6.50+1.30.
        self.assertEqual(logistica["total_bob"], Decimal("735.50"))
        self.assertEqual(logistica["diferencia_bob"], Decimal("112.00"))
        self.assertEqual(logistica["diferencia_pct"], Decimal("17.96"))

    def test_conserva_canasta_y_lineas_validas_del_mismo_documento(self):
        resultado = self.evaluar()
        self.assertEqual([r["id_movimiento"] for r in resultado["canasta"]], ["1", "2"])
        self.assertEqual(resultado["excluidos"], [{"id_movimiento": "3", "documento": "OC-1", "estado": "DUPLICADO"}])
        esperado = [("1", "REP-A", Decimal(10), Decimal(2)), ("2", "REP-B", Decimal(3), Decimal(5))]
        for e in resultado["evaluados"]:
            self.assertEqual([(r["id_movimiento"], r["codigo_unico"], r["cantidad"], r["precio_unitario_usd"]) for r in e["lineas"]], esperado)
        base, tc, log = resultado["evaluados"]
        self.assertEqual(base["logistica"], tc["logistica"])
        self.assertEqual(resultado["comparacion"][0]["tipo_cambio"], resultado["comparacion"][2]["tipo_cambio"])

    def test_requiere_exactamente_un_base_y_ambos_tipos_alternativos(self):
        original = copy.deepcopy(self.config["escenarios"])
        for escenarios in [original[:2], original[1:] + [dict(original[1], id="OTRO")],
                           original + [dict(original[0], id="BASE2")],
                           [original[0], original[1], dict(original[2], tipo="COMBINADO")]]:
            with self.subTest(escenarios=escenarios):
                self.config["escenarios"] = escenarios
                with self.assertRaises(ValueError):
                    self.evaluar()

    def test_rechaza_ids_y_campos_desconocidos(self):
        with self.subTest("id repetido"):
            self.config["escenarios"][1]["id"] = "BASE"
            with self.assertRaisesRegex(ValueError, "ID"):
                self.evaluar()
        self.config["escenarios"][1]["id"] = "CAMBIARIA"
        self.config["escenarios"][1]["cantidad"] = "99"
        with self.assertRaisesRegex(ValueError, "Campos desconocidos"):
            self.evaluar()

    def test_obligatorios_no_permiten_cambios_fuera_de_su_factor(self):
        original = copy.deepcopy(self.config)
        casos = [(0, "modificaciones", []), (1, "modificaciones", []), (1, "cambios_logistica", []),
                 (1, "parametros_logisticos", {}), (2, "tipo_cambio", original["escenarios"][0]["tipo_cambio"]),
                 (2, "modificaciones", [])]
        for indice, clave, valor in casos:
            with self.subTest(indice=indice, clave=clave):
                self.config = copy.deepcopy(original)
                self.config["escenarios"][indice][clave] = valor
                with self.assertRaises(ValueError):
                    self.evaluar()

    def test_alternativas_deben_cambiar_el_factor_declarado(self):
        self.config["escenarios"][1]["tipo_cambio"] = self.config["escenarios"][0]["tipo_cambio"]
        with self.assertRaisesRegex(ValueError, "debe cambiar"):
            self.evaluar()
        self.config["escenarios"][1]["tipo_cambio"] = {"origen": "serie", "id_serie": "PARALELO_P2P_VENTA", "fecha": "2026-10-23"}
        self.config["escenarios"][2]["cambios_logistica"] = []
        with self.assertRaisesRegex(ValueError, "debe cambiar"):
            self.evaluar()

    def test_logistica_exige_cambio_efectivo_y_no_solo_otra_fuente(self):
        self.tablas["costos_importacion"][1]["valor_min"] = "2"
        self.tablas["costos_importacion"][1]["valor_max"] = "2"
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "costo efectivo"):
            self.evaluar()

    def test_cambios_expresos_de_precio_y_cantidad_en_combinado(self):
        self.config["escenarios"].append({"id": "EXPRESO", "tipo": "COMBINADO", "descripcion": "Cambio autorizado",
            "modificaciones": [{"id_movimiento": "1", "cantidad": "12", "precio_unitario_usd": "2.5", "motivo": "Compra ampliada"}],
            "parametros_logisticos": {"peso_kg": {"valor": "12", "motivo": "Peso hipotético actualizado", "fecha_dato": "2026-10-23"}}})
        resultado = self.evaluar()
        self.assertEqual(resultado["comparacion"][-1]["mercancia_usd"], Decimal("45.00"))
        self.assertEqual(resultado["comparacion"][0]["mercancia_usd"], Decimal("35.00"))
        modificada = resultado["evaluados"][-1]["lineas"][0]
        self.assertEqual((modificada["cantidad_base"], modificada["precio_base_usd"]), (10, 2))
        self.assertIn("Compra ampliada", informe(resultado))
        self.assertEqual(resultado["canasta"][0]["cantidad"], 10)

    def test_modificar_cantidad_exige_redeclarar_peso(self):
        self.config["escenarios"].append({"id": "EXPRESO", "tipo": "COMBINADO", "descripcion": "Cambio",
            "modificaciones": [{"id_movimiento": "1", "cantidad": "12", "motivo": "Cambio"}]})
        with self.assertRaisesRegex(ValueError, "parámetros físicos"):
            self.evaluar()

    def test_modificaciones_exigen_linea_unica_y_motivo(self):
        for mods in [[{"id_movimiento": "99", "precio_unitario_usd": "3", "motivo": "Cambio"}],
                     [{"id_movimiento": "1", "precio_unitario_usd": "3", "motivo": ""}],
                     [{"id_movimiento": "1", "precio_unitario_usd": "3", "motivo": "Cambio"}] * 2]:
            with self.subTest(mods=mods):
                self.config["escenarios"] = self.config["escenarios"][:3] + [{"id": "EXPRESO", "tipo": "COMBINADO", "descripcion": "Cambio", "modificaciones": mods}]
                with self.assertRaises(ValueError):
                    self.evaluar()

    def test_pendientes_excluidos_salvo_seleccion_expresa(self):
        self.config["canasta"]["documentos"].append("OC-2")
        with self.assertRaisesRegex(ValueError, "sin líneas válidas"):
            self.evaluar()
        self.config["canasta"]["incluir_pendientes"] = True
        resultado = self.evaluar()
        self.assertEqual(len(resultado["canasta"]), 3)
        self.assertEqual(resultado["canasta"][-1]["estado_hu17"], "PENDIENTE_REVISION")

    def test_equipo_requiere_clasificacion_y_coincidencia_con_hu17(self):
        self.tablas["depuracion"][0]["cantidad"] = "11"
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "no coinciden"):
            self.evaluar()
        self.tablas["depuracion"].pop(0)
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "sin clasificación"):
            self.evaluar()

    def test_admite_historia_sintetica_ausente_en_hu17_con_etiqueta(self):
        self.tablas["movimientos"][0]["origen"] = "SINTETICO"
        self.tablas["depuracion"].pop(0)
        self.guardar_tablas()
        self.assertEqual(self.evaluar()["canasta"][0]["estado_hu17"], "SINTETICO_SIN_CLASIFICACION_HU17")

    def test_no_descarta_documentos_distintos_del_mismo_repuesto(self):
        self.tablas["depuracion"][3]["estado"] = "ORIGINAL"
        self.config["canasta"]["documentos"].append("OC-2")
        self.guardar_tablas()
        self.assertEqual(len(self.evaluar()["canasta"]), 3)

    def test_rechaza_numeros_invalidos(self):
        for valor in ["NaN", "Infinity", "-1", "0", "abc", True, 1.2, "1e100", "0.000000001"]:
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                numero(valor, "prueba")
        self.tablas["movimientos"][0]["cantidad"] = "1.5"
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "entero"):
            self.evaluar()

    def test_rechaza_unidades_incompatibles_e_indices(self):
        for unidad in ["puntos de indice", "EUR por kg", "USD por tonelada", "BOB/USD"]:
            with self.subTest(unidad=unidad):
                self.tablas["costos_importacion"][0]["unidad"] = unidad
                self.guardar_tablas()
                with self.assertRaisesRegex(ValueError, "Unidad incompatible"):
                    self.evaluar()
        self.tablas["costos_importacion"][0]["unidad"] = "USD por kg"
        self.tablas["costos_importacion"][0]["concepto"] = "indice compuesto SCFI"
        self.config["escenarios"][0]["logistica"][0]["concepto"] = "indice compuesto SCFI"
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "posible índice"):
            self.evaluar()

    def test_rechaza_doble_seguro_y_costo_incluido_en_precio(self):
        self.config["escenarios"][0]["logistica"].append(self.supuesto("seguro", "Seguro extra", "1", "USD", ["seguro"]))
        with self.assertRaisesRegex(ValueError, "Doble contabilización"):
            self.evaluar()
        self.config["escenarios"][0]["logistica"].pop()
        self.config["incluidos_en_precio"] = ["seguro"]
        with self.assertRaisesRegex(ValueError, "Doble contabilización"):
            self.evaluar()

    def test_rechaza_costos_pendientes_y_alcance_incompleto(self):
        self.tablas["costos_importacion"][0]["tipo_dato"] = "PENDIENTE"
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "pendiente"):
            self.evaluar()
        self.tablas["costos_importacion"][0]["tipo_dato"] = "ESTIMACION"
        self.guardar_tablas()
        self.config["escenarios"][0]["logistica"].pop()
        with self.assertRaisesRegex(ValueError, "Faltan componentes"):
            self.evaluar()

    def test_rechaza_bases_cif_de_moneda_o_alcance_incompatibles(self):
        self.tablas["costos_importacion"][0]["unidad"] = "BOB por kg"
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "CIF requiere"):
            self.evaluar()
        self.tablas["costos_importacion"][0]["unidad"] = "USD por kg"
        self.guardar_tablas()
        self.config["incluidos_en_precio"] = ["flete_local"]
        self.config["escenarios"][0]["logistica"].pop()
        with self.assertRaisesRegex(ValueError, "CIF no identificable"):
            self.evaluar()

    def test_rechaza_referencias_ambiguas_y_csv_sin_columnas(self):
        self.tablas["costos_importacion"].append(dict(self.tablas["costos_importacion"][0]))
        self.guardar_tablas()
        with self.assertRaisesRegex(ValueError, "exactamente una referencia"):
            self.evaluar()
        ruta = self.raiz / self.config["archivos"]["movimientos"]
        ruta.write_text("id_movimiento\n1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "faltan columnas"):
            self.evaluar()

    def test_rechaza_json_ambiguo_y_referencia_mal_formada(self):
        config = self.guardar_config()
        config.write_text('{"version": 1, "version": 2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Campo JSON repetido"):
            ejecutar(config, raiz=self.raiz)
        self.config["escenarios"][0]["logistica"] = ["internacional"]
        with self.assertRaisesRegex(ValueError, "objeto JSON"):
            self.evaluar()

    def test_rechaza_parametros_fisicos_ausentes(self):
        self.config["parametros_logisticos"] = {}
        with self.assertRaisesRegex(ValueError, "Falta parámetro explícito: peso_kg"):
            self.evaluar()

    def test_calcula_m3_y_contenedores_con_parametros_expresos(self):
        for unidad, parametro, valor, esperado in [("USD por m3", "volumen_m3", "2.5", "5.00"),
                                                     ("USD por contenedor", "contenedores", "2", "4.00")]:
            with self.subTest(unidad=unidad):
                self.tablas["costos_importacion"][0]["unidad"] = unidad
                self.config["parametros_logisticos"][parametro] = {"valor": valor, "motivo": "Supuesto", "fecha_dato": "2026-10-23"}
                self.guardar_tablas()
                detalle = self.evaluar()["detalle"]
                gasto = next(r for r in detalle if r["escenario_id"] == "BASE" and r.get("id_linea") == "internacional")
                self.assertEqual(gasto["importe_origen"], Decimal(esperado))
        self.config["parametros_logisticos"]["contenedores"]["valor"] = "1.5"
        with self.assertRaisesRegex(ValueError, "entero"):
            self.evaluar()

    def test_resuelve_seguro_porcentual_del_propio_cif(self):
        base = self.config["escenarios"][0]
        base["logistica"][0] = self.supuesto("internacional", "Flete sin seguro", "15", "USD", ["flete_internacional"])
        base["logistica"].append(self.supuesto("seguro", "Seguro CIF", "10", "% del CIF", ["seguro"]))
        self.config["escenarios"][2]["cambios_logistica"] = [self.supuesto("internacional", "Otro flete sin seguro", "20", "USD", ["flete_internacional"])]
        resultado = self.evaluar()
        # CIF = (35+15)/(1-0.10) => 55.56; prima redondeada = 5.56.
        self.assertEqual(resultado["comparacion"][0]["cif_simulado_usd"], Decimal("55.56"))
        seguro = next(r for r in resultado["detalle"] if r["escenario_id"] == "BASE" and r.get("id_linea") == "seguro")
        self.assertEqual(seguro["importe_origen"], Decimal("5.56"))
        base["logistica"][-1]["valor"] = "100"
        with self.assertRaisesRegex(ValueError, "menor al 100"):
            self.evaluar()

    def test_cambio_faltante_no_se_imputa_y_fecha_futura_se_rechaza(self):
        self.config["escenarios"][1]["tipo_cambio"]["fecha"] = "2026-10-22"
        with self.assertRaisesRegex(ValueError, "sin observación exacta"):
            self.evaluar()
        self.config["escenarios"][1]["tipo_cambio"]["fecha"] = "2026-10-24"
        with self.assertRaisesRegex(ValueError, "posterior"):
            self.evaluar()

    def test_cambio_supuesto_exige_motivo_y_conserva_naturaleza(self):
        self.config["escenarios"][1]["tipo_cambio"] = {"origen": "supuesto", "fecha": "2026-10-23", "valor": "9", "motivo": "Hipótesis"}
        resultado = self.evaluar()
        fila = next(r for r in resultado["detalle"] if r["escenario_id"] == "CAMBIARIA" and r["clase"] == "TIPO_CAMBIO")
        self.assertEqual(fila["tipo_dato"], "SINTETICO")
        self.assertLess(resultado["comparacion"][1]["diferencia_bob"], 0)

    def test_trazabilidad_y_reconciliacion_del_detalle(self):
        resultado = self.evaluar()
        for r in resultado["detalle"]:
            for campo in ("fuente", "archivo_fuente", "sha256_fuente", "fecha_dato", "unidad", "tipo_dato"):
                self.assertTrue(r[campo], (campo, r))
        for escenario in resultado["comparacion"]:
            detalle = [r for r in resultado["detalle"] if r["escenario_id"] == escenario["escenario_id"]]
            self.assertEqual(sum((r.get("importe_bob", Decimal(0)) for r in detalle), Decimal(0)), escenario["total_bob"])

    def test_redondeo_half_up_por_linea_y_no_sobre_el_agregado(self):
        for i in (0, 1):
            self.tablas["movimientos"][i].update(cantidad="1", precio_unitario_usd="0.01")
            self.tablas["depuracion"][i]["cantidad"] = "1"
        self.tablas["tipos_cambio"][0]["valor"] = "0.5"
        self.guardar_tablas()
        base = self.evaluar()["comparacion"][0]
        self.assertEqual(base["mercancia_usd"], Decimal("0.02"))
        # Cada línea da 0.005 BOB y se redondea a 0.01: total 0.02 BOB.
        self.assertEqual(base["mercancia_bob"], Decimal("0.02"))

    def test_reproducibilidad_fuentes_intactas_y_svg_valido(self):
        config = self.guardar_config()
        entradas = [self.raiz / p for p in self.config["archivos"].values()] + [config]
        antes = {p: p.read_bytes() for p in entradas}
        ejecutar(config, raiz=self.raiz)
        salidas = list((self.raiz / "data/processed/hu-06").glob("*.csv")) + list((self.raiz / "reports/hu-06").iterdir())
        self.assertEqual(len(salidas), 5)
        primera = {p: p.read_bytes() for p in salidas}
        ejecutar(config, raiz=self.raiz)
        self.assertEqual(primera, {p: p.read_bytes() for p in salidas})
        self.assertEqual(antes, {p: p.read_bytes() for p in entradas})
        svg = ET.parse(self.raiz / "reports/hu-06/comparacion_escenarios.svg")
        self.assertEqual(svg.getroot().tag, "{http://www.w3.org/2000/svg}svg")

    def test_un_error_no_sobrescribe_ultima_salida_valida(self):
        config = self.guardar_config()
        ejecutar(config, raiz=self.raiz)
        salida = self.raiz / "data/processed/hu-06/comparacion_escenarios.csv"
        anterior = salida.read_bytes()
        self.config["parametros_logisticos"] = {}
        self.guardar_config()
        with self.assertRaises(ValueError):
            ejecutar(config, raiz=self.raiz)
        self.assertEqual(salida.read_bytes(), anterior)

    def test_no_permite_escribir_resultados_de_otras_historias(self):
        config = self.guardar_config()
        with self.assertRaisesRegex(ValueError, "sin alterar otras historias"):
            ejecutar(config, salida=self.raiz / "data/processed/hu-32", raiz=self.raiz)
        protegido = self.raiz / "README.md"
        protegido.write_text("Contenido original", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sin alterar otras historias"):
            ejecutar(config, reporte=protegido, raiz=self.raiz)
        self.assertEqual(protegido.read_text(encoding="utf-8"), "Contenido original")


class IntegracionRepositorioTest(unittest.TestCase):
    def test_resultados_del_pedido_existente_con_valores_esperados(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        resultado = evaluar(config)
        self.assertEqual(len(resultado["canasta"]), 5)
        self.assertEqual({r["id_movimiento"] for r in resultado["excluidos"]}, {"1006", "1016", "1022"})
        self.assertEqual({r["unidades"] for r in resultado["comparacion"]}, {205})
        self.assertEqual({r["mercancia_usd"] for r in resultado["comparacion"]}, {Decimal("2740.85")})
        # Cálculos independientes: mercancía 411.20+641.70+491+799+397.95.
        # Base: CIF=3061.41; nacionalización=106.41; comisión=34.96; local=12.50.
        # Alternativa: CIF=3139.31; nacionalización=109.12; comisión=35.85.
        esperados = [("38068.92", "0.00", "0.00"), ("38551.21", "482.29", "1.27"),
                     ("39033.88", "964.96", "2.53"), ("39528.40", "1459.48", "3.83")]
        for r, (total, diferencia, porcentaje) in zip(resultado["comparacion"], esperados):
            self.assertEqual(r["total_bob"], Decimal(total))
            self.assertEqual(r["diferencia_bob"], Decimal(diferencia))
            self.assertEqual(r["diferencia_pct"], Decimal(porcentaje))

    def test_cli_desde_otra_carpeta_y_salida_de_error(self):
        with tempfile.TemporaryDirectory() as carpeta:
            temporal = Path(carpeta)
            comando = [sys.executable, str(RAIZ / "src/hu-06/comparar_escenarios.py"),
                       "--salida", str(temporal / "csv"), "--reporte", str(temporal / "reporte/REPORTE_HU06.md")]
            bien = subprocess.run(comando, cwd=temporal, capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(bien.returncode, 0, bien.stdout + bien.stderr)
            self.assertIn("38068.92", bien.stdout)
            mal = subprocess.run(comando + ["--config", str(temporal / "no_existe.json")], cwd=temporal, capture_output=True)
            self.assertEqual(mal.returncode, 1)
            self.assertIn(b"HU-06:", mal.stderr)


if __name__ == "__main__":
    unittest.main()
