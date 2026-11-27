"""SCRUM-79, versión empresarial del Tablero de ventas (27-11-2026).

La pantalla es para un gerente que no sabe de estadística. Todo lo que muestra sale de Motor.tableroEmpresa (con su
copia motor_ref.tablero_empresa; la equivalencia JS/Python está en test_dashboard_prediccion). Estas pruebas revisan:
- que los porcentajes de cada dona sean enteros que suman 100;
- que el filtro de período cambie las cifras, y que lo que es de hoy no cambie;
- que las cifras cuadren con Motor.dashboard, alertas y rotacion;
- que cada frase de conclusión salga de los datos: cambia si cambian los datos y no está escrita en la plantilla;
- que no aparezcan términos técnicos en la vista ni en las frases;
- que la vista solo dibuje lo del motor, con botones reales y gráficos con role="img" y aria-label.
"""
import copy
import json
import os
import re
import sys
import unittest
from pathlib import Path

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RAIZ, "src", "simulador"))
sys.path.insert(0, os.path.dirname(__file__))
import motor_ref as ref  # noqa: E402
from test_lenguaje_simple import RX, visible  # noqa: E402

DATOS = os.path.join(RAIZ, "data", "processed", "simulador", "datos_app.json")
PLANTILLA = os.path.join(RAIZ, "src", "simulador", "plantilla_app.html")
TC = 11.67
# Además de la tabla A.4 (test_lenguaje_simple), palabras que en esta pantalla tampoco van.
EXTRA = re.compile(r"[Rr]otaci[oó]n|[Aa]cumulaci[oó]n|\bABC\b|[Pp]ercentil|[Mm]ediana|[Dd]esv[ií]o|[Ee]stad[ií]stic|"
                   r"[Ii]ntermitente|[Pp]ron[oó]stico|[Mm]odelo|[Pp]robabilidad")


def cargar():
    with open(DATOS, encoding="utf-8") as f:
        return json.load(f)


def textos(t):
    """Todo el texto que el motor le pasa a la pantalla: frases y rótulos."""
    salida = list(t["conclusiones"].values()) + [a["etiqueta"] for a in t["hoy"]["almacen"]]
    if not t["vacio"]:
        salida += [x["tipo"] for x in t["tipos_cliente"]] + [x["categoria"] for x in t["categorias"]]
        salida += [x["nombre_corto"] for x in t["repuestos"]] + [x["nombre"] for x in t["clientes"]]
    return salida


class Donas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()

    def test_porcentajes_enteros_que_suman_100(self):
        for periodo in ("12m", "todo"):
            t = ref.tablero_empresa(self.d, TC, periodo)
            for nombre, partes in (("tipos", t["tipos_cliente"]), ("almacén", t["hoy"]["almacen"])):
                pcts = [p["pct"] for p in partes]
                self.assertEqual(sum(pcts), 100, (periodo, nombre, pcts))
                self.assertTrue(all(isinstance(p, int) and p >= 0 for p in pcts), pcts)
                self.assertLessEqual(len(partes), ref.DONA_MAX)

    def test_semaforo_cuenta_los_30_y_cuadra_con_las_alertas(self):
        t = ref.tablero_empresa(self.d, TC)
        al = ref.alertas(self.d, TC)
        self.assertEqual(t["hoy"]["almacen_total"], len(self.d["repuestos"]))
        cuenta = {a["clave"]: a["repuestos"] for a in t["hoy"]["almacen"]}
        self.assertEqual(cuenta["pedir"], sum(1 for a in al if a["est"] == 0))
        self.assertEqual(cuenta["vigilar"], sum(1 for a in al if a["est"] == 1))
        self.assertEqual(cuenta["suficiente"], sum(1 for a in al if a["est"] == 2))
        self.assertAlmostEqual(t["hoy"]["pedir_ya"]["costo_bs"], sum(a["costo_bs"] for a in al if a["est"] == 0), places=6)
        r = ref.rotacion(self.d, TC)
        self.assertEqual(t["hoy"]["dinero_parado"], {"valor_bs": r["valor_acumulado_bs"], "repuestos": r["acumulacion"]})

    def test_resto_mayor(self):
        self.assertEqual(ref.enteros100([1, 1, 1]), [34, 33, 33])
        self.assertEqual(ref.enteros100([0, 0]), [0, 0])
        self.assertEqual(sum(ref.enteros100([3, 4, 23])), 100)
        self.assertEqual(ref.enteros100([5, 0]), [100, 0])

    def test_mas_de_cinco_tipos_se_juntan_en_otros(self):
        d = copy.deepcopy(self.d)
        for i, c in enumerate(d["clientes"]["lista"][:6]):
            c["tipo"] = f"Tipo {i}"
        t = ref.tablero_empresa(d, TC)
        self.assertEqual(len(t["tipos_cliente"]), ref.DONA_MAX)
        self.assertEqual(t["tipos_cliente"][-1]["tipo"], "Otros")
        self.assertEqual(sum(x["pct"] for x in t["tipos_cliente"]), 100)


class Periodo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()
        cls.a = ref.tablero_empresa(cls.d, TC, "12m")
        cls.b = ref.tablero_empresa(cls.d, TC, "todo")
        cls.db = ref.dashboard(cls.d, TC)

    def test_el_filtro_cambia_las_cifras(self):
        self.assertEqual(self.a["meses_periodo"], 12)
        self.assertEqual(self.b["meses_periodo"], len(self.db["meses"]))
        self.assertNotEqual(self.a["tarjetas"]["ventas_bs"], self.b["tarjetas"]["ventas_bs"])
        self.assertNotEqual(self.a["tarjetas"]["unidades"], self.b["tarjetas"]["unidades"])
        self.assertNotEqual([x["tipo"] for x in self.a["tipos_cliente"]], [x["tipo"] for x in self.b["tipos_cliente"]])
        self.assertNotEqual([x["id"] for x in self.a["top_repuestos"]], [x["id"] for x in self.b["top_repuestos"]])
        self.assertNotEqual(self.a["conclusiones"]["meses"], self.b["conclusiones"]["meses"])

    def test_cuadra_con_el_dashboard(self):
        self.assertAlmostEqual(self.a["tarjetas"]["ventas_bs"], self.db["ult12_bs"], places=6)
        self.assertAlmostEqual(self.b["tarjetas"]["ventas_bs"], self.db["total"]["monto_bs"], places=6)
        self.assertEqual(self.b["tarjetas"]["unidades"], self.db["total"]["unidades"])
        for t in (self.a, self.b):
            for lista in ("meses", "tipos_cliente", "categorias", "clientes", "repuestos"):
                self.assertAlmostEqual(sum(x["monto_bs"] for x in t[lista]), t["tarjetas"]["ventas_bs"], places=4, msg=lista)
            self.assertEqual(sum(x["unidades"] for x in t["repuestos"]), t["tarjetas"]["unidades"])
            self.assertEqual(len(t["top_clientes"]), 5)
            self.assertEqual(len(t["top_repuestos"]), 10)
            self.assertEqual(len(t["categorias"]), 8)
            self.assertEqual(t["mejor_mes"]["monto_bs"], max(x["monto_bs"] for x in t["meses"]))

    def test_lo_de_hoy_y_los_anios_no_dependen_del_periodo(self):
        self.assertEqual(self.a["hoy"], self.b["hoy"])
        self.assertEqual(self.a["por_anio"], self.b["por_anio"])
        self.assertEqual(self.a["conclusiones"]["almacen"], self.b["conclusiones"]["almacen"])
        self.assertEqual(self.a["tarjetas"]["comparacion"], self.b["tarjetas"]["comparacion"])

    def test_anios_incompletos(self):
        inc = [a for a in self.a["por_anio"] if not a["completo"]]
        self.assertTrue(inc)
        self.assertTrue(all(a["meses"] < 12 for a in inc))

    def test_periodo_desconocido_es_12_meses(self):
        self.assertEqual(ref.tablero_empresa(self.d, TC, "otro")["tarjetas"], self.a["tarjetas"])

    def test_sin_ventas(self):
        d = copy.deepcopy(self.d)
        d["clientes"]["ventas"] = []
        t = ref.tablero_empresa(d, TC)
        self.assertTrue(t["vacio"])
        self.assertEqual(sum(a["pct"] for a in t["hoy"]["almacen"]), 100)


class Conclusiones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cargar()
        cls.t = ref.tablero_empresa(cls.d, TC)
        cls.html = Path(PLANTILLA).read_text(encoding="utf-8")

    def test_una_frase_por_grafico(self):
        self.assertEqual(set(self.t["conclusiones"]), {"meses", "tipos_cliente", "almacen", "categorias", "top_clientes", "top_repuestos", "anios"})
        self.assertTrue(all(f.strip().endswith(".") for f in self.t["conclusiones"].values()))

    def test_las_cifras_de_las_frases_son_las_del_motor(self):
        t, c = self.t, self.t["conclusiones"]
        self.assertIn(ref.bs_txt(t["mejor_mes"]["monto_bs"]), c["meses"])
        self.assertIn(ref.mes_largo(t["mejor_mes"]["mes"]), c["meses"].lower())
        self.assertIn(ref.bs_txt(t["promedio_mes_bs"]), c["meses"])
        self.assertIn(f"{t['tipos_cliente'][0]['pct']} %", c["tipos_cliente"])
        self.assertIn(ref.miles(t["top_clientes_pct"]) + " %", c["top_clientes"])
        self.assertIn(f"(de {t['clientes_total']})", c["top_clientes"])
        self.assertIn(ref.miles(t["top_repuestos_pct"]) + " %", c["top_repuestos"])
        self.assertIn(t["categorias"][0]["categoria"].lower(), c["categorias"])
        self.assertIn(str(t["hoy"]["pedir_ya"]["repuestos"]), c["almacen"])

    def test_cambian_si_cambian_los_datos(self):
        # Se triplican las ventas del primer mes del período: pasa a ser el mejor mes y la frase lo dice.
        d = copy.deepcopy(self.d)
        primero = self.t["meses"][0]["mes"]
        d["clientes"]["ventas"] = [v[:3] + [v[3] * 3] if v[0] == primero and isinstance(v[3], int) else v for v in d["clientes"]["ventas"]]
        t2 = ref.tablero_empresa(d, TC)
        self.assertEqual(t2["mejor_mes"]["mes"], primero)
        self.assertIn(ref.mes_largo(primero), t2["conclusiones"]["meses"].lower())
        self.assertNotEqual(t2["conclusiones"]["meses"], self.t["conclusiones"]["meses"])
        # Con todos los clientes de un mismo tipo, la dona tiene una sola porción de 100 % y la frase la nombra.
        d = copy.deepcopy(self.d)
        for x in d["clientes"]["lista"]:
            x["tipo"] = "Repuestera"
        t3 = ref.tablero_empresa(d, TC)
        self.assertEqual([(x["tipo"], x["pct"]) for x in t3["tipos_cliente"]], [("Repuestera", 100)])
        self.assertIn("las repuesteras (100 %)", t3["conclusiones"]["tipos_cliente"])

    def test_variantes_de_la_frase(self):
        # Pocos clientes concentrados frente a ventas repartidas: la frase elige según el porcentaje.
        self.assertGreaterEqual(self.t["top_clientes_pct"], 50)
        self.assertIn("Si uno deja de comprar", self.t["conclusiones"]["top_clientes"])
        d = copy.deepcopy(self.d)
        d["clientes"]["lista"] += [{"cliente_id": f"CLI-X{i}", "nombre": f"Cliente {i}", "tipo": "Particular", "zona": "x"} for i in range(40)]
        mes = self.t["hasta"]
        d["clientes"]["ventas"] += [[mes, "REP-0019", f"CLI-X{i}", 5] for i in range(40)]
        t = ref.tablero_empresa(d, TC)
        self.assertLess(t["top_clientes_pct"], 50)
        self.assertIn("repartidas entre muchos clientes", t["conclusiones"]["top_clientes"])

    def test_no_estan_escritas_en_la_plantilla(self):
        # Ni las frases ni sus cifras están en la página: las arma el motor con los datos.
        for periodo in ("12m", "todo"):
            for f in ref.tablero_empresa(self.d, TC, periodo)["conclusiones"].values():
                self.assertNotIn(f, self.html)
        self.assertNotIn(ref.bs_txt(self.t["mejor_mes"]["monto_bs"]), self.html)
        self.assertNotIn("fue el mejor mes", self.html)

    def test_formato_boliviano(self):
        self.assertEqual(ref.miles(13445.4), "13.445")
        self.assertEqual(ref.miles(1234567.5), "1.234.568")
        self.assertEqual(ref.miles(-0.2), "0")
        self.assertEqual(ref.miles(-1500), "−1.500")
        self.assertEqual(ref.bs_txt(999.5), "Bs 1.000")
        self.assertEqual(ref.nombre_corto("Cubo y rodamiento de rueda delantero con sensor ABS"), "Cubo y rodamiento de rueda delantero…")
        self.assertEqual(ref.nombre_corto("Filtro de aceite"), "Filtro de aceite")


class SinTerminosTecnicos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = Path(PLANTILLA).read_text(encoding="utf-8")
        vista = html[html.index('<section class="vista db" id="v-dashboard"'):html.index("<!-- ============ PREDICCIONES (SCRUM-80)")]
        codigo = html[html.index("/* ==================== DASHBOARD (SCRUM-79)"):html.index("/* ==================== PREDICCIONES (SCRUM-80)")]
        cls.vista = visible("<body>" + vista)
        cls.codigo = visible("<body><script>" + codigo)
        cls.d = cargar()

    def test_control_positivo(self):
        self.assertTrue(RX.search("el punto de pedido"))
        self.assertTrue(EXTRA.search("dinero en acumulación"))
        self.assertTrue(RX.search(visible('<body><p>Promedio móvil</p>')))

    def test_vista_y_codigo_sin_terminos(self):
        for nombre, texto in (("vista", self.vista), ("código", self.codigo)):
            self.assertEqual([m.group(0) for m in RX.finditer(texto)], [], nombre)
        # En el texto visible de la vista tampoco van las palabras de EXTRA.
        self.assertEqual([m.group(0) for m in EXTRA.finditer(re.sub(r"<[^>]+>", " ", self.vista))], [])

    def test_frases_y_rotulos_del_motor_sin_terminos(self):
        d2 = copy.deepcopy(self.d)
        d2["repuestos"][1] = dict(d2["repuestos"][1], stock_al_2026_11_10="")
        for d in (self.d, d2):
            for periodo in ("12m", "todo"):
                for txt in textos(ref.tablero_empresa(d, TC, periodo)):
                    self.assertIsNone(RX.search(txt), txt)
                    self.assertIsNone(EXTRA.search(txt), txt)


class Vista(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = Path(PLANTILLA).read_text(encoding="utf-8")
        cls.vista = html[html.index('<section class="vista db" id="v-dashboard"'):html.index("<!-- ============ PREDICCIONES (SCRUM-80)")]
        cls.codigo = html[html.index("/* ==================== DASHBOARD (SCRUM-79)"):html.index("/* ==================== PREDICCIONES (SCRUM-80)")]
        cls.pinta = cls.codigo[cls.codigo.index("function pintarDashboard()"):cls.codigo.index('$("b-db-rep").addEventListener')]

    def test_solo_dibuja_lo_del_motor(self):
        self.assertIn("Motor.tableroEmpresa(DM(), tcHoy(), S.dbPer)", self.pinta)
        for otro in ("Motor.dashboard(", "Motor.alertas(", "Motor.rotacion(", "alertas()", ".reduce("):
            self.assertNotIn(otro, self.pinta, otro)
        for f in ("meses", "tipos_cliente", "almacen", "categorias", "top_clientes", "top_repuestos", "anios"):
            self.assertIn(f"T.conclusiones.{f}", self.pinta)

    def test_filtro_con_botones_reales(self):
        self.assertIn('role="group" aria-labelledby="db-per-lab" id="db-per"', self.vista)
        for v, txt in (("12m", "Últimos 12 meses"), ("todo", "Todo el período")):
            self.assertIn(f'<button class="chip" type="button" data-v="{v}"', self.vista)
            self.assertIn(f">{txt}</button>", self.vista)
        self.assertIn('setAttribute("aria-pressed"', self.pinta)

    def test_graficos_accesibles(self):
        for f in ("function dbDona", "function dbColumnas", "function dbBarras"):
            i = self.codigo.index(f)
            cuerpo = self.codigo[i:self.codigo.index("\n}\n", i)]
            self.assertIn('role="img" aria-label="${esc(aria)}"', cuerpo, f)
        self.assertGreaterEqual(self.pinta.count("info("), 10)   # un ícono «i» por tarjeta y por gráfico

    def test_estructura_de_la_pantalla(self):
        for id_ in ("db-kpis", "chart-db", "chart-db-tipos", "chart-db-alm", "chart-db-cat", "chart-db-cli5", "chart-db-rep", "chart-db-anio"):
            self.assertIn(f'id="{id_}"', self.vista)
        self.assertIn('<a href="#alertas">Ver qué pedir →</a>', self.vista)
        # Las tablas de antes siguen, plegadas en «Ver detalle».
        det = self.vista[self.vista.index('<details class="card db-det"'):]
        for id_ in ("t-db-mes", "t-db-anio", "t-db-rep", "t-db-cli"):
            self.assertIn(f'id="{id_}"', det)
        # Semáforo solo en el almacén: los colores rojo y amarillo no se usan en otro gráfico.
        self.assertEqual(self.pinta.count("DB_ALM_COLOR"), 1)


if __name__ == "__main__":
    unittest.main()
