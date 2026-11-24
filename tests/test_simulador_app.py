"""Pruebas de la app del simulador (SCRUM-64): datos, armado del HTML y textos prohibidos.

La app se arma con el motor real (src/simulador/motor.js, frente A).
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

CLAVES = {"generado", "corte", "tc", "repuestos", "proveedores", "ventas", "clasificacion", "catalogo", "clientes", "prediccion", "parametros"}

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
        # El paralelo es la ÚLTIMA fila de su serie diaria, tampoco con fecha fija.
        with open(pd.PARALELO, encoding="utf-8", newline="") as f:
            up = sorted(csv.DictReader(f), key=lambda r: r["fecha"])[-1]
        self.assertEqual(tc["paralelo"]["valor"], float(up["paralelo_bs_por_usd"]))
        self.assertEqual(tc["paralelo"]["fecha"], up["fecha"])
        self.assertEqual(tc["paralelo"]["fuente"], up["fuente"])
        self.assertEqual(tc["paralelo"]["marca"], "PRIVADO")
        self.assertEqual(tc["paralelo"]["serie"][-1], [up["fecha"], float(up["paralelo_bs_por_usd"])])

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
        cls.datos, cls.html = ga.generar(ga.MOTOR, cls.salida)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_mineria_oculta_las_pantallas_que_devuelve_error_e1(self):
        # Error E1 (auditoría del 24-11-2026): al cambiar de pestaña en «Minería de datos», las pantallas prestadas
        # volvían a su lugar visibles y quedaban encima. La prueba en el navegador está en el PR; aquí se fija el código.
        i = self.html.index("function devolverPrestadas(){")
        cuerpo = self.html[i:self.html.index("\n}", i)]
        self.assertIn("s.hidden = true", cuerpo)

    def test_incrusta_datos_motor_y_logo(self):
        h = self.html
        for marca in ga.MARCAS:
            self.assertNotIn(marca, h)
        self.assertIn('"repuesto_id":"REP-0030"', h)
        self.assertIn("module.exports = Motor", h)
        self.assertIn("data:image/jpeg;base64,", h)
        self.assertEqual(h.lower().count("</script>"), 3)  # datos, motor y código de la app

    def test_vistas_sin_mis_decisiones(self):
        for v in ["dashboard", "predicciones", "rotacion", "alertas", "simulador", "proveedores", "plan", "temporadas", "clientes",
                  "catalogo", "cotizar"]:
            self.assertIn(f'id="v-{v}"', self.html)
        self.assertNotIn("Mis decisiones", self.html)

    def test_quitado_el_16_11(self):
        # Pedido de Fio y Sam (16-11-2026): sin «¿Qué hubiera pasado?», sin «Clasificación de repuestos» y sin selector de dólar.
        for x in ['id="v-backtest"', 'id="v-clasificacion"', '"#backtest"', '"#clasificacion"', 'id="tcsel"', 'id="f-otro"',
                  "Dólar para calcular", "tcModo", "dólar elegido"]:
            self.assertNotIn(x, self.html)

    def test_textos_y_ayuda_del_17_11(self):
        # SCRUM-82, decisión de Sam (17-11-2026): ninguna marca de dato simulado en pantalla, salvo una nota única al pie
        # del menú (y de la tienda), e ícono «i» con su explicación. Se leen las plantillas sin sus comentarios, porque
        # la app generada trae los datos con su campo origen_dato, que sí dice SINTÉTICO.
        nota = "Ventas: base pública carparts. Clientes, proveedores, precios y stock: datos de demostración."
        marcas = re.compile(r"SINTÉTIC|ILUSTRATIV|\bsimulad[oa]s?\b|TRAMOS DE EJEMPLO|historia nueva", re.I)
        for ruta in (RAIZ / "src/simulador/plantilla_app.html", RAIZ / "src/tienda/plantilla_tienda.html"):
            txt = ruta.read_text(encoding="utf-8")
            visible = re.sub(r"<!--.*?-->|/\*.*?\*/|^\s*//.*$", "", txt, flags=re.S | re.M)
            self.assertIn(nota, visible, ruta.name)
            self.assertEqual([m.group(0) for m in marcas.finditer(visible)], [], ruta.name)
            self.assertIn('class="info"', txt, ruta.name)
            self.assertIn('querySelectorAll("[data-i]")', txt, ruta.name)
        # control: el patrón sí detecta una marca cuando está
        self.assertTrue(marcas.search("Precio SINTÉTICO"))
        # el ícono es un botón real (teclado y toque), con nombre accesible, y hay muchos en la app
        self.assertGreaterEqual(self.html.count("${info(") + self.html.count("data-i=\""), 60)
        self.assertIn('aria-label="Qué es: ${esc(tema)}"', self.html)

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



# ---- Dólar paralelo diario (src/scrum-54/obtener_paralelo.py) ----
sys.path.insert(0, str(RAIZ / "src" / "scrum-54"))
import obtener_paralelo as op  # noqa: E402

PAGINA = ('<html><script type="application/ld+json">{"@graph":[{"@id":"https://dolarbolivia.net#rate-oficial",'
          '"currentExchangeRate":{"price":11.75}},{"@id":"https://dolarbolivia.net#rate-paralelo",'
          '"currentExchangeRate":{"price":11.95}}]}</script></html>')
BINANCE = json.dumps({"data": [{"adv": {"price": p}} for p in ("11.98", "11.99", "12.00", "11.99")]})


def red(respuestas):
    """Imita urllib: cada URL devuelve su texto o lanza el error indicado."""
    def pedir(url, cuerpo=None):
        r = respuestas[url]
        if isinstance(r, Exception):
            raise r
        return r
    return pedir


class DolarParalelo(unittest.TestCase):
    def test_fuente_principal(self):
        v, f = op.leer_fuentes("P", "R", red({"P": PAGINA, "R": OSError("no debe usarse")}))
        self.assertEqual((v, f.split(",")[0]), (11.95, "dolarbolivia.net"))

    def test_principal_caida_pasa_a_binance(self):
        v, f = op.leer_fuentes("P", "R", red({"P": OSError("caída"), "R": BINANCE}))
        self.assertEqual(v, 11.99)
        self.assertTrue(f.startswith("Binance P2P"))

    def test_principal_cambiada_pasa_a_binance(self):
        v, _ = op.leer_fuentes("P", "R", red({"P": "<html>sin datos</html>", "R": BINANCE}))
        self.assertEqual(v, 11.99)

    def test_valor_absurdo_se_descarta(self):
        with self.assertRaises(op.SinDato):
            op.leer_fuentes("P", "R", red({"P": PAGINA.replace("11.95", "1195"), "R": json.dumps({"data": []})}))

    def test_fuentes_caidas_no_tocan_el_csv(self):
        with tempfile.TemporaryDirectory() as t:
            csvp = Path(t) / "paralelo.csv"
            antes = "fecha,paralelo_bs_por_usd,fuente,fecha_lectura,marca\n2026-10-23,11.99,x,2026-10-25,PRIVADO\n"
            csvp.write_text(antes, encoding="utf-8")
            rc = op.main(["--url-principal", "http://127.0.0.1:9/", "--url-respaldo", "http://127.0.0.1:9/", "--salida", str(csvp)])
            self.assertEqual(rc, 1)
            self.assertEqual(csvp.read_bytes(), antes.encode())

    def test_una_fila_por_dia(self):
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as t:
            csvp = Path(t) / "p.csv"
            op.actualizar(11.9, "A", datetime(2026, 11, 20, 14, tzinfo=timezone.utc), csvp)
            op.actualizar(11.95, "B", datetime(2026, 11, 20, 22, tzinfo=timezone.utc), csvp)   # mismo día en Bolivia
            op.actualizar(12.0, "C", datetime(2026, 11, 21, 3, tzinfo=timezone.utc), csvp)    # 23:00 del 20 en Bolivia
            with csvp.open(encoding="utf-8", newline="") as f:
                filas = list(csv.DictReader(f))
            self.assertEqual([(r["fecha"], r["paralelo_bs_por_usd"], r["fuente"]) for r in filas], [("2026-11-20", "12.00", "C")])
            self.assertEqual(filas[0]["marca"], "PRIVADO")

if __name__ == "__main__":
    unittest.main()
