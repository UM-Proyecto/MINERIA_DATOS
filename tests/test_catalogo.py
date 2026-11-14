"""SCRUM-74: catálogo con nombre, categoría, descripción e imagen de cada repuesto."""
import csv
import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("armar_catalogo", RAIZ / "src/scrum-74/armar_catalogo.py")
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)
IMG = RAIZ / "data/raw/scrum-74/imagenes"
HTML = RAIZ / "reports/simulador/MULTIPARTES_Simulador_Compras.html"
LIBRES = re.compile(r"^(CC0|Public domain|CC BY(-SA)? \d\.\d)$")


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class Catalogo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = leer(RAIZ / "data/processed/scrum-55/repuestos.csv")
        cls.fuentes = leer(ac.FUENTES)
        cls.cat = leer(ac.SALIDA)

    def test_los_30_con_nombre_categoria_descripcion_e_imagen(self):
        self.assertEqual(sorted(c["repuesto_id"] for c in self.cat), sorted(r["repuesto_id"] for r in self.rep))
        for c in self.cat:
            for k in ("nombre", "categoria", "descripcion", "imagen"):
                self.assertTrue(c[k].strip(), (c["repuesto_id"], k))
            self.assertEqual(c["marca"], "ILUSTRATIVO")
        self.assertEqual(len({c["nombre"] for c in self.cat}), 30)

    def test_versionado_igual_a_la_regla(self):
        self.assertEqual(ac.armar(self.rep, self.fuentes), self.cat)

    def test_categorias_siguen_el_costo(self):
        costo = {r["repuesto_id"]: float(r["costo_unitario_usd"]) for r in self.rep}
        orden = [c[0] for c in ac.CATEGORIAS]
        por_cat = {k: [costo[c["repuesto_id"]] for c in self.cat if c["categoria"] == k] for k in orden}
        for a, b in zip(orden, orden[1:]):
            self.assertLessEqual(max(por_cat[a]), min(por_cat[b]), (a, b))

    def test_cada_imagen_tiene_licencia_libre_y_autor(self):
        usadas = {c["imagen"] for c in self.cat}
        fuentes = {f["archivo"]: f for f in self.fuentes}
        self.assertEqual(usadas, set(fuentes))
        for nombre, f in fuentes.items():
            self.assertRegex(f["licencia"], LIBRES, nombre)
            self.assertTrue(f["autor"].strip() and f["pagina"].startswith("https://"), nombre)
            datos = (IMG / nombre).read_bytes()
            self.assertEqual(hashlib.sha256(datos).hexdigest(), f["sha256"], nombre)
            self.assertLess(len(datos), 60_000, nombre)

    def test_la_app_trae_las_fotos_y_los_creditos(self):
        h = HTML.read_text(encoding="utf-8")
        d = json.loads(re.search(r'<script type="application/json" id="datos">(.*?)</script>', h, re.S).group(1))
        self.assertEqual(set(d["imagenes"]), {c["imagen"] for c in self.cat})
        self.assertTrue(all(v.startswith("data:image/jpeg;base64,") for v in d["imagenes"].values()))
        self.assertEqual(len(d["catalogo"]["fuentes"]), len(self.fuentes))
        self.assertIn('id="v-catalogo"', h)

    def test_falta_una_categoria(self):
        with self.assertRaises(SystemExit):
            ac.armar(self.rep[:-1], self.fuentes)
        with self.assertRaises(SystemExit):
            ac.armar(self.rep, self.fuentes[1:])


if __name__ == "__main__":
    unittest.main()
