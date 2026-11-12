import copy
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src/hu-09"))
from generar_alertas import (CAMPOS_DEMANDA, FUENTES, cargar_demanda, cargar_integracion,
                            equivalencias_hu17, evaluar_riesgo, ejecutar, leer_csv,
                            normalizar, numero, priorizar)


def registro(stock="20", plazo="10"):
    return {"codigo_unico": "REP-0001", "sistema_codigos": "REP", "stock_disponible": stock,
            "stock_verificable": True, "fecha_stock": "2026-10-20", "fecha_evaluacion": "2026-10-20",
            "max_antiguedad_stock_dias": 0, "plazo_dias": plazo, "tipo_dias_plazo": "naturales",
            "proveedor": "Proveedor prueba", "fuente_stock": "Conteo controlado de prueba"}


def demanda(tasa="4", **cambios):
    d = {"codigo_unico": "REP-0001", "proveedor": "", "validado": True, "metodo": "caso_de_prueba",
         "fecha_emision": "2026-10-20", "inicio_horizonte": "2026-10-21", "fin_horizonte": "2026-12-04",
         "tipo_pronostico": "TASA_CONSTANTE", "tasa": tasa, "valores": {}, "unidad_temporal": "unidades/dia",
         "distribucion": "", "fuente": "Caso sintético controlado", "tipo_dato": "SINTETICO"}
    d.update(cambios)
    return d


def escribir_csv(ruta, filas, campos=None):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos or list(filas[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


class MotorTest(unittest.TestCase):
    def test_stock_suficiente_identifica_los_tres_datos(self):
        r = evaluar_riesgo(registro(stock="100"), demanda())
        self.assertEqual((r["stock_disponible"], r["demanda_prevista"], r["plazo_dias"]), (Decimal(100), "4", Decimal(10)))
        self.assertEqual(r["demanda_durante_entrega"], Decimal(40))
        self.assertEqual(r["estado"], "SIN_ALERTA")
        self.assertEqual(r["faltante_previsto"], 0)
        self.assertEqual(r["fuente_demanda"], "Caso sintético controlado")

    def test_demanda_superior_al_stock(self):
        r = evaluar_riesgo(registro(), demanda())
        self.assertEqual((r["estado"], r["demanda_durante_entrega"], r["faltante_previsto"]), ("ALERTA", Decimal(40), Decimal(20)))

    def test_igualdad_no_genera_alerta(self):
        self.assertEqual(evaluar_riesgo(registro(stock="40"), demanda())["estado"], "SIN_ALERTA")

    def test_demanda_faltante_no_es_cero(self):
        for d in (None, demanda(tasa=None)):
            with self.subTest(d=d):
                r = evaluar_riesgo(registro(), d)
                self.assertEqual(r["estado"], "NO_CALCULABLE")
                self.assertIn("DEMANDA_FALTANTE", r["motivos"])
                self.assertIsNone(r["faltante_previsto"])

    def test_plazo_faltante(self):
        r = evaluar_riesgo(registro(plazo=None), demanda())
        self.assertEqual(r["estado"], "NO_CALCULABLE")
        self.assertIn("PLAZO_FALTANTE", r["motivos"])

    def test_ambos_faltantes_informa_ambos(self):
        r = evaluar_riesgo(registro(plazo=None))
        self.assertEqual(r["motivos"], ["DEMANDA_FALTANTE", "PLAZO_FALTANTE"])
        r = evaluar_riesgo(registro(plazo=None), demanda(tipo_pronostico="SERIE_DIARIA", tasa=None, valores={}))
        self.assertEqual(r["motivos"], ["DEMANDA_FALTANTE", "PLAZO_FALTANTE"])

    def test_stock_desconocido_o_no_verificable(self):
        for s, verificable in [(None, True), ("20", False)]:
            r = registro(stock=s)
            r["stock_verificable"] = verificable
            salida = evaluar_riesgo(r, demanda())
            self.assertIn("STOCK_DISPONIBLE_NO_VERIFICABLE", salida["motivos"])
            self.assertEqual(salida["estado"], "NO_CALCULABLE")

    def test_demanda_cero_valida_y_stock_cero(self):
        self.assertEqual(evaluar_riesgo(registro(stock="0"), demanda(tasa="0"))["estado"], "SIN_ALERTA")
        self.assertEqual(evaluar_riesgo(registro(stock="0"), demanda(tasa="1"))["faltante_previsto"], Decimal(10))

    def test_plazo_cero_explicito_conserva_regla_de_datos_faltantes(self):
        self.assertEqual(evaluar_riesgo(registro(plazo="0"), demanda())["demanda_durante_entrega"], 0)
        self.assertEqual(evaluar_riesgo(registro(plazo="0"))["estado"], "NO_CALCULABLE")

    def test_rechaza_negativos_y_no_finitos(self):
        for valor in ("-1", "NaN", "Infinity", True, 0.1):
            for campo in ("stock_disponible", "plazo_dias", "demanda"):
                with self.subTest(valor=valor, campo=campo):
                    r, d = registro(), demanda()
                    if campo == "demanda":
                        d["tasa"] = valor
                    else:
                        r[campo] = valor
                    with self.assertRaises(ValueError):
                        evaluar_riesgo(r, d)
        with self.assertRaises(ValueError):
            numero("1.5", "plazo", entero=True)

    def test_decimal_no_redondea_antes_de_comparar(self):
        r = evaluar_riesgo(registro(stock="0.3", plazo="3"), demanda(tasa="0.1"))
        self.assertEqual(r["estado"], "SIN_ALERTA")
        self.assertEqual(r["demanda_durante_entrega"], Decimal("0.3"))

    def test_horizonte_insuficiente(self):
        r = evaluar_riesgo(registro(), demanda(fin_horizonte="2026-10-25"))
        self.assertIn("HORIZONTE_INSUFICIENTE", r["motivos"])
        self.assertIsNone(r["demanda_durante_entrega"])

    def test_serie_diaria_suma_solo_ventana(self):
        valores = {"2026-10-21": "2", "2026-10-22": "5", "2026-10-23": "1", "2026-10-24": "999"}
        r = evaluar_riesgo(registro(stock="5", plazo="3"), demanda(tipo_pronostico="SERIE_DIARIA", tasa=None, valores=valores))
        self.assertEqual(r["demanda_durante_entrega"], 8)
        self.assertEqual(r["faltante_previsto"], 3)

    def test_serie_con_dia_faltante_o_vacio_no_se_completa(self):
        for valores in ({"2026-10-21": "0"}, {"2026-10-21": "0", "2026-10-22": None}):
            r = evaluar_riesgo(registro(plazo="2"), demanda(tipo_pronostico="SERIE_DIARIA", tasa=None, valores=valores))
            self.assertIn("DIAS_PRONOSTICO_FALTANTES", r["motivos"])

    def test_codigos_y_proveedores_no_se_asocian_por_parecido(self):
        with self.assertRaisesRegex(ValueError, "no relacionado"):
            evaluar_riesgo(registro(), demanda(codigo_unico="RP001"))
        r = evaluar_riesgo(registro(), demanda(proveedor="Otro proveedor"))
        self.assertIn("PROVEEDOR_PRONOSTICO_NO_COINCIDE", r["motivos"])

    def test_pronostico_no_validado_o_posterior_a_evaluacion(self):
        self.assertIn("PRONOSTICO_NO_VALIDADO", evaluar_riesgo(registro(), demanda(validado=False))["motivos"])
        self.assertIn("PRONOSTICO_POSTERIOR_A_EVALUACION", evaluar_riesgo(registro(), demanda(fecha_emision="2026-10-21", inicio_horizonte="2026-10-22"))["motivos"])

    def test_stock_antiguo_futuro_y_sin_fecha(self):
        r = registro()
        r["fecha_stock"] = "2026-10-19"
        self.assertIn("STOCK_DESACTUALIZADO", evaluar_riesgo(r, demanda())["motivos"])
        r["fecha_stock"] = "2026-10-21"
        with self.assertRaisesRegex(ValueError, "Stock posterior"):
            evaluar_riesgo(r, demanda())
        r["fecha_stock"] = ""
        self.assertIn("FECHA_STOCK_FALTANTE", evaluar_riesgo(r, demanda())["motivos"])

    def test_dias_habiles_incluyen_consumo_de_fin_de_semana_y_feriados(self):
        r = registro(stock="0", plazo="1")
        r.update(fecha_evaluacion="2026-11-13", fecha_stock="2026-11-13", tipo_dias_plazo="habiles")
        d = demanda(tasa="2", fecha_emision="2026-11-13", inicio_horizonte="2026-11-14")
        cal = {"dias_laborables": [0, 1, 2, 3, 4], "feriados": [], "fuente": "Calendario sintético de prueba"}
        salida = evaluar_riesgo(r, d, cal)
        self.assertEqual((salida["fecha_recepcion"], salida["demanda_durante_entrega"]), ("2026-11-16", Decimal(6)))
        cal["feriados"] = ["2026-11-16"]
        self.assertEqual(evaluar_riesgo(r, d, cal)["demanda_durante_entrega"], 8)
        r["tipo_dias_plazo"] = "naturales"
        self.assertEqual(evaluar_riesgo(r, d)["demanda_durante_entrega"], 2)

    def test_calendario_faltante_no_se_inventa(self):
        r = registro()
        r["tipo_dias_plazo"] = "habiles"
        self.assertIn("CALENDARIO_LABORAL_FALTANTE", evaluar_riesgo(r, demanda())["motivos"])
        r["tipo_dias_plazo"] = "no_definido"
        self.assertIn("CALENDARIO_PLAZO_NO_DEFINIDO", evaluar_riesgo(r, demanda())["motivos"])

    def test_conversion_semanal_exige_distribucion_explicita(self):
        d = demanda(tasa="70", unidad_temporal="unidades/semana")
        self.assertIn("DISTRIBUCION_TEMPORAL_FALTANTE", evaluar_riesgo(registro(plazo="3"), d)["motivos"])
        d["distribucion"] = "uniforme"
        self.assertEqual(evaluar_riesgo(registro(plazo="3"), d)["demanda_durante_entrega"], 30)

    def test_conversion_mensual_usa_dias_reales_en_cambio_de_mes(self):
        r = registro(plazo="2")
        r.update(fecha_evaluacion="2026-10-30", fecha_stock="2026-10-30")
        d = demanda(tasa="930", unidad_temporal="unidades/mes", distribucion="uniforme", fecha_emision="2026-10-30", inicio_horizonte="2026-10-31")
        # 31/10: 930/31=30; 01/11: 930/30=31.
        self.assertEqual(evaluar_riesgo(r, d)["demanda_durante_entrega"], 61)

    def test_igualdad_semanal_y_mensual_sin_microfaltantes_por_division(self):
        r = registro(stock="2", plazo="7")
        d = demanda(tasa="2", unidad_temporal="unidades/semana", distribucion="uniforme")
        self.assertEqual(evaluar_riesgo(r, d)["estado"], "SIN_ALERTA")
        r.update(stock_disponible="3", plazo_dias="31", fecha_stock="2026-09-30", fecha_evaluacion="2026-09-30")
        d = demanda(tasa="3", unidad_temporal="unidades/mes", distribucion="uniforme", fecha_emision="2026-09-30", inicio_horizonte="2026-10-01")
        salida = evaluar_riesgo(r, d)
        self.assertEqual((salida["estado"], salida["demanda_durante_entrega"], salida["faltante_previsto"]), ("SIN_ALERTA", Decimal(3), Decimal(0)))

    def test_prioridades_descendentes_y_no_calculables_visibles(self):
        filas = [dict(evaluar_riesgo(registro(stock=s), demanda()), codigo_unico=c) for s, c in [("30", "REP-0002"), ("5", "REP-0001"), ("50", "REP-0003")]]
        filas.append(dict(evaluar_riesgo(registro(), None), codigo_unico="REP-0004"))
        orden = priorizar(filas)
        self.assertEqual([r["codigo_unico"] for r in orden], ["REP-0001", "REP-0002", "REP-0003", "REP-0004"])
        self.assertEqual([r["prioridad"] for r in orden], [1, 2, None, None])


class IntegracionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        for ruta, _ in FUENTES.values():
            destino = self.raiz / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ / ruta, destino)
        self.config = json.loads((RAIZ / "data/raw/hu-09/demostracion/configuracion.json").read_text(encoding="utf-8"))
        destino = self.raiz / self.config["demanda"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RAIZ / self.config["demanda"], destino)
        self.ruta_config = self.raiz / "config.json"
        self.guardar_config()

    def guardar_config(self):
        self.ruta_config.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    def cargar(self):
        self.guardar_config()
        return cargar_integracion(self.ruta_config, self.raiz)

    def tabla(self, nombre):
        ruta, campos = FUENTES[nombre]
        return leer_csv(self.raiz / ruta, campos.split())

    def modificar_tabla(self, nombre, filas):
        escribir_csv(self.raiz / FUENTES[nombre][0], filas)

    def test_demo_reproduce_resultados_de_las_fuentes(self):
        r = ejecutar(self.ruta_config, raiz=self.raiz)
        self.assertEqual(Counter(f["estado"] for f in r["filas"]), {"ALERTA": 4, "SIN_ALERTA": 3, "NO_CALCULABLE": 3})
        alertas = [f for f in r["filas"] if f["estado"] == "ALERTA"]
        self.assertEqual([(f["codigo_unico"], f["faltante_previsto"]) for f in alertas], [("REP-0002", Decimal(37)), ("REP-0001", Decimal(25)), ("REP-0008", Decimal(15)), ("REP-0009", Decimal(15))])
        self.assertEqual(next(f for f in r["filas"] if f["codigo_unico"] == "REP-0004")["estado"], "SIN_ALERTA")

    def test_deduplicacion_preserva_lineas_legitimas(self):
        dep = self.tabla("depuracion")
        plantilla = next(r for r in dep if r["id_movimiento"] == "1015")
        dep.append(dict(plantilla, id_movimiento="2000", cantidad="3"))  # otra línea válida de la misma orden
        self.modificar_tabla("depuracion", dep)
        conc = self.tabla("conciliacion")
        for r in conc:
            if r["codigo_unico"] == "REP-0006":
                r.update(entradas="103", stock_registrado="133", conteo_fisico="133")
        self.modificar_tabla("conciliacion", conc)
        _, registros, _ = self.cargar()
        s = next(r for r, _ in registros if r["codigo_unico"] == "REP-0006")
        self.assertEqual(s["stock_registrado"], 133)
        self.assertEqual(s["duplicados_excluidos"], "1016")

    def test_ajustes_aplicados_se_cuentan_una_vez(self):
        for _ in range(2):
            _, registros, _ = self.cargar()
            stocks = {r["codigo_unico"]: r for r, _ in registros}
            self.assertEqual((stocks["REP-0002"]["stock_registrado"], stocks["REP-0002"]["stock_ajustado"]), (55, 53))
            self.assertEqual((stocks["REP-0004"]["stock_registrado"], stocks["REP-0004"]["stock_ajustado"]), (28, 18))
            self.assertEqual(stocks["REP-0004"]["ajustes_mismo_corte"], "1")

    def test_rechazos_repetidos_y_discrepancias_no_cambian_stock(self):
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0007")
        self.assertEqual((r["stock_registrado"], r["stock_ajustado"], r["ajustes_rechazados"]), (9, 9, 4))
        self.assertIsNone(r["stock_disponible"])
        self.assertIn("DIFERENCIA_CONTEO_PENDIENTE", r["motivos"])

    def test_ajustes_duplicados_o_sin_respaldo_se_rechazan(self):
        ajustes = self.tabla("ajustes")
        self.modificar_tabla("ajustes", ajustes + [ajustes[0]])
        with self.assertRaisesRegex(ValueError, "duplicado"):
            self.cargar()
        self.modificar_tabla("ajustes", ajustes)
        self.modificar_tabla("historial", [r for r in self.tabla("historial") if r["accion"] != "AJUSTE_APLICADO"])
        with self.assertRaisesRegex(ValueError, "Respaldo"):
            self.cargar()

    def test_ajustes_futuros_no_se_usan_retrospectivamente(self):
        self.config["fecha_evaluacion"] = "2026-09-30"
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0004")
        self.assertEqual(r["stock_ajustado"], 28)
        self.assertIn("AJUSTE_POSTERIOR_A_EVALUACION", r["motivos"])
        self.assertIsNone(r["stock_disponible"])

    def test_reservas_desconocidas_y_pendientes_no_se_ignoran(self):
        self.config["disponibilidad"] = {"politica": "no_confirmada", "motivo": "Sin información"}
        self.config["permitir_pendientes_con_conteo_coincidente"] = False
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0001")
        self.assertIn("RESERVAS_Y_BLOQUEOS_DESCONOCIDOS", r["motivos"])
        self.assertIn("MOVIMIENTOS_PENDIENTES_REVISION", r["motivos"])
        self.assertIsNone(r["reservas"])

    def test_reservas_confirmadas_se_restan_sin_inventarlas(self):
        self.config["disponibilidad"] = {"politica": "confirmadas", "motivo": "Confirmación de prueba", "confirmaciones": {
            "REP-0002": {"reservas": "3", "bloqueos": "2", "fecha": "2026-09-30", "fuente": "Registro sintético", "tipo_dato": "SINTETICO"}}}
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0002")
        self.assertEqual(r["stock_disponible"], 48)  # 55 - ajuste 2 - reservas 3 - bloqueos 2
        self.assertEqual(r["naturaleza_disponibilidad"], "SINTETICO")
        self.config["disponibilidad"]["confirmaciones"]["REP-0002"]["reservas"] = "100"
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0002")
        self.assertIn("RESERVAS_Y_BLOQUEOS_SUPERAN_STOCK", r["motivos"])

    def test_plazo_de_hu31_no_es_condicion_de_pago_y_vence(self):
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0004")
        self.assertEqual(r["plazo_dias"], 3)  # la cotización dice Crédito 30 días
        self.config["fecha_evaluacion"] = "2026-11-10"
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0004")
        self.assertIsNone(r["plazo_dias"])
        self.assertEqual(r["plazo_referencia_dias"], 3)
        self.assertIn("COTIZACION_VENCIDA", r["motivos"])

    def test_alias_hu17_y_rechazo_de_rp_sin_equivalencia(self):
        eq = equivalencias_hu17(self.tabla("depuracion"))
        self.assertEqual(normalizar("TOY-FA01", "REP", eq), "REP-0002")
        with self.assertRaises(ValueError):
            normalizar("RP001", "RP", eq)
        with self.assertRaises(ValueError):
            normalizar("REP-9999", "REP", eq)

    def test_pronosticos_duplicados_y_negativos_se_rechazan(self):
        ruta = self.raiz / self.config["demanda"]
        filas = leer_csv(ruta, CAMPOS_DEMANDA)
        escribir_csv(ruta, filas + [filas[0]])
        with self.assertRaisesRegex(ValueError, "duplicada"):
            self.cargar()
        filas[0]["demanda"] = "-1"
        escribir_csv(ruta, filas)
        with self.assertRaises(ValueError):
            self.cargar()

    def test_csv_de_mae_no_cumple_contrato_de_demanda(self):
        shutil.copyfile(RAIZ / "data/processed/hu-07/comparacion_pronosticos.csv", self.raiz / self.config["demanda"])
        with self.assertRaisesRegex(ValueError, "faltan columnas"):
            self.cargar()

    def test_cabecera_sola_y_demanda_vacia_no_son_cero(self):
        ruta = self.raiz / self.config["demanda"]
        escribir_csv(ruta, [], CAMPOS_DEMANDA)
        _, registros, _ = self.cargar()
        self.assertTrue(all(d is None for _, d in registros))
        resultado = ejecutar(self.ruta_config, raiz=self.raiz)
        self.assertTrue(all(r["estado"] == "NO_CALCULABLE" for r in resultado["filas"]))

    def test_regeneracion_identica_conserva_entradas_y_svg(self):
        originales = [self.raiz / p for p, _ in FUENTES.values()] + [self.ruta_config, self.raiz / self.config["demanda"]]
        antes = {p: p.read_bytes() for p in originales}
        r = ejecutar(self.ruta_config, raiz=self.raiz)
        primera = {p: p.read_bytes() for p in r["artefactos"]}
        ejecutar(self.ruta_config, raiz=self.raiz)
        self.assertEqual(primera, {p: p.read_bytes() for p in r["artefactos"]})
        self.assertEqual(antes, {p: p.read_bytes() for p in originales})
        svg = next(p for p in r["artefactos"] if p.suffix == ".svg")
        self.assertEqual(ET.parse(svg).getroot().tag, "{http://www.w3.org/2000/svg}svg")
        alertas = leer_csv(next(p for p in r["artefactos"] if p.name == "alertas_faltantes.csv"), ["estado", "faltante_previsto"])
        self.assertTrue(all(a["faltante_previsto"] == "" for a in alertas if a["estado"] == "NO_CALCULABLE"))

    def test_error_no_sobrescribe_salida_y_modos_separados(self):
        r = ejecutar(self.ruta_config, raiz=self.raiz)
        antes = {p: p.read_bytes() for p in r["artefactos"]}
        with self.assertRaisesRegex(ValueError, "modo seleccionado"):
            ejecutar(self.ruta_config, salida=self.raiz / "data/processed/hu-09", raiz=self.raiz)
        self.config["fecha_stock"] = "2026-11-01"
        self.guardar_config()
        with self.assertRaises(ValueError):
            ejecutar(self.ruta_config, raiz=self.raiz)
        self.assertEqual(antes, {p: p.read_bytes() for p in r["artefactos"]})

    def test_integracion_no_admite_reservas_cero_sin_confirmacion(self):
        self.config["modo"] = "INTEGRACION"
        with self.assertRaisesRegex(ValueError, "Solo la demostración"):
            self.cargar()


class RepositorioTest(unittest.TestCase):
    def test_integracion_actual_no_inventa_datos_y_preserva_otras_hu(self):
        fuentes = [RAIZ / p for p, _ in FUENTES.values()] + [RAIZ / "src/hu-07/comparar_pronosticos.py", RAIZ / "data/processed/hu-07/comparacion_pronosticos.csv"]
        antes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes}
        with tempfile.TemporaryDirectory() as t:
            r = ejecutar(salida=Path(t) / "csv", reporte=Path(t) / "reporte/REPORTE_HU09.md")
            self.assertEqual(Counter(f["estado"] for f in r["filas"]), {"NO_CALCULABLE": 10})
            self.assertTrue(all("DEMANDA_FALTANTE" in f["motivos"] and f["stock_disponible"] is None for f in r["filas"]))
            self.assertEqual(sum(f["plazo_dias"] is not None for f in r["filas"]), 1)
        self.assertEqual(antes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes})

    def test_cli_desde_otro_directorio_y_error_controlado(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            cmd = [sys.executable, str(RAIZ / "src/hu-09/generar_alertas.py"), "--salida", str(t / "csv"), "--reporte", str(t / "reporte/REPORTE_HU09.md")]
            r = subprocess.run(cmd, cwd=t, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(b"NO_CALCULABLE=10", r.stdout)
            error = subprocess.run(cmd + ["--config", str(t / "ausente.json")], cwd=t, capture_output=True)
            self.assertEqual(error.returncode, 1)
            self.assertIn(b"HU-09:", error.stderr)


if __name__ == "__main__":
    unittest.main()
