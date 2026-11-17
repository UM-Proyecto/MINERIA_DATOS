"""SCRUM-71: el dólar oficial del BCB se actualiza solo una vez al día.

Comprueba la tarea programada (.github/workflows/tco-diario.yml), que una lectura fallida del BCB no toque el
último valor guardado y que la app avise cuando el valor tiene más de un día.
"""
import importlib.util
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FLUJO = RAIZ / ".github/workflows/tco-diario.yml"
CSV = RAIZ / "data/processed/scrum-54/tco_bcb_diario.csv"
FIXTURE = RAIZ / "data/raw/scrum-54/tco_bcb_2026-11-10.html"
PLANTILLA = RAIZ / "src/simulador/plantilla_app.html"

spec = importlib.util.spec_from_file_location("obtener_tco_bcb", RAIZ / "src/scrum-54/obtener_tco_bcb.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TareaDiaria(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.y = FLUJO.read_text(encoding="utf-8")

    def test_corre_cada_dia_y_a_mano(self):
        self.assertEqual(len(re.findall(r'^\s+- cron: "\d+ \d+ \* \* \*"', self.y, re.M)), 2)
        self.assertIn("workflow_dispatch:", self.y)

    def test_usa_el_script_de_scrum54(self):
        self.assertIn("python3 src/scrum-54/obtener_tco_bcb.py", self.y)
        self.assertNotIn("--inseguro", self.y)

    def test_si_el_bcb_falla_no_se_corta_ni_se_guarda(self):
        bloque = self.y[self.y.index("id: bcb"):self.y.index("- name: Si el BCB")]
        self.assertIn("continue-on-error: true", bloque)
        guardar = self.y[self.y.index("- name: Guardar"):]
        self.assertIn("steps.cambio.outputs.nuevo == 'si'", guardar)
        self.assertIn("github.event_name != 'pull_request'", guardar)

    def test_prueba_antes_de_guardar(self):
        self.assertLess(self.y.index("unittest discover"), self.y.index("git push"))


class FallaSinPisar(unittest.TestCase):
    def test_lectura_fallida_conserva_el_ultimo_valor(self):
        with tempfile.TemporaryDirectory() as d:
            sal = Path(d) / "tco.csv"
            shutil.copy(CSV, sal)
            antes = sal.read_bytes()
            mal = Path(d) / "tco_bcb_2026-11-10.html"
            mal.write_text("<html>el BCB respondió otra cosa</html>", encoding="utf-8")
            self.assertEqual(m.main(["--desde-archivo", str(mal), "--salida", str(sal)]), 1)
            self.assertEqual(sal.read_bytes(), antes)


class AvisoEnLaApp(unittest.TestCase):
    def test_aviso_de_dato_viejo(self):
        if shutil.which("node") is None:
            self.skipTest("node no está instalado")
        p = PLANTILLA.read_text(encoding="utf-8")
        dias = re.search(r"const diasTc = .*?;\n", p).group(0)
        aviso = re.search(r"const avisoTc = .*?;\n", p).group(0)
        self.assertIn("avisoTc()", p[p.index('$("of-src").innerHTML'):])
        js = ("const MES=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];"
              "const fecha=f=>{const[y,m,d]=f.split('-');return +d+'-'+MES[+m-1]+'-'+y};"
              "const h=new Date();const iso=x=>{const t=new Date(h.getFullYear(),h.getMonth(),h.getDate()-x);"
              "return t.getFullYear()+'-'+String(t.getMonth()+1).padStart(2,'0')+'-'+String(t.getDate()).padStart(2,'0')};"
              "let OF={fecha:iso(0)};" + dias + aviso +
              "const r=[];for(const x of [0,1,3]){OF={fecha:iso(x)};r.push(diasTc()+':'+(avisoTc()?'aviso':'-'))}"
              "process.stdout.write(r.join(' '))")
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
        self.assertEqual(out, "0:- 1:- 3:aviso")


if __name__ == "__main__":
    unittest.main()
