"""Tienda pública del portal: mejora del sitio www.multipartes.com.bo (aprobada por Sam el 14-11-2026).

Comprueba que el contenido sale del sitio real (data/raw/tienda/contenido_sitio.json), que lo agregado está
marcado como prototipo, que cada repuesto cae en un rubro del sitio y que la página no lleva datos de la empresa.
"""
import csv
import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generar_tienda", RAIZ / "src/tienda/generar_tienda.py")
gt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gt)


class Tienda(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.html = gt.generar(Path(cls.tmp.name) / "t.html")
        cls.c = json.loads(gt.CONTENIDO.read_text(encoding="utf-8"))
        cls.t = json.loads(re.search(r'<script type="application/json" id="datos">(.*?)</script>', cls.html, re.S).group(1))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_versionado_igual_al_generado(self):
        self.assertEqual(gt.SALIDA.read_text(encoding="utf-8"), self.html)

    def test_dice_que_es_prototipo_y_no_se_indexa(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.html)
        self.assertIn("PROTOTIPO ACADÉMICO", self.html)
        self.assertIn("No es el sitio oficial de MULTIPARTES", self.html)
        self.assertIn('href="https://www.multipartes.com.bo/"', self.html)

    def test_contenido_real_del_sitio(self):
        d = self.t["contenido"]
        self.assertEqual(d, self.c)
        self.assertIn("Avenida Cristo Redentor Nº 282", d["oficina"])
        self.assertEqual(len(d["sucursales"]), 7)
        self.assertEqual(d["horario"], ["Lunes a viernes 07:45 a 18:30", "Sábados 07:45 a 14:00"])
        self.assertEqual(len(d["rubros"]), 9)
        self.assertTrue(d["whatsapp_portada"]["a_revisar"] and d["sucursales_a_revisar"])

    def test_cada_repuesto_en_un_rubro_del_sitio(self):
        rubros = {r[0] for r in self.c["rubros"]}
        for c in self.t["catalogo"]:
            self.assertIn(gt.RUBRO_DE_CATEGORIA[c["categoria"]], rubros, c["repuesto_id"])
        self.assertEqual(len(self.t["catalogo"]), 30)

    def test_imagenes_del_sitio_con_fuente(self):
        fuentes = {f["archivo"]: f for f in csv.DictReader(open(RAIZ / "data/raw/tienda/fuentes_imagenes.csv", encoding="utf-8"))}
        for _, f in self.c["rubros"]:
            self.assertIn(f, fuentes)
            self.assertTrue(fuentes[f]["original"].startswith("https://www.multipartes.com.bo/"))
            self.assertEqual(hashlib.sha256((gt.IMG_SITIO / f).read_bytes()).hexdigest(), fuentes[f]["sha256"])
            self.assertIn(f, self.t["imagenes"])
        self.assertIn("logo_multipartes.jpg", self.t["imagenes"])

    def test_no_lleva_datos_de_la_empresa(self):
        self.assertEqual(set(self.t), {"contenido", "imagenes", "catalogo", "repuestos", "proveedores", "tc", "rubro_de_categoria"})
        self.assertTrue(all(set(r) == set(gt.CAMPOS_REP) for r in self.t["repuestos"]))
        self.assertTrue(all(set(p) == set(gt.CAMPOS_PROV) for p in self.t["proveedores"]))
        self.assertNotIn("CLI-01", json.dumps(self.t, ensure_ascii=False))
        self.assertNotIn("demo-importador", self.html)

    def test_sin_voseo_ni_textos_prohibidos(self):
        texto = re.sub(r"<script.*?</script>", "", self.html, flags=re.S)
        self.assertIsNone(re.search(r"\b(tenés|podés|acá|querés|elegí)\b", texto, re.I))


if __name__ == "__main__":
    unittest.main()
