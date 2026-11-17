"""SCRUM-76: clientes SINTÉTICOS sobre las ventas reales y su tablero."""
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
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "simulador"))
import motor_ref as ref  # noqa: E402

spec = importlib.util.spec_from_file_location("generar_clientes", RAIZ / "src/scrum-76/generar_clientes.py")
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)
DATOS = RAIZ / "data/processed/simulador/datos_app.json"
MOTOR = RAIZ / "src/simulador/motor.js"
TOL = 1e-9


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cargar():
    return json.loads(DATOS.read_text(encoding="utf-8"))


class Reparto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ventas = leer(gc.VENTAS)
        cls.cat = {c["repuesto_id"]: c["categoria"] for c in leer(gc.CATALOGO)}
        cls.filas = leer(gc.SAL_VENTAS)

    def test_conserva_cada_repuesto_y_mes(self):
        real = {(v["repuesto_id"], v["mes"]): int(v["unidades"]) for v in self.ventas if int(v["unidades"]) > 0}
        asignado = {}
        for f in self.filas:
            k = (f["repuesto_id"], f["mes"])
            asignado[k] = asignado.get(k, 0) + int(f["unidades"])
        self.assertEqual(asignado, real)

    def test_misma_semilla_mismo_resultado_y_versionado(self):
        a = gc.repartir(self.ventas, self.cat)
        self.assertEqual(a, gc.repartir(self.ventas, self.cat))
        self.assertEqual([(f["mes"], f["repuesto_id"], f["cliente_id"], int(f["unidades"])) for f in self.filas],
                         [(f["mes"], f["repuesto_id"], f["cliente_id"], f["unidades"]) for f in a])
        self.assertNotEqual(a, gc.repartir(self.ventas, self.cat, semilla=1))

    def test_todo_marcado_sintetico(self):
        for ruta in (gc.SAL_CLIENTES, gc.SAL_VENTAS):
            self.assertTrue(all(r["marca"] == "SINTÉTICO" for r in leer(ruta)), ruta)
        self.assertTrue(all("(ficticio)" in c[1] for c in gc.CLIENTES))


class Tablero(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()
        cls.t = ref.tablero_clientes(cls.d, 11.70)

    def test_ordenado_por_compras_y_suma_el_total(self):
        m = [c["monto_bs"] for c in self.t["clientes"]]
        self.assertEqual(m, sorted(m, reverse=True))
        self.assertAlmostEqual(sum(m), self.t["total"]["monto_bs"], places=4)
        self.assertEqual(sum(c["unidades"] for c in self.t["clientes"]), 797)

    def test_temporada_y_fuera_suman_el_total(self):
        for c in self.t["clientes"]:
            self.assertAlmostEqual(c["monto_temp_bs"] + c["monto_fuera_bs"], c["monto_bs"], places=6)
            self.assertEqual(c["unid_temp"] + c["unid_fuera"], c["unidades"])
        self.assertEqual(self.t["temporada"], ref.temporadas(self.d)["total"]["meses_fuertes"])

    def test_monto_con_el_precio_del_cotizador(self):
        c = self.t["clientes"][0]
        filas = [v for v in self.d["clientes"]["ventas"] if v[2] == c["id"]]
        esperado = sum(v[3] * ref.cotizar(self.d, v[1], 1, 11.70)["precio_lista_bs"] for v in filas)
        self.assertAlmostEqual(c["monto_bs"], esperado, places=6)

    def test_que_lleva(self):
        for c in self.t["clientes"]:
            self.assertLessEqual(len(c["top"]), 3)
            u = [x["unidades"] for x in c["top"]]
            self.assertEqual(u, sorted(u, reverse=True))

    def test_una_venta_nueva_cambia_el_tablero(self):
        d = copy.deepcopy(self.d)
        ultimo = self.t["clientes"][-1]["id"]
        d["clientes"]["ventas"].append(["2026-12", "REP-0013", ultimo, 500])
        t = ref.tablero_clientes(d, 11.70)
        self.assertEqual(t["clientes"][0]["id"], ultimo)
        self.assertEqual(t["total"]["unidades"], 1297)

    def test_dato_invalido_no_suma(self):
        d = copy.deepcopy(self.d)
        d["clientes"]["ventas"] += [["2026-12", "REP-0013", "CLI-01", -5], ["2026-12", "REP-0013", "CLI-99", 5],
                                    ["2026-12", "REP-XXXX", "CLI-01", 5], ["2026-12", "REP-0013", "CLI-01", ""]]
        self.assertEqual(ref.tablero_clientes(d, 11.70)["total"], self.t["total"])

    def test_js_y_python_dan_lo_mismo(self):
        if shutil.which("node") is None:
            self.skipTest("node no está instalado")
        js = ("const M=require(process.argv[1]);const D=require(process.argv[2]);"
              "process.stdout.write(JSON.stringify([M.tableroClientes(D,11.7),M.tableroClientes(D,12.4)]))")
        out = json.loads(subprocess.run(["node", "-e", js, str(MOTOR), str(DATOS)], capture_output=True, text=True,
                                        check=True).stdout)
        py = json.loads(json.dumps([self.t, ref.tablero_clientes(self.d, 12.4)]))

        def igual(a, b, r="$"):
            if isinstance(a, dict):
                self.assertEqual(set(a), set(b), r)
                for k in a:
                    igual(a[k], b[k], f"{r}.{k}")
            elif isinstance(a, list):
                self.assertEqual(len(a), len(b), r)
                for i, (x, y) in enumerate(zip(a, b)):
                    igual(x, y, f"{r}[{i}]")
            elif isinstance(a, float) or isinstance(b, float):
                self.assertAlmostEqual(a, b, delta=TOL * max(1, abs(a)), msg=r)
            else:
                self.assertEqual(a, b, r)
        igual(out, py)


if __name__ == "__main__":
    unittest.main()
