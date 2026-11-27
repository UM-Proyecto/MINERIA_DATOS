"""Revisión visual del 24-11-2026: «Marcar venta» descuenta stock, así que antes de enviarla se muestra un diálogo
con el repuesto, la cantidad y el stock antes y después. La prueba en el navegador está en la evidencia del PR."""
import re
import unittest
from pathlib import Path

PLANTILLA = Path(__file__).resolve().parents[1] / "src" / "simulador" / "plantilla_app.html"


class ConfirmarVenta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = PLANTILLA.read_text(encoding="utf-8")

    def test_dialogo_con_repuesto_cantidad_y_stock(self):
        self.assertIn('<dialog id="vt-dlg"', self.p)
        # El diálogo lo pinta pintarDialogoVenta, que el clic en la tabla llama al abrirlo.
        i = self.p.index("function pintarDialogoVenta(f, antes)")
        bloque = self.p[i:self.p.index('$("vt-cancelar")', i)]
        self.assertIn('$("t-cz").addEventListener("click"', bloque)
        for pieza in ("f.cantidad", "nombreRep(f.repuesto_id)", "antes", "despues", 'showModal()'):
            self.assertIn(pieza, bloque)
        # El clic en la tabla solo abre el diálogo: la venta sale del botón del diálogo.
        self.assertNotIn("marcarVenta(", bloque)

    def test_stock_viejo_pasa_a_forzar(self):
        # 27-11-2026: si la lista tenía un stock viejo, el servidor responde 409 con el stock real. Antes el botón seguía
        # enviando sin «forzar» y repetía el mismo rechazo. Ahora el error conserva los datos del servidor y el diálogo
        # se vuelve a pintar con ese stock, lo que pone forzar y cambia el texto del botón.
        self.assertIn("e.status = r.status; e.datos = d; throw e;", self.p)
        i = self.p.index('$("vt-ok").addEventListener("click"')
        bloque = self.p[i:self.p.index('$("cz-csv")', i)]
        for pieza in ("err.status === 409", "typeof d.stock === \"number\"", "pintarDialogoVenta(VT.f, d.stock)", "STOCK_REAL[VT.f.repuesto_id] = d.stock"):
            self.assertIn(pieza, bloque)
        j = self.p.index("function pintarDialogoVenta(f, antes)")
        self.assertIn("VT.forzar = falta;", self.p[j:self.p.index("$(\"t-cz\")", j)])

    def test_sin_confirm_nativo(self):
        # Control positivo: el patrón encuentra la forma anterior.
        rx = re.compile(r"\bconfirm\(")
        self.assertTrue(rx.search('!confirm(err.message)'))
        self.assertIsNone(rx.search(self.p))
