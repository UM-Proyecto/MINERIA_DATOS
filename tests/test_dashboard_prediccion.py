"""Pruebas de SCRUM-79 (dashboard), SCRUM-80 (predicciones) y SCRUM-81 (rotación e importancia ABC).

- El motor de la pantalla (motor.js) y la referencia en Python (motor_ref.py) dan lo mismo.
- Los números del dashboard cuadran con las ventas reales por repuesto.
- Las reglas de ABC, rotación, acumulación y baja rotación se cumplen fila por fila.
- Las métricas del clasificador se recalculan desde los casos de prueba guardados, el modelo no mira el futuro y el
  resultado es reproducible.
"""
import copy
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
import motor_ref as ref  # noqa: E402

DATOS = os.path.join(RAIZ, "data", "processed", "simulador", "datos_app.json")
PRED = os.path.join(RAIZ, "data", "processed", "scrum-80", "prediccion.json")
MOTOR = os.path.join(RAIZ, "src", "simulador", "motor.js")
TC = 11.67

spec = importlib.util.spec_from_file_location("predecir_venta", os.path.join(RAIZ, "src", "scrum-80", "predecir_venta.py"))
pv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pv)

sys.path.insert(0, os.path.dirname(__file__))
from test_temporadas_cotizar import diferencias  # noqa: E402


def cargar():
    with open(DATOS, encoding="utf-8") as f:
        return json.load(f)


def raro(d):
    """Datos con casos borde: venta inválida, cliente desconocido, repuesto sin historia y sin stock."""
    d = copy.deepcopy(d)
    d["clientes"]["ventas"] += [["2026-10", "REP-0001", "CLI-01", ""], ["2026-10", "REP-0001", "CLI-XX", 3],
                                ["2026-11", "REP-0005", "CLI-02", 2], ["mal", "REP-0005", "CLI-02", 2]]
    d["ventas"]["REP-0030"] = d["ventas"]["REP-0030"][-5:]
    d["repuestos"][1] = dict(d["repuestos"][1], stock_al_2026_11_10="")
    d["repuestos"][2] = dict(d["repuestos"][2], stock_al_2026_11_10=0)
    return d


RUNNER = r"""
const fs = require("fs");
const M = require(process.argv[2]);
const out = process.argv.slice(3).map(p => { const D = JSON.parse(fs.readFileSync(p, "utf8"));
  return {dashboard: M.dashboard(D, %TC%), rotacion: M.rotacion(D, %TC%)}; });
process.stdout.write(JSON.stringify(out));
""".replace("%TC%", str(TC))


class Dashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()
        cls.t = ref.dashboard(cls.d, TC)

    def test_cuadra_con_las_ventas_por_repuesto(self):
        por_mes = {}
        for serie in self.d["ventas"].values():
            for m, u in serie:
                por_mes[m] = por_mes.get(m, 0) + u
        self.assertEqual({x["mes"]: x["unidades"] for x in self.t["demanda_mes"]}, por_mes)
        self.assertEqual(self.t["total"]["unidades"], sum(por_mes.values()))
        self.assertEqual(self.t["meses"][0], "2022-08")
        self.assertEqual(self.t["ultimo_mes"], "2026-10")
        self.assertEqual(len(self.t["meses"]), 51)

    def test_por_anio_suma_el_total(self):
        self.assertAlmostEqual(sum(a["monto_bs"] for a in self.t["por_anio"]), self.t["total"]["monto_bs"], places=6)
        self.assertEqual(sum(a["meses"] for a in self.t["por_anio"]), 51)

    def test_repuesto_y_cliente_que_mas(self):
        u = {}
        for rid, serie in self.d["ventas"].items():
            u[rid] = sum(x for _, x in serie)
        self.assertEqual(self.t["repuestos"][0]["unidades"], max(u.values()))
        self.assertEqual(self.t["clientes"][0]["id"], ref.tablero_clientes(self.d, TC)["clientes"][0]["id"])
        self.assertAlmostEqual(self.t["clientes"][0]["monto_bs"], ref.tablero_clientes(self.d, TC)["clientes"][0]["monto_bs"], places=6)

    def test_tendencia_6_meses_a_mano(self):
        c = self.t["clientes"][0]
        precio = {r["repuesto_id"]: ref.redondear(r["precio_venta_usd"] * TC, 2) for r in self.d["repuestos"]}
        ult = sum(v[3] * precio[v[1]] for v in self.d["clientes"]["ventas"] if v[2] == c["id"] and "2026-05" <= v[0] <= "2026-10")
        prev = sum(v[3] * precio[v[1]] for v in self.d["clientes"]["ventas"] if v[2] == c["id"] and "2025-11" <= v[0] <= "2026-04")
        self.assertAlmostEqual(c["ult6_bs"], ult, places=6)
        self.assertAlmostEqual(c["prev6_bs"], prev, places=6)
        self.assertAlmostEqual(sum(c["trimestres"]), c["monto_bs"], places=6)

    def test_datos_invalidos_no_suman(self):
        t = ref.dashboard(raro(self.d), TC)
        self.assertEqual(t["total"]["unidades"], self.t["total"]["unidades"] + 2)  # solo la venta de 2026-11 válida
        self.assertEqual(t["ultimo_mes"], "2026-11")

    def test_sin_ventas(self):
        d = copy.deepcopy(self.d)
        d["clientes"]["ventas"] = []
        self.assertEqual(ref.dashboard(d, TC)["meses"], [])


class Rotacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()
        cls.r = ref.rotacion(cls.d, TC)

    def test_abc_por_pareto(self):
        filas = sorted(self.r["repuestos"], key=lambda f: (-f["valor12_bs"], f["id"]))
        total, acum = sum(f["valor12_bs"] for f in filas), 0
        for f in filas:
            previo = acum / total
            self.assertEqual(f["clase_abc"], "A" if previo < 0.8 else "B" if previo < 0.95 else "C", f["id"])
            acum += f["valor12_bs"]

    def test_rotacion_y_alertas_fila_por_fila(self):
        rep = {r["repuesto_id"]: r for r in self.d["repuestos"]}
        for f in self.r["repuestos"]:
            r = rep[f["id"]]
            u12 = sum(u for _, u in self.d["ventas"][f["id"]][-12:])
            self.assertEqual(f["u12"], u12)
            cob = r["stock_al_2026_11_10"] / (u12 / 12) if u12 else None
            self.assertEqual(f["clase_rot"], "baja" if u12 == 0 else "alta" if cob <= 3 else "media" if cob <= 12 else "baja", f["id"])
            acum = (r["stock_al_2026_11_10"] + r["en_transito_al_2026_11_10"] > r["nivel_maximo_S"]
                    or (cob is not None and cob > 24) or (u12 == 0 and r["stock_al_2026_11_10"] > 0))
            self.assertEqual(f["acumulacion"], acum, f["id"])
            self.assertEqual(f["baja_rotacion"], u12 == 0 or u12 / r["stock_al_2026_11_10"] < 1, f["id"])

    def test_matriz_cuenta_los_30(self):
        self.assertEqual(sum(sum(c.values()) for c in self.r["matriz"].values()), 30)
        self.assertGreater(self.r["acumulacion"], 0)   # control: la regla encuentra algo en los datos reales
        self.assertLess(self.r["acumulacion"], 30)

    def test_casos_borde(self):
        r = ref.rotacion(raro(self.d), TC)
        f = {x["id"]: x for x in r["repuestos"]}
        self.assertTrue(f["REP-0030"]["sin_datos"])
        self.assertTrue(f[self.d["repuestos"][1]["repuesto_id"]]["sin_datos"])
        sin_stock = f[self.d["repuestos"][2]["repuesto_id"]]
        self.assertFalse(sin_stock["sin_datos"])
        self.assertIsNone(sin_stock["rotacion_anual"])
        self.assertEqual(sum(sum(c.values()) for c in r["matriz"].values()), 28)


class Equivalencia(unittest.TestCase):
    def test_js_y_python_dan_lo_mismo(self):
        if shutil.which("node") is None:
            self.skipTest("node no está instalado")
        d = cargar()
        with tempfile.TemporaryDirectory() as tmp:
            rutas = []
            for i, x in enumerate([d, raro(d)]):
                p = os.path.join(tmp, f"d{i}.json")
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(x, f)
                rutas.append(p)
            runner = os.path.join(tmp, "r.js")
            with open(runner, "w", encoding="utf-8") as f:
                f.write(RUNNER)
            js = json.loads(subprocess.run(["node", runner, MOTOR] + rutas, capture_output=True, text=True, check=True).stdout)
        py = json.loads(json.dumps([{"dashboard": ref.dashboard(x, TC), "rotacion": ref.rotacion(x, TC)} for x in (d, raro(d))]))
        self.assertEqual(diferencias(js, py), [])


class Prediccion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PRED, encoding="utf-8") as f:
            cls.p = json.load(f)
        cls.v = cls.p["validacion"]

    def test_metricas_se_recalculan_desde_los_casos(self):
        casos = self.v["casos_prueba"]
        probs, y = [c[2] for c in casos], [c[3] for c in casos]
        self.assertEqual(len(casos), self.v["prueba"]["casos"])
        m = pv.metricas([1 if q >= self.p["corte"] else 0 for q in probs], y, probs)
        for k in ("vp", "fp", "fn", "vn"):
            self.assertEqual(m[k], self.v["modelo"][k], k)
        for k in ("exactitud", "auc", "brier"):
            self.assertAlmostEqual(m[k], self.v["modelo"][k], places=3, msg=k)
        my = pv.metricas([1 if q >= self.p["corte_youden"] else 0 for q in probs], y)
        self.assertEqual(my["vp"], self.v["modelo_corte_youden"]["vp"])

    def test_validacion_temporal_sin_mezclar(self):
        self.assertLessEqual(self.v["entreno"]["hasta"], "2025-10")
        self.assertEqual(self.v["prueba"]["desde"], "2025-11")
        self.assertTrue(all(c[1] > self.v["entreno"]["hasta"] for c in self.v["casos_prueba"]))

    def test_no_mira_el_futuro(self):
        meses, series = pv.leer_series()
        s = series["REP-0001"]
        t = 30
        fut = s[:t] + [99] * (len(s) - t)
        self.assertEqual(pv.variables(s, t), pv.variables(fut, t))

    def test_mejor_que_la_regla_simple_y_que_la_tasa_base(self):
        self.assertGreater(self.v["modelo"]["auc"], self.v["regla_mes_anterior"]["auc"])
        self.assertLess(self.v["modelo"]["brier"], self.v["brier_tasa_base"])

    def test_calibracion_cubre_los_casos(self):
        self.assertEqual(sum(t["n"] for t in self.v["calibracion"]), self.v["prueba"]["casos"])

    def test_predicciones_y_niveles(self):
        pr = self.p["predicciones"]
        self.assertEqual(len(pr), 30)
        self.assertEqual([q["probabilidad"] for q in pr], sorted((q["probabilidad"] for q in pr), reverse=True))
        for q in pr:
            self.assertTrue(0 <= q["probabilidad"] <= 1)
            esp = "alta" if q["probabilidad"] >= 0.5 else "media" if q["probabilidad"] >= self.p["corte_youden"] else "baja"
            self.assertEqual(q["nivel"], esp, q["repuesto_id"])
        self.assertEqual(self.p["mes_predicho"], "2026-11")

    def test_reproducible_y_dentro_de_la_app(self):
        self.assertEqual(json.loads(json.dumps(pv.modelo())), self.p)
        self.assertEqual(cargar()["prediccion"], self.p)

    def test_las_metricas_detectan_un_modelo_malo(self):
        # Control negativo: probabilidades al revés deben dar AUC por debajo de 0,5.
        casos = self.v["casos_prueba"]
        self.assertLess(pv.auc([1 - c[2] for c in casos], [c[3] for c in casos]), 0.5)


if __name__ == "__main__":
    unittest.main()
