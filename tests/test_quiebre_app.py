"""El dólar de quiebre que muestra la app tiene que coincidir con la recomendación que muestra la misma pantalla.

Hasta el 24-11-2026 la app calculaba la recomendación con 1.500 futuros y el quiebre con 400 (el valor por defecto del
motor). En los 30 repuestos, el quiebre salía entre 0,15 y 0,25 Bs más alto, y con el dólar entre los dos valores la
pantalla recomendaba otra alternativa mientras la tarjeta decía que el quiebre todavía no se había alcanzado.

La prueba lee de la plantilla qué opciones se le pasan a Motor.simular y a Motor.quiebreDolar, las evalúa con los
parámetros reales de datos_app.json y comprueba, para cada repuesto, que con las opciones de la recomendación gana
«antes» justo debajo del quiebre (valor − 0,05) y «después» en el quiebre.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = RAIZ / "src" / "simulador" / "plantilla_app.html"
MOTOR = RAIZ / "src" / "simulador" / "motor.js"
DATOS = RAIZ / "data" / "processed" / "simulador" / "datos_app.json"
HECHOS = RAIZ / "src" / "guia" / "hechos.js"

JS = r"""
const M = require(process.argv[1]); const D = JSON.parse(require("fs").readFileSync(process.argv[2]));
const PAR = D.parametros; const OPC_SIM = %s, OPC_Q = %s;
const tc = D.tc.oficial.valor, sup = {tc_base: tc, tc_90: tc, venta_pct: 0, atraso_dias: 0, precio_sigue_dolar: true};
const en = (id, v) => M.simular(D, id, null, Object.assign({}, sup, {tc_90: v}), OPC_SIM).mejor;
process.stdout.write(JSON.stringify(D.repuestos.map(r => {
  const q = M.quiebreDolar(D, r.repuesto_id, null, sup, OPC_Q);
  return q ? {id: r.repuesto_id, q, bajo: en(r.repuesto_id, Math.round(q.valor * 100 - 5) / 100), alto: en(r.repuesto_id, q.valor)} : {id: r.repuesto_id, q: null};
})));
"""


def opciones(p, llamada):
    """Expresión de opciones que la plantilla le pasa a Motor.<llamada>(D, S.rep, S.prov, s, X)."""
    nombre = re.search(r"Motor\." + llamada + r"\(D, S\.rep, S\.prov, s, (\w+)\)", p).group(1)
    return re.search(r"const " + nombre + r" = (\{[^;]*\});", p).group(1)


@unittest.skipUnless(shutil.which("node"), "hace falta Node")
class QuiebreCoherenteConLaRecomendacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = PLANTILLA.read_text(encoding="utf-8")
        cls.o_sim, cls.o_q, cls.o_sens = opciones(p, "simular"), opciones(p, "quiebreDolar"), opciones(p, "sensibilidad")
        out = subprocess.run(["node", "-e", JS % (cls.o_sim, cls.o_q), str(MOTOR), str(DATOS)],
                             capture_output=True, text=True, check=True).stdout
        cls.res = json.loads(out)

    def test_mismas_opciones(self):
        self.assertEqual(self.o_q, self.o_sim)
        self.assertEqual(self.o_sens, self.o_sim)

    def test_antes_y_despues_del_quiebre_en_los_30(self):
        con_quiebre = [r for r in self.res if r["q"]]
        self.assertEqual(len(self.res), 30)
        self.assertGreater(len(con_quiebre), 0)
        for r in con_quiebre:
            with self.subTest(repuesto=r["id"], quiebre=r["q"]["valor"]):
                self.assertEqual(r["bajo"], r["q"]["antes"])
                self.assertEqual(r["alto"], r["q"]["despues"])

    def test_la_guia_usa_los_mismos_futuros(self):
        h = HECHOS.read_text(encoding="utf-8")
        for f in ("quiebreDolar", "sensibilidad"):
            self.assertRegex(h, r"M\." + f + r"\([^)]*\{n: d\.parametros\.simulaciones,")
