"""Decisión D9: tabla ILUSTRATIVA repuesto ↔ vehículo y filtro del catálogo por marca, modelo y año.

Comprueba la tabla (data/processed/scrum-74/aplicaciones.csv), que sale igual del script, que llega a la tienda y al
área de la empresa, y el filtro encadenado de src/portal/filtro_vehiculo.js. Cada comprobación de la tabla tiene su
control negativo: la misma validación sobre una copia estropeada a propósito tiene que fallar.
"""
import copy
import csv
import importlib.util
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("armar_aplicaciones", RAIZ / "src/scrum-74/armar_aplicaciones.py")
aa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aa)
TIENDA = RAIZ / "reports/tienda/MULTIPARTES_Tienda.html"
APP = RAIZ / "reports/simulador/MULTIPARTES_Simulador_Compras.html"


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class Tabla(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.filas = leer(aa.SALIDA)
        cls.catalogo = leer(aa.CATALOGO)
        cls.ids = {c["repuesto_id"] for c in cls.catalogo}
        cls.marcas = json.loads(aa.CONTENIDO.read_text(encoding="utf-8"))["marcas_vehiculos"]
        cls.nombre = {c["repuesto_id"]: c["nombre"] for c in cls.catalogo}

    def test_columnas(self):
        self.assertEqual(tuple(self.filas[0].keys()), aa.CAMPOS)

    def test_validacion_pasa_y_cada_repuesto_tiene_aplicacion(self):
        self.assertEqual(len(self.ids), 30)
        self.assertEqual(aa.validar(self.filas, self.marcas, self.ids), [])
        self.assertEqual({r["repuesto_id"] for r in self.filas}, self.ids)

    def test_control_negativo_de_la_validacion(self):
        # Cada estropeo tiene que aparecer en la lista de problemas; si no, la validación no prueba nada.
        casos = {
            "sin aplicación": lambda f: [r for r in f if r["repuesto_id"] != "REP-0007"],
            "fuera de 1990": lambda f: [dict(f[0], anio_desde="1985")] + f[1:],
            "invertidos": lambda f: [dict(f[0], anio_desde="2015", anio_hasta="2010")] + f[1:],
            "fuera de 1990-2026": lambda f: [dict(f[0], anio_hasta="2031")] + f[1:],
            "fuera de marcas_vehiculos": lambda f: [dict(f[0], marca="FORD")] + f[1:],
            "debe ser ILUSTRATIVO": lambda f: [dict(f[0], procedencia="REAL")] + f[1:],
            "no numéricos": lambda f: [dict(f[0], anio_desde="")] + f[1:],
        }
        for esperado, estropear in casos.items():
            with self.subTest(esperado):
                problemas = aa.validar(estropear(copy.deepcopy(self.filas)), self.marcas, self.ids)
                self.assertTrue(any(esperado in p for p in problemas), problemas)

    def test_marcas_dentro_de_marcas_vehiculos(self):
        usadas = {r["marca"] for r in self.filas}
        self.assertLessEqual(usadas, set(self.marcas))
        self.assertGreaterEqual(len(usadas), 8)  # el parque cubre casi todas las marcas del sitio

    def test_procedencia_ilustrativa(self):
        self.assertEqual({r["procedencia"] for r in self.filas}, {"ILUSTRATIVO"})

    def test_se_genera_igual_con_la_semilla(self):
        a = aa.armar(self.catalogo, self.marcas)
        b = aa.armar(self.catalogo, self.marcas)
        self.assertEqual(a, b)
        en_disco = [{k: (int(v) if k.startswith("anio") else v) for k, v in r.items()} for r in self.filas]
        self.assertEqual(a, en_disco)

    def test_muchos_a_muchos(self):
        por_rep = {}
        for r in self.filas:
            por_rep.setdefault(r["repuesto_id"], set()).add((r["marca"], r["modelo"]))
        self.assertTrue(all(len(v) >= 2 for v in por_rep.values()))
        hilux = {r["repuesto_id"] for r in self.filas if r["modelo"] == "Hilux"}
        self.assertGreater(len(hilux), 1)

    def test_coherente_con_el_nombre(self):
        for r in self.filas:
            n = self.nombre[r["repuesto_id"]].lower()
            with self.subTest(r["repuesto_id"], motor=r["motor"]):
                if "diésel 2.5" in n:
                    self.assertEqual(r["motor"], "2.5 diésel")
                elif "motor 1.6" in n:
                    self.assertEqual(r["motor"], "1.6 gasolina")
                elif "motor 1.4" in n:
                    self.assertEqual(r["motor"], "1.4 gasolina")
                elif "motor 2.0" in n:
                    self.assertEqual(r["motor"], "2.0 gasolina")
                elif "motor diésel" in n:
                    self.assertTrue(r["motor"].endswith("diésel"))
                if n.startswith("bujía") or "a gasolina" in n:
                    self.assertTrue(r["motor"].endswith("gasolina"))
                if "para camioneta" in n:
                    self.assertIn(r["modelo"], {"Hilux", "Frontier", "BT-50", "L200", "D-Max"})

    def test_control_negativo_de_las_reglas(self):
        with self.assertRaises(SystemExit):
            aa.armar([{"repuesto_id": "REP-9999", "nombre": "Radiador de aluminio"}], self.marcas)
        with self.assertRaises(SystemExit):
            aa.armar(self.catalogo, [m for m in self.marcas if m != "TOYOTA"])


class LlegaALasPantallas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.csv = [[r["repuesto_id"], r["marca"], r["modelo"], int(r["anio_desde"]), int(r["anio_hasta"]), r["motor"]]
                   for r in leer(aa.SALIDA)]

    def test_datos_app(self):
        d = json.loads((RAIZ / "data/processed/simulador/datos_app.json").read_text(encoding="utf-8"))
        ap = d["catalogo"]["aplicaciones"]
        self.assertEqual(ap["procedencia"], "ILUSTRATIVO")
        self.assertEqual(ap["filas"], self.csv)

    def test_tienda_y_empresa(self):
        t = json.loads(re.search(r'<script type="application/json" id="datos">(.*?)</script>', TIENDA.read_text(encoding="utf-8"), re.S).group(1))
        self.assertEqual(t["aplicaciones"]["filas"], self.csv)
        for ruta, ids in ((TIENDA, ("ca-ma", "ca-mo", "ca-an", "ca-limpiar")), (APP, ("catv-ma", "catv-mo", "catv-an", "catv-limpiar"))):
            html = ruta.read_text(encoding="utf-8")
            self.assertIn("var FiltroVehiculo", html)
            self.assertIn("Compatibilidades de demostración (prototipo académico)", html)
            for i in ids:
                self.assertIn(f'id="{i}"', html, ruta.name)


JS = r"""
const F = require(process.argv[1] + "/src/portal/filtro_vehiculo.js");
const d = require(process.argv[1] + "/data/processed/simulador/datos_app.json");
const A = d.catalogo.aplicaciones.filas, I = F.indice(A), ids = d.catalogo.repuestos.map(c => c.repuesto_id);
const cuenta = sel => ids.filter(id => F.coincide(I[id], sel)).length;
process.stdout.write(JSON.stringify({
  marcas: F.marcas(A), modelosToyota: F.modelos(A, "TOYOTA"), modelosSin: F.modelos(A, ""),
  aniosHilux: F.anios(A, "TOYOTA", "Hilux"), aniosSinModelo: F.anios(A, "TOYOTA", ""),
  todos: cuenta({}), toyota: cuenta({marca: "TOYOTA"}), hilux: cuenta({marca: "TOYOTA", modelo: "Hilux"}),
  hilux2010: cuenta({marca: "TOYOTA", modelo: "Hilux", anio: "2010"}), hilux2018: cuenta({marca: "TOYOTA", modelo: "Hilux", anio: "2018"}),
  hilux2000: cuenta({marca: "TOYOTA", modelo: "Hilux", anio: "2000"}),
  ids2010: ids.filter(id => F.coincide(I[id], {marca: "TOYOTA", modelo: "Hilux", anio: "2010"})),
  ids2018: ids.filter(id => F.coincide(I[id], {marca: "TOYOTA", modelo: "Hilux", anio: "2018"})),
  modeloDeOtraMarca: cuenta({marca: "TOYOTA", modelo: "Frontier"}),
  cargadoSinFiltro: F.coincide(undefined, {}), cargadoConFiltro: F.coincide(undefined, {marca: "TOYOTA"}),
  resumenVacio: F.resumen([]), resumen13: F.resumen(I["REP-0013"], 2), resumen13Todo: F.resumen(I["REP-0013"], 99),
}));
"""


@unittest.skipUnless(shutil.which("node"), "hace falta Node")
class FiltroEncadenado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", "-e", JS, str(RAIZ)], capture_output=True, text=True, check=True)
        cls.r = json.loads(r.stdout)

    def test_modelo_depende_de_la_marca(self):
        self.assertEqual(self.r["modelosSin"], [])
        self.assertIn("Hilux", self.r["modelosToyota"])
        self.assertNotIn("Frontier", self.r["modelosToyota"])

    def test_anio_depende_del_modelo(self):
        self.assertEqual(self.r["aniosSinModelo"], [])
        # dos generaciones de la Hilux (2005-2015 y 2016-2023): los años se unen, del más nuevo al más viejo
        self.assertEqual(self.r["aniosHilux"], list(range(2023, 2004, -1)))

    def test_cada_paso_acota(self):
        r = self.r
        self.assertEqual(r["todos"], 30)
        self.assertTrue(30 > r["toyota"] >= r["hilux"] >= r["hilux2010"] > 0, r)
        # el año separa las generaciones: la Hilux 2018 (2.4 diésel) no lleva lo que es solo de la 2005-2015
        self.assertTrue(r["hilux"] > r["hilux2018"] > 0, r)
        self.assertNotEqual(set(r["ids2010"]), set(r["ids2018"]))
        self.assertIn("REP-0004", r["ids2018"])   # filtro de aceite diésel: sirve a todos los diésel
        # control negativo: un año fuera de toda generación y un modelo de otra marca no devuelven nada
        self.assertEqual(r["hilux2000"], 0)
        self.assertEqual(r["modeloDeOtraMarca"], 0)

    def test_repuestos_cargados_sin_aplicaciones(self):
        self.assertTrue(self.r["cargadoSinFiltro"])
        self.assertFalse(self.r["cargadoConFiltro"])
        self.assertEqual(self.r["resumenVacio"], "Compatibilidad no registrada")

    def test_resumen_corto(self):
        # REP-0013 tiene la Hilux con tres motores y dos generaciones: se cuenta una vez, con el rango completo.
        self.assertRegex(self.r["resumen13"], r"^Toyota Hilux 2005–2023, \w.* y \d+ más$")
        self.assertEqual(self.r["resumen13Todo"].count("Hilux"), 1)


if __name__ == "__main__":
    unittest.main()
