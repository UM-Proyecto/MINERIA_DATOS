"""Revisión visual del 24-11-2026: con el botón «Actualizar» (D7), la barra de sesión partía la miga y el nombre en
varios renglones y a 800 px desbordaba la página. Se fija la separación de «(demostración)» y las reglas de la barra;
la medición en el navegador (renglones y desborde a 1366, 1000, 800 y 390 px) está en la evidencia del PR."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLANTILLA = Path(__file__).resolve().parents[1] / "src" / "simulador" / "plantilla_app.html"


class BarraDeSesion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = PLANTILLA.read_text(encoding="utf-8")

    @unittest.skipUnless(shutil.which("node"), "hace falta Node")
    def test_nombre_separa_la_aclaracion(self):
        fn = re.search(r"function nombreSesion\(.*?\n", self.p).group(0)
        esc = 'const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;");\n'
        js = esc + fn + 'console.log(JSON.stringify([nombreSesion("Jefatura de compras (demostración)"), nombreSesion("Proveedor"), nombreSesion("")]))'
        out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out, ['Jefatura de compras<span class="demo"> (demostración)</span>', "Proveedor", ""])

    def test_reglas_de_la_barra(self):
        self.assertIn(".topbar #miga{min-width:0;flex:1 1 auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}", self.p)
        self.assertIn("@media (max-width:1100px){ .sesion .act,.sesion .demo{display:none} }", self.p)
        self.assertIn("<span>${nombreSesion(SES.nombre)}</span>", self.p)
