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
        i = self.p.index('$("t-cz").addEventListener("click", e => { const b = e.target.closest("button[data-venta]")')
        bloque = self.p[i:self.p.index('$("vt-cancelar")', i)]
        for pieza in ("f.cantidad", "nombreRep(f.repuesto_id)", "antes", "despues", 'showModal()'):
            self.assertIn(pieza, bloque)
        # El clic en la tabla solo abre el diálogo: la venta sale del botón del diálogo.
        self.assertNotIn("marcarVenta(", bloque)

    def test_sin_confirm_nativo(self):
        # Control positivo: el patrón encuentra la forma anterior.
        rx = re.compile(r"\bconfirm\(")
        self.assertTrue(rx.search('!confirm(err.message)'))
        self.assertIsNone(rx.search(self.p))
