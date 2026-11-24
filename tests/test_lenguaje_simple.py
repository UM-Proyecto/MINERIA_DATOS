"""Lenguaje simple en el portal de la empresa (decisiones D2 a D5 de Sam, 24-11-2026; auditoría de gráficos).

- D5: las alternativas B y D se ocultan cuando sacan 0 de puntaje y vuelven a aparecer cuando ganan en algún escenario.
- D3: los términos técnicos de la tabla A.4 no aparecen en el texto visible de la plantilla. Lo técnico solo puede ir
  dentro de un «Detalle técnico» plegado (<details class="tecnico">, la función tecnico(...) o una región marcada con
  /* técnico: inicio */ ... /* técnico: fin */ en el código).
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = RAIZ / "src" / "simulador" / "plantilla_app.html"
TIENDA = RAIZ / "src" / "tienda" / "plantilla_tienda.html"
MOTOR = RAIZ / "src" / "simulador" / "motor.js"
DATOS = RAIZ / "data" / "processed" / "simulador" / "datos_app.json"

# Términos de la tabla A.4 tal como se escriben en pantalla. Se buscan con mayúsculas y espacios para no confundirlos
# con nombres del código (p.incoterm, capital_inmovilizado_bs, corte_youden).
TERMINOS = [r"[Cc]osto puesto", r"[Pp]unto de pedido", r"Incoterm", r"\b[Cc]lase (ABC|A|B|C)\b", r"[Dd]ólar de quiebre",
            r"Monte Carlo", r"[Pp]romedio móvil", r"[Pp]unto de equilibrio", r"[Íí]ndice estacional", r"veces el promedio",
            r"[Rr]egresión logística", r"[Cc]lasificación supervisada", r"[Mm]atriz de confusión", r"Desabastecimiento",
            r"Acumulación", r"[Bb]aja rotación", r"(?<!_)inmovilizad[oa]", r"Cobertura", r"escenario desfavorable",
            r"método SBA", r"Croston", r"\bAUC\b", r"\bBrier\b", r"Youden", r"Pareto", r"[Cc]alibración",
            r"[Ss]tock de seguridad", r"\(s, S\)", r"venta (ocasional|irregular)", r"fechas trasladadas",
            r"[Pp]enalización L2", r"[Aa]nálisis de sensibilidad", r"semilla \$"]
RX = re.compile("|".join(f"(?:{t})" for t in TERMINOS))


def visible(html):
    """La plantilla sin lo plegado ni los comentarios: lo que puede llegar a la pantalla fuera del detalle técnico."""
    t = html[html.index("<body>"):] if "<body>" in html else html
    t = re.sub(r"/\* técnico: inicio \*/.*?/\* técnico: fin \*/", "", t, flags=re.S)
    t = re.sub(r'<details class="tecnico[^"]*"[^>]*>.*?</details>', "", t, flags=re.S)
    t = re.sub(r'tecnico\(`.*?`(, "[^"]*")?\)', "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->|/\*.*?\*/", "", t, flags=re.S)
    return re.sub(r"^\s*//.*$|(?<=[;{}])\s*//.*$", "", t, flags=re.M)


class TerminosTecnicos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PLANTILLA.read_text(encoding="utf-8")

    def test_sin_terminos_tecnicos_a_la_vista(self):
        hallados = [(m.group(0), visible(self.html)[max(0, m.start() - 60):m.end() + 20]) for m in RX.finditer(visible(self.html))]
        self.assertEqual(hallados, [])

    def test_control_positivo(self):
        # Sin quitar lo plegado, los términos sí están (en el detalle técnico): el filtro no es un vacío que siempre pasa.
        crudo = {m.group(0) for m in RX.finditer(self.html)}
        for t in ("Incoterm", "AUC", "Monte Carlo", "Pareto", "Clase ABC"):
            self.assertIn(t, crudo)
        # Y un término plantado en texto visible se detecta.
        self.assertTrue(RX.search(visible('<body><p>Columna Costo puesto</p>')))
        self.assertTrue(RX.search(visible('<body><script>x.textContent = "el dólar de quiebre";</script>')))

    def test_detalle_tecnico_con_el_mismo_rotulo(self):
        sums = [s for s in re.findall(r'<details class="tecnico[^"]*"[^>]*><summary>([^<]*)</summary>', self.html) if s != "${t}"]
        self.assertGreaterEqual(len(sums), 8)
        self.assertTrue(all(s.startswith("Detalle técnico") for s in sums), sums)
        self.assertIn('const tecnico = (html, t = "Detalle técnico")', self.html)

    def test_quitados_por_d2(self):
        # #6: el gráfico de compras por cliente salió del tablero y su «Tendencia» está en Clientes.
        self.assertNotIn('id="chart-db-cli"', self.html)
        cli = self.html[self.html.index("function pintarClientes"):self.html.index("$(\"cli-per\").addEventListener")]
        self.assertIn("Tendencia", cli)
        # #39: sin el gráfico de los dos dólares en Minería; los tres indicadores siguen.
        self.assertNotIn('id="chart-tc2"', self.html)
        self.assertIn('id="tc2-kpis"', self.html)

    def test_guia_del_simulador(self):
        # D4: la caja «Cómo leer esta pantalla» con tres pasos, arriba de la tarjeta del dólar.
        self.assertLess(self.html.index('id="guia"'), self.html.index('id="h-tchoy"'))
        for i in (1, 2, 3):
            self.assertIn(f'id="guia-{i}"', self.html)

    def test_tienda_sin_nota_interna_de_logos(self):
        t = TIENDA.read_text(encoding="utf-8")
        self.assertNotIn('id="dist-nota"', t)
        self.assertNotIn("distribuidores_nota", visible(t))
        self.assertIn('class="revisar"', t)   # la insignia «?» de Aisin y Advics se mantiene


@unittest.skipUnless(shutil.which("node"), "hace falta Node")
class OcultarAlternativasEnCero(unittest.TestCase):
    """D5. Se prueba la línea altsVisibles de la plantilla tal cual, con casos armados y con el motor real."""

    @classmethod
    def setUpClass(cls):
        p = PLANTILLA.read_text(encoding="utf-8")
        cls.fn = re.search(r"const altsVisibles = .*?;\n", p).group(0)
        cls.datos = json.loads(DATOS.read_text(encoding="utf-8"))

    def node(self, js):
        r = subprocess.run(["node", "-e", self.fn + js, str(MOTOR), str(DATOS)], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)

    def test_casos_armados(self):
        out = self.node("""
          const R = (a,b,c,d) => ({A:{puntaje:a},B:{puntaje:b},C:{puntaje:c},D:{puntaje:d}});
          process.stdout.write(JSON.stringify([altsVisibles(R(62,0,38,0), false), altsVisibles(R(50,12,38,0), false),
            altsVisibles(R(40,0,30,30), false), altsVisibles(R(0,0,0,0), true), altsVisibles(R(100,0,0,0), false)]));""")
        self.assertEqual(out, [["A", "C"], ["A", "B", "C"], ["A", "C", "D"], ["A", "B", "C", "D"], ["A", "C"]])

    def test_con_el_motor_se_ocultan_y_reaparecen(self):
        # Con los supuestos de base, B y D sacan 0 en REP-0001 (el ejemplo de simulador.md, S3) y en REP-0019: se ocultan.
        # En REP-0019, si se supone que se venderá 30 % más, B gana en algún escenario y vuelve a mostrarse (medido el
        # 24-11-2026 con el dólar oficial de 11,78 Bs). D se sigue ocultando porque sigue en 0.
        out = self.node("""
          const Motor = require(process.argv[1]), D = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
          const tc = D.tc.oficial.valor, P = D.parametros;
          const corre = (id, v) => { const r = D.repuestos.find(x => x.repuesto_id === id);
            const R = Motor.simular(D, id, r.proveedor_id, {tc_base:tc, tc_90:tc, venta_pct:v, atraso_dias:0, precio_sigue_dolar:true},
              {n:P.simulaciones, semilla:P.semilla, horizonte_dias:90});
            return [altsVisibles(R, false), R.B.puntaje, R.D.puntaje]; };
          process.stdout.write(JSON.stringify([corre('REP-0001', 0), corre('REP-0019', 0), corre('REP-0019', 30)]));""")
        (v1, b1, d1), (v19, b19, d19), (v19b, b19b, d19b) = out
        self.assertEqual((b1, d1, v1), (0, 0, ["A", "C"]))
        self.assertEqual((b19, d19, v19), (0, 0, ["A", "C"]))
        self.assertGreater(b19b, 0)
        self.assertEqual(d19b, 0)
        self.assertEqual(v19b, ["A", "B", "C"])

if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "hace falta Node")
class SingularYPlural(unittest.TestCase):
    """Revisión visual del 24-11-2026: el simulador decía «1 unidades». Se prueban nf y pal tal cual están en la
    plantilla, y que ningún contador conocido quede con el plural fijo."""

    @classmethod
    def setUpClass(cls):
        cls.p = PLANTILLA.read_text(encoding="utf-8")
        cls.fn = re.search(r"function pal\(.*?\n", cls.p).group(0) + re.search(r"function nf\(.*?\n}\n", cls.p, re.S).group(0)

    def test_pal(self):
        js = ('console.log(JSON.stringify([pal(1,"unidad","unidades"), pal(2,"unidad","unidades"), pal(0,"unidad","unidades"),'
              ' pal(1,"unidad","unidades",1), pal(0.6,"unidad","unidades"), pal(1.4,"unidad","unidades"), pal(-1,"día","días")]))')
        out = json.loads(subprocess.run(["node", "-e", self.fn + js], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out, ["unidad", "unidades", "unidades", "unidades", "unidad", "unidad", "días"])

    def test_sin_plural_fijo_tras_una_cifra(self):
        # Control positivo: la forma vieja del stock del simulador la detecta este mismo patrón.
        rx = re.compile(r"\$\{nf\([^()]*\)\}(?: |<small>)(?:unidades|días|meses)\b|\$\{(?:stock|pedir|vig|A\.length)\}<small>(?:unidades|repuestos)\b")
        self.assertTrue(rx.search("${nf(stock)}<small>unidades"))
        self.assertEqual(rx.findall(self.p), [])


class PestanasDeMineria(unittest.TestCase):
    """Decisión de Sam del 24-11-2026: cada pestaña de «Minería de datos» se nombra con la pregunta de negocio que
    responde. El nombre de la técnica va en chico debajo del título, no en el botón. MN_TABS está dentro de una región
    técnica (la explicación de cada técnica), así que la prueba general de términos no la ve: esta revisa los botones."""

    @classmethod
    def setUpClass(cls):
        cls.p = PLANTILLA.read_text(encoding="utf-8")
        bloque = cls.p[cls.p.index("const MN_TABS = ["):cls.p.index("/* técnico: fin */", cls.p.index("const MN_TABS = ["))]
        cls.preguntas = re.findall(r'\{k:"\w+", p:"([^"]+)"', bloque)
        cls.tecnicas = re.findall(r'tec:"([^"]+)"', bloque)

    def test_nueve_pestanas_con_pregunta_y_tecnica(self):
        self.assertEqual(len(self.preguntas), 9)
        self.assertEqual(len(self.tecnicas), 9)
        for q in self.preguntas:
            self.assertTrue(q.startswith("¿") and q.endswith("?"), q)

    def test_botones_sin_terminos_tecnicos(self):
        # Control positivo: los nombres de antes del cambio los detecta el mismo patrón.
        for viejo in ("Regresión logística", "Simulación de Monte Carlo", "Punto de pedido (s, S)", "Índice estacional"):
            self.assertTrue(RX.search(viejo), viejo)
        self.assertEqual([q for q in self.preguntas if RX.search(q)], [])

    def test_boton_y_titulo_usan_la_pregunta(self):
        self.assertIn("${esc(t.p)}</button>", self.p)
        self.assertIn('<h2>${esc(tab.p)}</h2><p class="mn-tec">${esc(tab.tec)}</p>', self.p)
        self.assertNotIn("${esc(t.t)}</button>", self.p)
