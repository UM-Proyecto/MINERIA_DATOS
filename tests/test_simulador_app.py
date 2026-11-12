"""Pruebas de la app del simulador (SCRUM-64): datos, armado del HTML y textos prohibidos.

El motor real (src/simulador/motor.js) lo construye el frente A. Mientras no esté, las pruebas arman la app con
tests/_motor_stub.js, que respeta la misma API.
"""
import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "simulador"
sys.path.insert(0, str(SRC))
import preparar_datos as pd  # noqa: E402
import generar_app as ga  # noqa: E402

STUB = RAIZ / "tests" / "_motor_stub.js"
CLAVES = {"generado", "corte", "tc", "repuestos", "proveedores", "ventas", "clasificacion", "parametros"}

# Textos que no pueden aparecer en la app (ver contrato y pedido de claudia-mineria del 12-nov-2026).
PROHIBIDOS = [
    (r"nivel de servicio", re.I),
    (r"pasa al precio de venta", re.I),
    (r"\bRP0\d\d\b", 0),          # códigos viejos de repuesto
    (r"\bPR\d\d\b", 0),           # códigos viejos de proveedor
    (r"\bHU-(5[3-9]|6\d|7\d)\b", 0),  # las historias nuevas se llaman SCRUM-nn
    (r"\b(tenés|podés|acá|querés|elegí)\b", re.I),  # voseo: el texto va en español neutro
]


class DatosApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = pd.preparar()

    def test_claves_del_contrato(self):
        self.assertEqual(set(self.d), CLAVES)
        self.assertEqual(set(self.d["tc"]), {"oficial", "serie", "paralelo"})
        self.assertEqual(set(self.d["parametros"]), {"costo_pedido_bs", "costo_capital_mensual", "simulaciones", "semilla"})
        self.assertEqual(self.d["corte"], self.d["tc"]["oficial"]["fecha"])

    def test_treinta_repuestos_con_numeros(self):
        reps = self.d["repuestos"]
        self.assertEqual(len(reps), 30)
        self.assertEqual([r["repuesto_id"] for r in reps], [f"REP-{i:04d}" for i in range(1, 31)])
        for r in reps:
            self.assertIsInstance(r["costo_unitario_usd"], float)
            self.assertIsInstance(r["stock_al_2026_11_10"], int)
            self.assertIsInstance(r["codigo_carparts"], str)
        self.assertEqual(set(self.d["ventas"]), {r["repuesto_id"] for r in reps})
        self.assertTrue(all(len(v) == 51 for v in self.d["ventas"].values()))

    def test_dolar_oficial_y_paralelo(self):
        tc = self.d["tc"]
        # El oficial es la ÚLTIMA fila del CSV del BCB, sin valor fijo.
        with open(pd.TCO, encoding="utf-8-sig", newline="") as f:
            ultima = list(csv.DictReader(f))[-1]
        self.assertEqual(tc["oficial"]["valor"], float(ultima["tco_bs_por_usd"]))
        self.assertEqual(tc["oficial"]["fecha"], ultima["fecha"])
        self.assertEqual(tc["serie"][-1], [ultima["fecha"], float(ultima["tco_bs_por_usd"])])
        self.assertIn("BCB", tc["oficial"]["fuente"])
        self.assertEqual(tc["serie"][0], ["2026-06-27", 9.73])
        self.assertEqual(tc["paralelo"]["valor"], 11.99)
        self.assertEqual(tc["paralelo"]["fecha"], "2026-10-23")
        self.assertEqual(tc["paralelo"]["marca"], "PRIVADO")

    def test_clasificacion(self):
        c = self.d["clasificacion"]
        self.assertEqual(c["conteo"]["intermitente"], 2294)
        self.assertEqual(sum(c["conteo"].values()), 2674)
        self.assertEqual(len(c["puntos"]), 2674 - c["conteo"]["sin clasificar"])
        self.assertTrue(all(len(p) == 3 and isinstance(p[0], float) for p in c["puntos"]))

    def test_json_guardado_igual_al_calculado(self):
        guardado = json.loads(pd.SALIDA.read_text(encoding="utf-8"))
        guardado["generado"] = self.d["generado"]
        self.assertEqual(guardado, json.loads(json.dumps(self.d)))


class ArmadoApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.salida = Path(cls.tmp.name) / "app.html"
        cls.datos, cls.html = ga.generar(STUB, cls.salida)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_incrusta_datos_motor_y_logo(self):
        h = self.html
        for marca in ga.MARCAS:
            self.assertNotIn(marca, h)
        self.assertIn('"repuesto_id":"REP-0030"', h)
        self.assertIn("module.exports = Motor", h)
        self.assertIn("data:image/jpeg;base64,", h)
        self.assertEqual(h.lower().count("</script>"), 3)  # datos, motor y código de la app

    def test_seis_vistas_sin_mis_decisiones(self):
        for v in ["alertas", "simulador", "proveedores", "plan", "backtest", "clasificacion"]:
            self.assertIn(f'id="v-{v}"', self.html)
        self.assertNotIn("Mis decisiones", self.html)

    def test_sin_textos_prohibidos(self):
        for patron, flags in PROHIBIDOS:
            self.assertIsNone(re.search(patron, self.html, flags), patron)

    def test_ids_unicos(self):
        ids = re.findall(r'\bid="([^"$]+)"', self.html)
        repetidos = {i for i in ids if ids.count(i) > 1}
        self.assertEqual(repetidos, set())

    def test_falla_sin_motor(self):
        with self.assertRaises(SystemExit) as cm:
            ga.generar(Path(self.tmp.name) / "no_existe.js", self.salida)
        self.assertIn("motor", str(cm.exception.code))

    def test_falla_sin_motor_por_linea_de_comandos(self):
        r = subprocess.run([sys.executable, str(SRC / "generar_app.py"), "--motor", str(Path(self.tmp.name) / "no.js"),
                            "--salida", str(Path(self.tmp.name) / "x.html")], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No existe el motor", r.stderr)
        self.assertFalse((Path(self.tmp.name) / "x.html").exists())

    def test_rechaza_un_js_que_no_es_el_motor(self):
        otro = Path(self.tmp.name) / "otro.js"
        otro.write_text("console.log(1)", encoding="utf-8")
        with self.assertRaises(SystemExit):
            ga.generar(otro, self.salida)

    def test_escape_de_script(self):
        self.assertEqual(ga.seguro_en_script("a</script>b i</n"), "a<\\/script>b i</n")


if __name__ == "__main__":
    unittest.main()
