"""Pruebas de la lógica única de alertas (HU-09 unida con SCRUM-66).

Los casos de la primera parte vienen de las pruebas de HU-09 de Sabrina Adrian Zelaya, adaptados a la lógica del
motor del simulador: igualdad sin alerta, datos faltantes que no se vuelven cero, plazo cero explícito, rechazo de
negativos y no finitos, sin redondeo antes de comparar, prioridades con los no calculables visibles, regeneración
idéntica, uso desde otra carpeta y error que no sobrescribe la salida. La segunda parte prueba el exportador
src/hu-09/generar_alertas.py y que la app y el motor de Python den las mismas alertas.
"""
import copy
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RAIZ, "src", "simulador"))
import motor_ref  # noqa: E402

DATOS = os.path.join(RAIZ, "data", "processed", "simulador", "datos_app.json")
SCRIPT = os.path.join(RAIZ, "src", "hu-09", "generar_alertas.py")

_spec = importlib.util.spec_from_file_location("generar_alertas", SCRIPT)
GA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GA)


def cargar():
    with open(DATOS, encoding="utf-8") as f:
        return json.load(f)


def caso(stock, camino, plazo, ventas, s=2, S=5):
    """Un solo repuesto con su proveedor, con los valores que interesan a la prueba."""
    d = cargar()
    rep = copy.deepcopy(d["repuestos"][0])
    prov = copy.deepcopy(next(p for p in d["proveedores"] if p["proveedor_id"] == rep["proveedor_id"]))
    rep.update({"repuesto_id": "REP-T", "stock_al_2026_11_10": stock, "en_transito_al_2026_11_10": camino,
                "punto_pedido_s": s, "nivel_maximo_S": S, "tipo_demanda": "suave"})
    prov["plazo_normal_dias"] = plazo
    return {"repuestos": [rep], "proveedores": [prov], "ventas": {"REP-T": ventas}}


def meses(valores):
    return [["2025-{:02d}".format(i % 12 + 1), v] for i, v in enumerate(valores)]


def leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def uno(datos):
    return motor_ref.alertas(datos, 11.70)[0]


class CriteriosDeHU09(unittest.TestCase):
    def test_demanda_superior_al_stock_da_faltante(self):
        # Media de 12 meses = 30 u/mes = 1 u/día; plazo 30 días → 30 u durante la entrega; hay 20.
        f = uno(caso(15, 5, 30, meses([30] * 12)))
        self.assertAlmostEqual(f["demanda_entrega"], 30.0, places=9)
        self.assertAlmostEqual(f["faltante_previsto"], 10.0, places=9)
        self.assertEqual(GA.alerta_faltante(f), "ALERTA")

    def test_igualdad_no_genera_alerta(self):
        f = uno(caso(20, 10, 30, meses([30] * 12)))
        self.assertEqual(f["faltante_previsto"], 0)
        self.assertEqual(GA.alerta_faltante(f), "SIN_ALERTA")

    def test_stock_suficiente_sin_alerta(self):
        f = uno(caso(100, 0, 30, meses([30] * 12)))
        self.assertEqual(f["faltante_previsto"], 0)
        self.assertEqual(f["est"], 2)

    def test_demanda_faltante_no_es_cero(self):
        f = uno(caso(10, 0, 30, []))
        self.assertEqual(f["est"], 3)
        self.assertEqual(f["etiqueta"], "Sin datos")
        self.assertIn("DEMANDA_FALTANTE", f["motivos"])
        self.assertIsNone(f["demanda_entrega"])
        self.assertIsNone(f["faltante_previsto"])
        self.assertEqual(f["cantidad_sugerida"], 0)

    def test_mes_vacio_en_la_serie_no_se_completa(self):
        v = meses([3] * 12)
        v[5][1] = ""
        f = uno(caso(10, 0, 30, v))
        self.assertIn("DEMANDA_FALTANTE", f["motivos"])

    def test_plazo_faltante(self):
        f = uno(caso(10, 0, "", meses([3] * 12)))
        self.assertEqual(f["motivos"], ["PLAZO_FALTANTE"])
        self.assertIsNone(f["plazo"])

    def test_ambos_faltantes_informa_ambos(self):
        f = uno(caso(10, 0, None, []))
        self.assertEqual(f["motivos"], ["PLAZO_FALTANTE", "DEMANDA_FALTANTE"])

    def test_stock_desconocido(self):
        f = uno(caso("", 0, 30, meses([3] * 12)))
        self.assertIn("STOCK_FALTANTE", f["motivos"])
        self.assertIsNone(f["stock"])

    def test_demanda_cero_valida_y_stock_cero(self):
        f = uno(caso(0, 0, 30, meses([0] * 12)))
        self.assertNotEqual(f["est"], 3)
        self.assertEqual(f["demanda_entrega"], 0)
        self.assertEqual(f["faltante_previsto"], 0)

    def test_plazo_cero_explicito_es_valido(self):
        f = uno(caso(1, 0, 0, meses([30] * 12)))
        self.assertNotEqual(f["est"], 3)
        self.assertEqual(f["demanda_entrega"], 0)

    def test_rechaza_negativos_y_no_finitos(self):
        for malo in (-1, "nan", "inf", "-inf", "abc"):
            with self.subTest(malo=malo):
                self.assertIn("STOCK_FALTANTE", uno(caso(malo, 0, 30, meses([3] * 12)))["motivos"])
                self.assertIn("PLAZO_FALTANTE", uno(caso(5, 0, malo, meses([3] * 12)))["motivos"])

    def test_no_redondea_antes_de_comparar(self):
        # 1 u/mes durante 31 días = 1,0333…: con 1 unidad disponible hay un faltante pequeño, no cero.
        f = uno(caso(1, 0, 31, meses([1] * 12)))
        self.assertGreater(f["faltante_previsto"], 0)
        self.assertAlmostEqual(f["faltante_previsto"], 31 / 30 - 1, places=12)

    def test_prioridades_y_no_calculables_visibles(self):
        d = caso(15, 5, 30, meses([30] * 12), s=25)
        base = d["repuestos"][0]
        otros = []
        for rid, stock, camino in (("REP-U", 5, 0), ("REP-V", "", 0)):
            r = copy.deepcopy(base)
            r.update({"repuesto_id": rid, "stock_al_2026_11_10": stock, "en_transito_al_2026_11_10": camino})
            otros.append(r)
            d["ventas"][rid] = meses([30] * 12)
        d["repuestos"] += otros
        filas = motor_ref.alertas(d, 11.70)
        self.assertEqual([f["id"] for f in filas], ["REP-U", "REP-T", "REP-V"])  # mayor faltante primero
        self.assertEqual(filas[-1]["etiqueta"], "Sin datos")
        self.assertEqual(len(filas), 3)

    def test_proveedor_desconocido_queda_sin_datos(self):
        d = caso(5, 0, 30, meses([3] * 12))
        d["repuestos"][0]["proveedor_id"] = "PROV-NO-EXISTE"
        self.assertIn("PLAZO_FALTANTE", uno(d)["motivos"])


class DatosReales(unittest.TestCase):
    def test_los_30_repuestos_se_calculan(self):
        filas = motor_ref.alertas(cargar(), 11.70)
        self.assertEqual(len(filas), 30)
        self.assertEqual(sum(1 for f in filas if f["est"] == 3), 0)
        conteo = {e: sum(1 for f in filas if f["etiqueta"] == e) for e in motor_ref.ETIQUETAS}
        self.assertEqual((conteo["Pedir ya"], conteo["Vigilar"]), (3, 4))

    def test_js_y_python_dan_las_mismas_alertas_con_sin_datos(self):
        if shutil.which("node") is None:
            self.skipTest("node no está instalado")
        d = cargar()
        d["repuestos"][1]["stock_al_2026_11_10"] = ""
        d["ventas"][d["repuestos"][2]["repuesto_id"]] = []
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "d.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(d, f)
            js = ("const M=require(process.argv[1]);const D=require(process.argv[2]);"
                  "process.stdout.write(JSON.stringify(M.alertas(D,11.7)))")
            out = subprocess.run(["node", "-e", js, os.path.join(RAIZ, "src", "simulador", "motor.js"), ruta],
                                 capture_output=True, text=True, check=True).stdout
        a_js, a_py = json.loads(out), motor_ref.alertas(d, 11.7)
        self.assertEqual([f["id"] for f in a_js], [f["id"] for f in a_py])
        for x, y in zip(a_js, a_py):
            self.assertEqual(set(x), set(y))
            for k in x:
                if isinstance(y[k], float) and x[k] is not None:
                    self.assertAlmostEqual(x[k], y[k], places=9, msg=k)
                else:
                    self.assertEqual(x[k], y[k], msg=k)
        self.assertEqual(sum(1 for f in a_py if f["est"] == 3), 2)


class Exportador(unittest.TestCase):
    def test_regeneracion_identica(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = os.path.join(tmp, "r", "REPORTE_HU09.md")
            GA.ejecutar(DATOS, tmp, rep)
            primero = {n: leer(os.path.join(dp, n))
                       for dp, _, fs in os.walk(tmp) for n in fs}
            GA.ejecutar(DATOS, tmp, rep)
            segundo = {n: leer(os.path.join(dp, n))
                       for dp, _, fs in os.walk(tmp) for n in fs}
            self.assertEqual(primero, segundo)
            self.assertEqual(set(primero), {"alertas_faltantes.csv", "REPORTE_HU09.md", "prioridades.svg"})

    def test_csv_versionado_coincide_con_la_logica(self):
        versionado = leer(os.path.join(RAIZ, "data", "processed", "hu-09", "alertas_faltantes.csv"))
        d = cargar()
        _, filas = GA.construir(d, float(d["tc"]["oficial"]["valor"]), d["tc"]["oficial"]["fecha"])
        self.assertEqual(versionado, GA.csv_texto(filas))

    def test_no_calculable_sale_vacio_no_cero(self):
        d = cargar()
        d["repuestos"][0]["stock_al_2026_11_10"] = ""
        _, filas = GA.construir(d, 11.70, "prueba")
        f = next(x for x in filas if x["alerta_faltante"] == "NO_CALCULABLE")
        self.assertEqual((f["stock"], f["venta_durante_entrega"], f["faltante_previsto"], f["costo_bs"]), ("", "", "", ""))
        self.assertEqual(f["motivos"], "STOCK_FALTANTE")

    def test_cli_desde_otro_directorio_y_error_controlado(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = subprocess.run([sys.executable, SCRIPT, "--salida", tmp, "--reporte", os.path.join(tmp, "R.md")],
                                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertIn("Pedir ya=3", ok.stdout)
            antes = leer(os.path.join(tmp, "alertas_faltantes.csv"))
            malo = subprocess.run([sys.executable, SCRIPT, "--datos", os.path.join(tmp, "no_existe.json"),
                                   "--salida", tmp, "--reporte", os.path.join(tmp, "R.md")],
                                  cwd=tmp, capture_output=True, text=True)
            self.assertEqual(malo.returncode, 1)
            self.assertIn("ERROR", malo.stderr)
            self.assertEqual(antes, leer(os.path.join(tmp, "alertas_faltantes.csv")))


if __name__ == "__main__":
    unittest.main()
