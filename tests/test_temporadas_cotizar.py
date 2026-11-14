"""Pruebas de SCRUM-75 (temporadas de venta) y SCRUM-72 (cotización por cantidad).

Comprueban los criterios de cada historia sobre los datos reales de la app y que el motor de la pantalla
(src/simulador/motor.js) y la referencia en Python (motor_ref.py) den lo mismo.
"""
import copy
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
MOTOR = os.path.join(RAIZ, "src", "simulador", "motor.js")
TOL = 1e-9


def cargar():
    with open(DATOS, encoding="utf-8") as f:
        return json.load(f)


CASOS_COTIZAR = [
    {"rep": "REP-0022", "q": 1, "tc": 11.70},
    {"rep": "REP-0022", "q": 9, "tc": 11.70},
    {"rep": "REP-0022", "q": 10, "tc": 11.70},
    {"rep": "REP-0001", "q": 49, "tc": 11.75},
    {"rep": "REP-0013", "q": 50, "tc": 12.40},
    {"rep": "REP-0030", "q": 500, "tc": 9.80},
    {"rep": "REP-0005", "q": 60, "tc": 11.70, "tramos": [{"desde": 5, "pct": 40}]},
]

RUNNER = r"""
const fs = require("fs");
const M = require(process.argv[2]);
const D = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const C = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
process.stdout.write(JSON.stringify({
  temporadas: M.temporadas(D),
  cotizar: C.map(c => M.cotizar(D, c.rep, c.q, c.tc, c.tramos))
}));
"""


def diferencias(a, b, ruta="$"):
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return [] if a == b else [f"{ruta}: {a!r} != {b!r}"]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return [] if abs(a - b) <= TOL * max(1, abs(a), abs(b)) else [f"{ruta}: {a} != {b}"]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{ruta}: largo {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diferencias(x, y, f"{ruta}[{i}]")]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{ruta}: claves {sorted(set(a) ^ set(b))}"]
        return [d for k in a for d in diferencias(a[k], b[k], f"{ruta}.{k}")]
    return [f"{ruta}: tipos {type(a).__name__} != {type(b).__name__}"]


class Temporadas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()
        cls.t = ref.temporadas(cls.d)

    def test_un_perfil_por_repuesto_y_el_total(self):
        self.assertEqual([p["id"] for p in self.t["repuestos"]], [r["repuesto_id"] for r in self.d["repuestos"]])
        self.assertEqual(len(self.t["total"]["promedio_mes"]), 12)

    def test_promedio_por_mes_calculado_a_mano(self):
        # REP-0022, febrero: los meses 02 de la serie, promediados.
        serie = self.d["ventas"]["REP-0022"]
        feb = [u for m, u in serie if m[5:7] == "02"]
        p = next(x for x in self.t["repuestos"] if x["id"] == "REP-0022")
        self.assertAlmostEqual(p["promedio_mes"][1], sum(feb) / len(feb), places=12)
        self.assertEqual(p["observaciones"][1], len(feb))

    def test_total_suma_los_30(self):
        meses = sorted({m for v in self.d["ventas"].values() for m, _ in v})
        dic = [m for m in meses if m[5:7] == "12"]
        tot = [sum(u for v in self.d["ventas"].values() for mm, u in v if mm == m) for m in dic]
        self.assertAlmostEqual(self.t["total"]["promedio_mes"][11], sum(tot) / len(tot), places=12)

    def test_meses_fuertes_son_los_que_superan_el_promedio(self):
        for p in self.t["repuestos"] + [self.t["total"]]:
            esperados = [i + 1 for i, v in enumerate(p["promedio_mes"]) if v is not None and v > p["media"] + ref.EPS]
            self.assertEqual(p["meses_fuertes"], esperados)
            self.assertTrue(all(p["indice"][m - 1] > 1 for m in p["meses_fuertes"]))

    def test_mes_vacio_no_se_vuelve_cero(self):
        d = copy.deepcopy(self.d)
        d["ventas"]["REP-0001"] = [["2025-01", 4], ["2025-02", ""], ["2026-01", 6], ["2025-03", -1]]
        p = next(x for x in ref.temporadas(d)["repuestos"] if x["id"] == "REP-0001")
        self.assertEqual(p["promedio_mes"][0], 5)
        self.assertIsNone(p["promedio_mes"][1])
        self.assertIsNone(p["promedio_mes"][2])
        self.assertEqual(p["meses_fuertes"], [])
        self.assertEqual(p["mes_pico"], 1)

    def test_serie_vacia(self):
        p = ref.perfil_mensual([])
        self.assertIsNone(p["media"])
        self.assertEqual(p["meses_fuertes"], [])
        self.assertIsNone(p["mes_pico"])


class Cotizar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()

    def c(self, q, rep="REP-0022", tc=11.70, tramos=None):
        return ref.cotizar(self.d, rep, q, tc, tramos)

    def test_precio_con_el_dolar_del_dia(self):
        r = ref.buscar_repuesto(self.d, "REP-0022")
        self.assertAlmostEqual(self.c(1)["precio_lista_bs"], ref.redondear(r["precio_venta_usd"] * 11.70, 2))
        self.assertGreater(self.c(1, tc=12.5)["precio_lista_bs"], self.c(1)["precio_lista_bs"])

    def test_tramos_de_ejemplo(self):
        self.assertEqual([self.c(q)["pct_aplicado"] for q in (1, 9, 10, 49, 50, 300)], [0, 0, 5, 5, 10, 10])
        x = self.c(10)
        self.assertAlmostEqual(x["precio_unitario_bs"], ref.redondear(x["precio_lista_bs"] * 0.95, 2))
        self.assertAlmostEqual(x["total_bs"], ref.redondear(x["precio_unitario_bs"] * 10, 2))
        self.assertAlmostEqual(x["subtotal_bs"] - x["descuento_bs"], x["total_bs"], places=6)

    def test_siguiente_tramo(self):
        self.assertEqual(self.c(9)["siguiente_tramo"], {"desde": 10, "pct": 5, "faltan": 1})
        self.assertEqual(self.c(10)["siguiente_tramo"]["desde"], 50)
        self.assertIsNone(self.c(50)["siguiente_tramo"])

    def test_nunca_por_debajo_del_costo(self):
        x = self.c(60, rep="REP-0005", tramos=[{"desde": 5, "pct": 40}])
        self.assertTrue(x["tope"])
        self.assertEqual(x["precio_unitario_bs"], x["costo_puesto_bs"])
        self.assertLess(x["pct_aplicado"], 40)
        for r in self.d["repuestos"]:
            for q in (1, 10, 50):
                y = ref.cotizar(self.d, r["repuesto_id"], q, 11.70)
                self.assertGreaterEqual(y["precio_unitario_bs"], y["costo_puesto_bs"], r["repuesto_id"])

    def test_tramos_de_ejemplo_no_llegan_al_tope_hoy(self):
        # Con márgenes de 35 % o más, un 10 % de descuento no alcanza el costo: el tope existe, pero hoy no se activa.
        self.assertFalse(any(ref.cotizar(self.d, r["repuesto_id"], 50, 11.70)["tope"] for r in self.d["repuestos"]))

    def test_stock_y_lo_que_hay_que_pedir(self):
        x = self.c(30)
        self.assertEqual(x["en_stock"] + x["por_pedir"], 30)
        self.assertLessEqual(x["en_stock"], x["stock"])

    def test_cantidad_invalida(self):
        for malo in (0, -3, 2.5, "abc", "", None, float("nan"), float("inf")):
            with self.subTest(malo=malo), self.assertRaises(ValueError):
                self.c(malo)
        with self.assertRaises(ValueError):
            self.c(5, tc=0)


class Equivalencia(unittest.TestCase):
    def test_js_y_python_dan_lo_mismo(self):
        if shutil.which("node") is None:
            self.skipTest("node no está instalado")
        d = cargar()
        with tempfile.TemporaryDirectory() as tmp:
            casos = os.path.join(tmp, "c.json")
            runner = os.path.join(tmp, "r.js")
            with open(casos, "w", encoding="utf-8") as f:
                json.dump(CASOS_COTIZAR, f)
            with open(runner, "w", encoding="utf-8") as f:
                f.write(RUNNER)
            out = subprocess.run(["node", runner, MOTOR, DATOS, casos], capture_output=True, text=True, check=True).stdout
        js = json.loads(out)
        py = json.loads(json.dumps({"temporadas": ref.temporadas(d),
                                    "cotizar": [ref.cotizar(d, c["rep"], c["q"], c["tc"], c.get("tramos"))
                                                for c in CASOS_COTIZAR]}))
        self.assertEqual(diferencias(js, py), [])

    def test_js_rechaza_cantidad_invalida(self):
        if shutil.which("node") is None:
            self.skipTest("node no está instalado")
        js = ("const M=require(process.argv[1]);const D=require(process.argv[2]);let n=0;"
              "for(const q of [0,-3,2.5,'abc','',null,NaN,Infinity]){try{M.cotizar(D,'REP-0022',q,11.7)}catch(e){n++}}"
              "process.stdout.write(String(n))")
        out = subprocess.run(["node", "-e", js, MOTOR, DATOS], capture_output=True, text=True, check=True).stdout
        self.assertEqual(out, "8")


if __name__ == "__main__":
    unittest.main()
