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
        liv = Path(cls.tmp.name) / "liviano"
        ap.main(["--salida", str(liv), "--liviano"])
        out = subprocess.run(["node", "--no-warnings", str(RAIZ / "tests/_portal_runner.mjs"), str(Path(cls.tmp.name) / "_worker.js"),
                              str(liv / "_worker.js"), str(ap.DATOS), str(ap.APP), str(ap.TIENDA)],
                             capture_output=True, text=True, check=True).stdout
        cls.r = json.loads(out)
        with open(ap.DATOS, encoding="utf-8") as f:
            cls.d = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def st(self, k):
        return self.r[k]["status"]

    def test_tienda_en_la_raiz_y_empresa_aparte(self):
        self.assertEqual(self.st("html"), 200)
        self.assertEqual(self.r["html"]["cuerpo"], {"portal": True, "tienda": True, "empresa": False})
        for k in ("empresa", "empresa_barra"):
            self.assertEqual(self.r[k]["cuerpo"], {"portal": True, "tienda": False, "empresa": True}, k)
        self.assertEqual(self.st("pagina_rara"), 404)
        self.assertEqual(self.r["html"]["robots"], "noindex, nofollow")
        self.assertEqual(self.r["empresa"]["robots"], "noindex, nofollow")
        self.assertEqual(self.st("post_raiz"), 405)
        self.assertEqual(self.st("no_existe"), 404)

    def test_dolar_del_dia(self):
        self.assertEqual(self.r["tc"]["cuerpo"], {**self.r["tc"]["cuerpo"], "valor": 11.65, "fecha": self.d["tc"]["oficial"]["fecha"], "origen": "repositorio"})
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
        self.assertEqual([f["numero"] for f in li["filas"]], [3, 2, 1])
        self.assertEqual(li["filas"][2]["cliente_nombre"], "Taller Prueba")
        self.assertEqual((li["total"], li["convertidas"], li["no_convertidas"]), (3, 0, 3))
        self.assertEqual(self.st("lista_mes_mal"), 400)
        self.assertEqual([f["repuesto_id"] for f in self.r["lista_rep"]["cuerpo"]["filas"]], ["REP-0001"])

    def test_correo_de_la_cotizacion_scrum83(self):
        # El envío es de demostración: el servidor valida el correo y lo guarda con la hora; no manda nada.
        c = self.r["cot_correo"]
        self.assertEqual(c["status"], 201)
        self.assertEqual(c["cuerpo"]["correo"], "compras@tallerelcruce.com")
        self.assertTrue(c["cuerpo"]["correo_enviado"])
        self.assertEqual(c["cuerpo"]["cliente_nombre"], "Taller El Cruce")
        self.assertAlmostEqual(c["cuerpo"]["total_bs"], ref.cotizar(self.d, "REP-0019", 12, 11.65)["total_bs"], places=6)
        self.assertEqual(self.st("cot_correo_mal"), 400)
        self.assertIn("correo", self.r["cot_correo_mal"]["cuerpo"]["error"].lower())
        self.assertEqual(self.st("cot_correo_largo"), 400)
        fila = next(f for f in self.r["lista_imp"]["cuerpo"]["filas"] if f["numero"] == c["cuerpo"]["numero"])
        self.assertEqual(fila["correo"], "compras@tallerelcruce.com")
        self.assertTrue(fila["correo_enviado"])
        # sin correo, como antes: se guarda igual y sin hora de envío
        self.assertIsNone(self.r["cot1"]["cuerpo"]["correo_enviado"])

    def test_migracion_agrega_columnas_de_correo(self):
        m = self.r["migracion"]
        self.assertIn("correo", m["columnas"])
        self.assertIn("correo_enviado", m["columnas"])
        self.assertEqual(self.st("cot_migrada"), 201)
        self.assertEqual(m["filas"], [{"numero": 1, "correo": None}, {"numero": 2, "correo": "a@b.co"}])

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

    def test_venta_de_la_tienda_llega_a_clientes_error_e2(self):
        # Antes del arreglo, /api/ventas-clientes filtraba cliente_id IS NOT NULL y la venta de la tienda se perdía.
        self.assertEqual(self.st("venta_web"), 200)
        v = self.r["ventas_cli_web"]["cuerpo"]
        self.assertEqual(len(v), 2)
        self.assertIn(["REP-0022", "CLI-WEB", 10], [x[1:] for x in v])
        self.assertIn(["REP-0001", "CLI-01", 3], [x[1:] for x in v])

    def test_catalogos_pdf_desde_el_portal_error_e3(self):
        self.assertEqual(self.st("pdf_ok"), 200)
        self.assertEqual(self.r["pdf_ok"]["tipo"], "application/pdf")
        self.assertEqual(self.r["pdf_pedidos"], ["/catalogos/catalogo_baja.pdf"])  # la ruta rara no llega a ASSETS
        self.assertEqual(self.st("pdf_raro"), 404)
        self.assertEqual(self.st("pdf_sin_assets"), 404)

    def test_armar_copia_los_catalogos(self):
        for pdf in ("catalogo_baja.pdf", "catalogo_30.pdf"):
            f = Path(self.tmp.name) / "catalogos" / pdf
            self.assertTrue(f.is_file(), pdf)
            self.assertEqual(f.read_bytes()[:5], b"%PDF-")

    def test_codigo_nuevo_sin_choque_tras_borrar(self):
        self.assertEqual(self.r["cli_2"]["cuerpo"]["cliente_id"], "CLI-N002")
        self.assertEqual(self.st("cli_tras_borrar"), 201)
        self.assertEqual(self.r["cli_tras_borrar"]["cuerpo"]["cliente_id"], "CLI-N003")
        self.assertEqual(self.r["rep_2"]["cuerpo"]["repuesto_id"], "REP-N002")
        self.assertEqual(self.st("rep_tras_borrar"), 201)
        self.assertEqual(self.r["rep_tras_borrar"]["cuerpo"]["repuesto_id"], "REP-N003")
        self.assertEqual(self.r["cli_base_vieja"]["cuerpo"]["cliente_id"], "CLI-N008")

    def base(self, rid):
        return next(r["stock_al_2026_11_10"] for r in self.d["repuestos"] if r["repuesto_id"] == rid)

    def test_d6_venta_descuenta_stock(self):
        d6 = self.r["d6"]
        self.assertEqual(d6["rep1_tras_venta"], self.base("REP-0001") - 3)
        self.assertEqual(d6["rep5_antes"], self.base("REP-0005"))
        self.assertEqual(d6["rep5_tras_cotizar"], self.base("REP-0005"))  # cotizar no descuenta ni reserva
        v = self.r["d6_venta_justa"]
        self.assertEqual(v["status"], 200, v)
        self.assertEqual((v["cuerpo"]["stock_antes"], v["cuerpo"]["stock_despues"]), (4, 0))
        self.assertEqual(d6["rep5_tras_venta"], 0)
        self.assertEqual(d6["cot_sin_stock"], {"en_stock": 0, "por_pedir": 2})  # el cotizador ve el stock vigente
        self.assertEqual(d6["n002_pub"], 0)  # repuesto cargado con stock 2, vendido 2
        mp = {a["id"]: a["stock"] for a in self.r["d6_miprov"]["cuerpo"]["repuestos"]}
        self.assertEqual(mp["REP-0001"], self.base("REP-0001") - 3)
        antes = {a["id"]: a["stock"] for a in self.r["miprov"]["cuerpo"]["repuestos"]}
        self.assertEqual(antes["REP-0001"], self.base("REP-0001"))

    def test_d6_venta_que_deja_negativo_409_y_forzar(self):
        r = self.r["d6_venta_negativa"]
        self.assertEqual(r["status"], 409)
        self.assertIn("No hay stock suficiente", r["cuerpo"]["error"])
        self.assertEqual((r["cuerpo"]["stock"], r["cuerpo"]["stock_despues"]), (0, -2))
        self.assertEqual(self.r["d6"]["rep5_tras_409"], 0)  # el 409 no escribe nada
        self.assertEqual(self.r["d6"]["cot6_tras_409"], 0)
        self.assertEqual(self.st("d6_forzar_texto"), 409)  # solo forzar: true fuerza
        f = self.r["d6_venta_forzada"]
        self.assertEqual(f["status"], 200, f)
        self.assertTrue(f["cuerpo"]["forzada"])
        self.assertEqual(self.r["d6"]["rep5_forzado"], -2)
        self.assertEqual(self.st("d6_forzada_otra_vez"), 404)  # no descuenta dos veces
        self.assertEqual(self.r["d6"]["rep5_final"], -2)
        # con stock negativo, el motor recibe 0: en almacén no hay nada y todo va por pedir
        self.assertEqual(self.r["d6"]["cot_con_negativo"], {"stock": 0, "en_stock": 0, "por_pedir": 3})

    def test_d6_movimientos(self):
        self.assertEqual(self.st("d6_mov_anon"), 401)
        self.assertEqual(self.st("d6_mov_prov"), 403)
        mov = self.r["d6_mov"]["cuerpo"]
        self.assertEqual([(m["cantidad"], m["motivo"], m["usuario"]) for m in mov], [(-2, "venta", "importador"), (-4, "venta", "importador")])
        self.assertTrue(all(m["cotizacion"] for m in mov))

    def test_exportar_csv(self):
        c = self.r["csv"]
        self.assertTrue(c["tipo"].startswith("text/csv"))
        lineas = c["cuerpo"].strip().split("\n")
        self.assertTrue(lineas[0].startswith("numero,fecha,cliente_id"))
        self.assertEqual(len(lineas), 1 + 4)
        self.assertTrue(lineas[0].endswith(",correo,correo_enviado"))
        self.assertTrue(any("compras@tallerelcruce.com" in l for l in lineas[1:]))

    def test_liviano_lee_datos_y_app_de_la_rama(self):
        self.assertEqual(self.st("liv_caido"), 503)
        self.assertEqual(self.st("liv_html"), 200)
        self.assertEqual(self.r["liv_html"]["cuerpo"], {"portal": True, "tienda": True, "empresa": False})
        self.assertEqual(self.r["liv_empresa"]["cuerpo"], {"portal": True, "tienda": False, "empresa": True})
        self.assertEqual(self.st("liv_cot"), 201)
        esperado = ref.cotizar(self.d, "REP-0022", 10, 11.65)
        self.assertAlmostEqual(self.r["liv_cot"]["cuerpo"]["total_bs"], esperado["total_bs"], places=6)


class PortalLiviano(unittest.TestCase):
    def test_liviano_no_incluye_datos(self):
        t = ap.armar(liviano=True)
        self.assertNotIn("DATOS_INCLUIDOS =", t)
        self.assertLess(len(t), 80_000)
        self.assertIn("DATOS_INCLUIDOS =", ap.armar())


if __name__ == "__main__":
    unittest.main()
