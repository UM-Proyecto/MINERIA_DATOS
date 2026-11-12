import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "obtener_tco_bcb", RAIZ / "src/scrum-54/obtener_tco_bcb.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

FIXTURE = RAIZ / "data/raw/scrum-54/tco_bcb_2026-11-10.html"
CSV_ACTUAL = RAIZ / "data/processed/scrum-54/tco_bcb_diario.csv"


def leer(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class PruebasTCO(unittest.TestCase):
    def test_fixture_reproduce_el_csv_actual(self):
        with tempfile.TemporaryDirectory() as d:
            sal = Path(d) / "tco.csv"
            rc = m.main(["--desde-archivo", str(FIXTURE), "--salida", str(sal)])
            self.assertEqual(rc, 0)
            nuevo, actual = leer(sal), leer(CSV_ACTUAL)
            self.assertEqual(len(nuevo), 137)
            # El CSV del repo puede haberse extendido con capturas posteriores:
            # las primeras 137 filas deben coincidir exactamente.
            self.assertGreaterEqual(len(actual), 137)
            self.assertEqual(nuevo, actual[:137])

    def test_negativo_dia_borrado(self):
        crudo = FIXTURE.read_text(encoding="utf-8")
        alterado = crudo.replace("domingo 28 de junio de 2026", "x", 1)
        self.assertNotEqual(alterado, crudo)
        filas, vig, ult = m.parsear(alterado)
        self.assertEqual(len(filas), 136)
        with self.assertRaisesRegex(m.ErrorTCO, "Faltan días"):
            m.validar(filas, vig, ult)

    def test_negativo_valor_fuera_de_rango(self):
        crudo = FIXTURE.read_text(encoding="utf-8")
        filas, vig, ult = m.parsear(crudo)
        filas[3] = (filas[3][0], 115.0)
        with self.assertRaisesRegex(m.ErrorTCO, "fuera de rango"):
            m.validar(filas, vig, ult)

    def test_negativo_valor_115_en_el_html(self):
        crudo = FIXTURE.read_text(encoding="utf-8")
        i = crudo.index("martes 30 de junio de 2026")
        j = crudo.index("9,76", i)
        alterado = crudo[:j] + "115,0" + crudo[j + 4:]
        filas, vig, ult = m.parsear(alterado)
        with self.assertRaisesRegex(m.ErrorTCO, "fuera de rango"):
            m.validar(filas, vig, ult)

    def test_negativo_vigencia_distinta(self):
        crudo = FIXTURE.read_text(encoding="utf-8")
        alterado = crudo.replace("VIGENCIA: MARTES 10 DE NOVIEMBRE",
                                 "VIGENCIA: MIÉRCOLES 11 DE NOVIEMBRE")
        self.assertNotEqual(alterado, crudo)
        filas, vig, ult = m.parsear(alterado)
        with self.assertRaisesRegex(m.ErrorTCO, "vigencia"):
            m.validar(filas, vig, ult)

    def test_main_corta_y_no_escribe(self):
        with tempfile.TemporaryDirectory() as d:
            mal = Path(d) / "tco_bcb_2026-11-10.html"
            mal.write_text(FIXTURE.read_text(encoding="utf-8").replace(
                "domingo 28 de junio de 2026", "x", 1), encoding="utf-8")
            sal = Path(d) / "tco.csv"
            self.assertEqual(m.main(["--desde-archivo", str(mal), "--salida", str(sal)]), 1)
            self.assertFalse(sal.exists())


if __name__ == "__main__":
    unittest.main()
