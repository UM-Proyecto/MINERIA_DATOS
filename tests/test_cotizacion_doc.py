"""SCRUM-83: cotización imprimible y correo de demostración (src/portal/cotizacion_doc.js)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
JS = r"""
const D = require(process.argv[1] + "/src/portal/cotizacion_doc.js");
const M = require(process.argv[1] + "/src/simulador/motor.js");
const d = require(process.argv[1] + "/data/processed/simulador/datos_app.json");
const c = M.cotizar(d, "REP-0019", 12, 11.67);
// Como la devuelve el servidor al guardar
const q = Object.assign({numero: 7, fecha: "2026-11-17T13:43:00Z", tc_fecha: "2026-11-13", correo: "compras@tallerelcruce.com",
  cliente_nombre: "Taller <b>El Cruce</b>", repuesto_id: "REP-0019", repuesto_nombre: "Correa de distribución"}, c);
// Como viene de la tabla de Cotizaciones guardadas (sin precio por unidad ni subtotal: se derivan)
const fila = {numero: 7, fecha: q.fecha, tc: 11.67, tc_fecha: q.tc_fecha, repuesto_id: "REP-0019", cantidad: 12,
  precio_lista_bs: c.precio_lista_bs, pct_aplicado: c.pct_aplicado, total_bs: c.total_bs};
const op = {logo: "data:image/jpeg;base64,AAAA", tramos: M.TRAMOS_EJEMPLO, validez_dias: 7};
process.stdout.write(JSON.stringify({
  c, doc: D.documento(q, op), docFila: D.documento(fila, op), correo: D.correo(q, op), completada: D._completar(fila),
  validos: ["a@b.co", "compras@tallerelcruce.com", " x@y.bo "].map(D.correoValido),
  invalidos: ["", "compras@taller", "a b@c.com", "@c.com", "a@", "a".repeat(120) + "@x.com", null].map(D.correoValido),
}));
"""


@unittest.skipUnless(shutil.which("node"), "hace falta Node")
class CotizacionDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", "-e", JS, str(RAIZ)], capture_output=True, text=True, check=True)
        cls.r = json.loads(r.stdout)

    def test_documento_trae_lo_pedido(self):
        doc = self.r["doc"]
        for t in ("COTIZACIÓN N° 000007", "PROTOTIPO ACADÉMICO", "compras@tallerelcruce.com", "Código REP-0019",
                  "Emitida el 17-nov-2026", "válida hasta el 24-nov-2026", "11,67 Bs por dólar", "13-nov-2026",
                  "10 a 49 unidades", "50 o más unidades", "data:image/jpeg;base64,AAAA", "https://robjhyndman.com/expsmooth/",
                  "datos de demostración", "Imprimir o guardar en PDF", "@page{size:A4"):
            self.assertIn(t, doc, t)
        # el total y el tramo aplicado salen del motor, sin recalcular
        self.assertIn("Bs 6.872,76", doc)
        self.assertIn('<tr class="on"><td>10 a 49 unidades</td><td>5 % de descuento</td></tr>', doc)

    def test_escapa_lo_que_escribe_el_cliente(self):
        self.assertNotIn("<b>El Cruce</b>", self.r["doc"])
        self.assertIn("Taller &lt;b&gt;El Cruce&lt;/b&gt;", self.r["doc"])

    def test_fila_guardada_da_la_misma_cuenta_que_el_motor(self):
        c, f = self.r["c"], self.r["completada"]
        self.assertAlmostEqual(f["subtotal_bs"], c["subtotal_bs"], places=2)
        self.assertAlmostEqual(f["descuento_bs"], c["descuento_bs"], places=2)
        self.assertAlmostEqual(f["precio_unitario_bs"], c["precio_unitario_bs"], places=2)
        self.assertIn("Bs 6.872,76", self.r["docFila"])
        self.assertIn("Cliente de la tienda en línea", self.r["docFila"])  # sin nombre ni correo

    def test_correo_de_demostracion(self):
        m = self.r["correo"]
        self.assertEqual(m["para"], "compras@tallerelcruce.com")
        self.assertEqual(m["asunto"], "Cotización N° 000007 de MULTIPARTES: Correa de distribución")
        self.assertEqual(m["adjunto"], "Cotizacion_MULTIPARTES_000007.pdf")
        for t in ("Cantidad: 12 unidades", "Total: Bs 6.872,76", "5 % de descuento por cantidad", "válida hasta el 24-nov-2026"):
            self.assertIn(t, m["cuerpo"], t)

    def test_validacion_del_correo(self):
        self.assertEqual(self.r["validos"], [True, True, True])
        self.assertEqual(self.r["invalidos"], [False] * 7)


if __name__ == "__main__":
    unittest.main()
