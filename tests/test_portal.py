"""SCRUM-73, 77 y 78: servidor del portal (src/portal/worker_api.js) contra una D1 simulada con node:sqlite.

Arma el _worker.js en una carpeta temporal con src/portal/armar_portal.py, lo corre en Node con
tests/_portal_runner.mjs y revisa cada respuesta: guardado de cotizaciones, permisos por rol, validación de lo que
se carga y el dólar del día.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "simulador"))
import motor_ref as ref  # noqa: E402

spec = importlib.util.spec_from_file_location("armar_portal", RAIZ / "src/portal/armar_portal.py")
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)


def node_con_sqlite():
    if shutil.which("node") is None:
        return False
    r = subprocess.run(["node", "-e", "require('node:sqlite')"], capture_output=True)
    return r.returncode == 0


@unittest.skipUnless(node_con_sqlite(), "hace falta Node 22 o superior (node:sqlite)")
class Portal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        ap.main(["--salida", cls.tmp.name])
        out = subprocess.run(["node", "--no-warnings", str(RAIZ / "tests/_portal_runner.mjs"), str(Path(cls.tmp.name) / "_worker.js")],
                             capture_output=True, text=True, check=True).stdout
        cls.r = json.loads(out)
        with open(ap.DATOS, encoding="utf-8") as f:
            cls.d = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def st(self, k):
        return self.r[k]["status"]

    def test_sirve_la_app_como_portal(self):
        self.assertEqual(self.st("html"), 200)
        self.assertTrue(self.r["html"]["cuerpo"]["portal"])
        self.assertEqual(self.st("post_raiz"), 405)
        self.assertEqual(self.st("no_existe"), 404)

    def test_dolar_del_dia(self):
        self.assertEqual(self.r["tc"]["cuerpo"], {**self.r["tc"]["cuerpo"], "valor": 11.65, "fecha": "2026-11-14", "origen": "repositorio"})
        sin = self.r["tc_sin_red"]["cuerpo"]
        self.assertEqual((sin["valor"], sin["fecha"], sin["origen"]), (self.d["tc"]["oficial"]["valor"], self.d["tc"]["oficial"]["fecha"], "incrustado"))

    def test_cotizacion_se_guarda_con_numero_y_precio_del_servidor(self):
        c = self.r["cot1"]
        self.assertEqual(c["status"], 201)
        self.assertEqual(c["cuerpo"]["numero"], 1)
        esperado = ref.cotizar(self.d, "REP-0022", 10, 11.65)
        self.assertAlmostEqual(c["cuerpo"]["total_bs"], esperado["total_bs"], places=6)
        self.assertNotEqual(c["cuerpo"]["total_bs"], 1)
        self.assertEqual(self.r["cot_cli"]["cuerpo"]["numero"], 2)

    def test_cotizacion_rechaza_datos_malos(self):
        for k, st in (("cot_cero", 400), ("cot_decimal", 400), ("cot_rep_mal", 400), ("cot_cli_mal", 400),
                      ("cot_json_mal", 400), ("cot_grande", 413)):
            self.assertEqual(self.st(k), st, k)
            self.assertIn("error", self.r[k]["cuerpo"], k)

    def test_listar_solo_importador(self):
        self.assertEqual(self.st("lista_anon"), 401)
        self.assertEqual(self.st("lista_prov"), 403)
        li = self.r["lista_imp"]["cuerpo"]
        self.assertEqual(self.st("lista_imp"), 200)
        self.assertEqual([f["numero"] for f in li["filas"]], [2, 1])
        self.assertEqual(li["filas"][1]["cliente_nombre"], "Taller Prueba")
        self.assertEqual((li["total"], li["convertidas"], li["no_convertidas"]), (2, 0, 2))
        self.assertEqual(self.st("lista_mes_mal"), 400)
        self.assertEqual([f["repuesto_id"] for f in self.r["lista_rep"]["cuerpo"]["filas"]], ["REP-0001"])

    def test_sesiones(self):
        self.assertEqual(self.st("entrar_mal"), 401)
        self.assertEqual(self.r["entrar_imp"]["cuerpo"]["rol"], "importador")
        self.assertEqual(self.r["yo_imp"]["cuerpo"]["rol"], "importador")
        self.assertEqual(self.st("yo_falso"), 401)
        self.assertEqual(self.st("otra_clave"), 401)
        self.assertEqual(self.st("sin_secreto"), 500)

    def test_alta_de_clientes(self):
        self.assertEqual(self.st("cli_anon"), 401)
        self.assertEqual(self.st("cli_prov"), 403)
        self.assertEqual(self.st("cli_tipo_mal"), 400)
        self.assertEqual(self.r["cli_ok"]["cuerpo"]["cliente_id"], "CLI-N001")
        self.assertEqual([c["nombre"] for c in self.r["clientes"]["cuerpo"]], ["Taller Nuevo"])

    def test_carga_de_repuestos(self):
        for k in ("rep_neg", "rep_fecha_mal", "rep_prov_mal", "rep_vacio"):
            self.assertEqual(self.st(k), 400, k)
        self.assertEqual(self.r["rep_ok"]["cuerpo"]["repuesto_id"], "REP-N001")
        pub = self.r["repuestos_pub"]["cuerpo"]
        self.assertEqual([p["repuesto_id"] for p in pub], ["REP-N001"])
        self.assertAlmostEqual(pub[0]["precio_venta_usd"], 11.9)
        self.assertEqual(self.st("cot_nuevo"), 201)  # lo cargado se puede cotizar

    def test_proveedor_ve_solo_lo_suyo(self):
        self.assertEqual(self.st("miprov_imp"), 403)
        m = self.r["miprov"]["cuerpo"]
        self.assertEqual(m["proveedor"]["proveedor_id"], "PROV-CN-03")
        propios = {r["repuesto_id"] for r in self.d["repuestos"] if r["proveedor_id"] == "PROV-CN-03"} | {"REP-N001"}
        self.assertEqual({a["id"] for a in m["repuestos"]}, propios)
        nuevo = next(a for a in m["repuestos"] if a["id"] == "REP-N001")
        self.assertEqual(nuevo["etiqueta"], "Sin datos")  # sin historial: no se inventa

    def test_marcar_venta_y_tablero(self):
        self.assertEqual(self.st("venta_prov"), 403)
        self.assertEqual(self.st("venta"), 200)
        self.assertEqual(self.st("venta_otra_vez"), 404)
        v = self.r["ventas_cli"]["cuerpo"]
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0][1:], ["REP-0001", "CLI-01", 3])

    def test_exportar_csv(self):
        c = self.r["csv"]
        self.assertTrue(c["tipo"].startswith("text/csv"))
        lineas = c["cuerpo"].strip().split("\n")
        self.assertTrue(lineas[0].startswith("numero,fecha,cliente_id"))
        self.assertEqual(len(lineas), 1 + 3)


if __name__ == "__main__":
    unittest.main()
