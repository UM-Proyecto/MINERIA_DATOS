"""Guía de estudio del portal: ninguna cifra escrita a mano.

La guía versionada (docs/GUIA_ESTUDIO_PORTAL.md) tiene que ser idéntica a la que genera src/guia/generar_guia.py con el
motor y los datos actuales. Si alguien cambia un número a mano, o los datos cambian y no se regenera, falla.
"""
import re
import shutil
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src/guia"))
import generar_guia as gg  # noqa: E402


@unittest.skipUnless(shutil.which("node"), "hace falta Node para correr el motor")
class Guia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = gg.hechos()
        cls.generada = gg.armar(cls.h)
        cls.versionada = gg.SALIDA.read_text(encoding="utf-8")

    def test_versionada_igual_a_la_generada(self):
        self.assertEqual(self.versionada, self.generada,
                         "La guía no coincide con los datos: corra python3 src/guia/generar_guia.py")

    def test_un_numero_cambiado_a_mano_se_detecta(self):
        # Control negativo: se altera una cifra en una copia (el AUC del modelo) y la comparación tiene que fallar.
        auc = self.h["pr_auc"]
        self.assertIn(auc, self.versionada)
        alterada = self.versionada.replace("AUC " + auc, "AUC 0,91", 1)
        self.assertNotEqual(alterada, self.versionada)
        self.assertNotEqual(alterada, self.generada)

    def test_cifras_clave_coinciden_con_el_portal(self):
        # Las mismas que muestran las pantallas (medidas en el sitio publicado el 16 y 17-11-2026).
        self.assertEqual(self.h["n_repuestos"], "30")
        self.assertEqual(self.h["n_series_carparts"], "2.674")
        self.assertEqual(self.h["pr_p"], self.h["pr_p_calc"])        # la probabilidad recalculada a mano = la del modelo
        self.assertEqual((self.h["rt_A"], self.h["pr_auc"], self.h["pr_youden"]), ("13", "0,68", "26 %"))

    def test_plantilla_sin_marcas_desconocidas_ni_restos(self):
        with self.assertRaises(SystemExit):
            gg.armar(self.h, "Cifra inventada: {{no_existe}}")
        self.assertNotRegex(self.generada, r"\{\{|\}\}")
        self.assertEqual(re.findall(r"\bundefined\b|\bNaN\b", self.generada), [])

    def test_cubre_cada_pantalla_y_las_preguntas(self):
        for t in ("Tienda", "Entrada", "Tablero de ventas", "Predicción de ventas", "Alertas de reposición", "Simulador de compra",
                  "Comparar proveedores", "Plan de compra con presupuesto", "Importancia y rotación", "Temporadas de venta",
                  "Clientes que más compran", "Catálogo", "Cotizar por cantidad", "Cotizaciones guardadas",
                  "Registrar repuestos y clientes", "Vista del proveedor", "Cotización por correo"):
            self.assertRegex(self.generada, r"### 4\.\d+ " + re.escape(t), t)
        preguntas = re.findall(r"^\d+\. \*\*¿", self.generada, re.M)
        self.assertGreaterEqual(len(preguntas), 25)
        self.assertIn("https://robjhyndman.com/expsmooth/", self.generada)


if __name__ == "__main__":
    unittest.main()
