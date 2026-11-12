import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "scrum-55"
sys.path.insert(0, str(SRC))
import adaptar_carparts as ac

ARCHIVOS_CSV = ["repuestos.csv", "ventas_mensuales.csv", "proveedores.csv", "compras_historicas.csv",
                "resumen_clasificacion.csv", "clasificacion_2674.csv"]
ARCHIVOS = ARCHIVOS_CSV + ["fuente.json"]


def leer(ruta):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def huellas(carpeta):
    return {nombre: hashlib.sha256((Path(carpeta) / nombre).read_bytes()).hexdigest() for nombre in ARCHIVOS}


def filas_sin_marca(filas):
    return [i for i, fila in enumerate(filas) if fila.get("marca") != ac.MARCA]


def compras_con_tc_incorrecto(compras, tco):
    """Índices de las compras cuyo tipo de cambio o costo en Bs no corresponde a su fecha."""
    malas = []
    for i, c in enumerate(compras):
        fecha = date.fromisoformat(c["fecha_orden"])
        esperado = tco[fecha] if fecha >= ac.INICIO_TCO else ac.TC_FIJO
        bs = (Decimal(c["costo_total_usd"]) * esperado).quantize(Decimal("0.01"))
        if Decimal(c["tc_bs_por_usd"]) != esperado or Decimal(c["costo_total_bs"]) != bs:
            malas.append(i)
    return malas


class Scrum55Test(unittest.TestCase):
    """Se genera la salida una vez en una carpeta temporal y se revisa contra los criterios."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.salida = Path(cls._tmp.name) / "a"
        ac.ejecutar(salida=cls.salida)
        cls.repuestos = leer(cls.salida / "repuestos.csv")
        cls.ventas = leer(cls.salida / "ventas_mensuales.csv")
        cls.compras = leer(cls.salida / "compras_historicas.csv")
        cls.proveedores = leer(cls.salida / "proveedores.csv")
        cls.resumen = leer(cls.salida / "resumen_clasificacion.csv")
        cls.detalle = leer(cls.salida / "clasificacion_2674.csv")
        cls.fuente = json.loads((cls.salida / "fuente.json").read_text(encoding="utf-8"))
        cls.tco, _ = ac.leer_tco()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # Criterio 1: carparts citado, con licencia y fecha de descarga.
    def test_criterio1_fuente_carparts(self):
        self.assertEqual(self.fuente["conjunto"], "carparts")
        self.assertIn("Hyndman", self.fuente["cita"])
        self.assertIn("GPL", self.fuente["licencia"])
        self.assertRegex(self.fuente["fecha_descarga"], r"^\d{4}-\d{2}-\d{2}$")
        zip_local = RAIZ / self.fuente["archivo_local"]
        self.assertEqual(hashlib.sha256(zip_local.read_bytes()).hexdigest(), self.fuente["sha256_zip"])
        self.assertEqual(self.fuente["series"], 2674)
        self.assertEqual(len(self.detalle), 2674)
        self.assertEqual(len({f["codigo_carparts"] for f in self.detalle}), 2674)

    # Criterio 2: 30 repuestos con 24 meses o más, clasificados por tipo de demanda y ABC.
    def test_criterio2_treinta_repuestos_con_24_meses(self):
        self.assertEqual(len(self.repuestos), 30)
        self.assertEqual([r["repuesto_id"] for r in self.repuestos], ["REP-%04d" % i for i in range(1, 31)])
        meses = {}
        for v in self.ventas:
            meses.setdefault(v["repuesto_id"], set()).add(v["mes"])
        self.assertEqual(set(meses), {r["repuesto_id"] for r in self.repuestos})
        for rid, conjunto in meses.items():
            self.assertGreaterEqual(len(conjunto), 24, rid)
        self.assertEqual(min(v["mes"] for v in self.ventas), "2022-08")
        self.assertEqual(max(v["mes"] for v in self.ventas), "2026-10")

    def test_criterio2_clasificacion(self):
        sbc = {"suave", "errática", "intermitente", "irregular"}
        for r in self.repuestos:
            self.assertIn(r["tipo_demanda"], sbc)
            self.assertIn(r["clase_abc"], {"A", "B", "C"})
            self.assertTrue(r["adi"] and r["cv2"])
        self.assertEqual({r["clase_abc"] for r in self.repuestos}, {"A", "B", "C"})
        universo = [f for f in self.resumen if f["grupo"] == "universo_2674"]
        self.assertEqual(sum(int(f["series"]) for f in universo), 2674)
        elegidos = [f for f in self.resumen if f["grupo"] == "elegidos_30"]
        self.assertEqual(sum(int(f["series"]) for f in elegidos), 30)

    def test_clasificador_distingue_las_cuatro_clases(self):
        # Series de juguete, una por cuadrante de Syntetos-Boylan.
        self.assertEqual(ac.clasificar_demanda([5, 5, 6, 5, 5, 6])[0], "suave")
        self.assertEqual(ac.clasificar_demanda([1, 9, 1, 12, 1, 10])[0], "errática")
        self.assertEqual(ac.clasificar_demanda([0, 2, 0, 0, 2, 0, 3])[0], "intermitente")
        self.assertEqual(ac.clasificar_demanda([0, 1, 0, 0, 12, 0, 1])[0], "irregular")
        self.assertEqual(ac.clasificar_demanda([0, 0, 3, None])[0], "sin clasificar")

    # Criterio 3: capa simulada y marca en todos los archivos.
    def test_criterio3_capa_simulada(self):
        origenes = {p["origen"] for p in self.proveedores}
        self.assertEqual(origenes, {"Brasil", "China", "EE. UU."})
        for origen in origenes:
            self.assertTrue(3 <= sum(1 for p in self.proveedores if p["origen"] == origen) <= 5)
        for p in self.proveedores:
            self.assertIn(p["incoterm"], {"EXW", "FOB", "CIF"})
        for r in self.repuestos:
            for campo in ("proveedor_id", "origen", "plazo_normal_dias", "costo_unitario_usd", "stock_al_2026_11_10"):
                self.assertNotEqual(r[campo], "", campo)

    def test_criterio3_marca_en_todas_las_filas(self):
        for nombre in ARCHIVOS_CSV:
            filas = leer(self.salida / nombre)
            self.assertTrue(filas, nombre)
            self.assertEqual(filas_sin_marca(filas), [], nombre)
        self.assertEqual(self.fuente["marca"], ac.MARCA)

    def test_control_negativo_marca(self):
        copia = copy.deepcopy(self.repuestos)
        copia[7]["marca"] = ""
        self.assertEqual(filas_sin_marca(copia), [7])
        del copia[3]["marca"]
        self.assertEqual(filas_sin_marca(copia), [3, 7])

    # Criterio 4: montos en USD y Bs con el tipo de cambio oficial.
    def test_criterio4_columnas_usd_y_bs(self):
        for campo in ("costo_unitario_usd", "costo_unitario_bs", "precio_venta_bs", "precio_venta_usd",
                      "valor_stock_usd", "valor_stock_bs"):
            self.assertIn(campo, self.repuestos[0])
        for campo in ("costo_total_usd", "costo_total_bs", "tc_bs_por_usd", "tc_tipo", "tc_fuente"):
            self.assertIn(campo, self.compras[0])

    def test_criterio4_tipo_de_cambio_por_fecha(self):
        posteriores = [c for c in self.compras if c["fecha_orden"] >= ac.INICIO_TCO.isoformat()]
        anteriores = [c for c in self.compras if c["fecha_orden"] < ac.INICIO_TCO.isoformat()]
        self.assertTrue(posteriores and anteriores)
        self.assertEqual(compras_con_tc_incorrecto(self.compras, self.tco), [])
        for c in posteriores:
            self.assertEqual(Decimal(c["tc_bs_por_usd"]), self.tco[date.fromisoformat(c["fecha_orden"])])
            self.assertEqual(c["tc_tipo"], "TCO_BCB_DIARIO")
        for c in anteriores:
            self.assertEqual(Decimal(c["tc_bs_por_usd"]), Decimal("6.96"))
            self.assertEqual(c["tc_tipo"], "OFICIAL_FIJO_BCB")

    def test_control_negativo_tipo_de_cambio(self):
        copia = copy.deepcopy(self.compras)
        i = next(i for i, c in enumerate(copia) if c["fecha_orden"] >= ac.INICIO_TCO.isoformat())
        copia[i]["tc_bs_por_usd"] = "6.96"
        self.assertEqual(compras_con_tc_incorrecto(copia, self.tco), [i])

    # Reproducibilidad.
    def test_determinismo(self):
        otra = Path(self._tmp.name) / "b"
        ac.ejecutar(salida=otra)
        self.assertEqual(huellas(self.salida), huellas(otra))

    def test_otra_semilla_cambia_solo_la_capa_simulada(self):
        otra = Path(self._tmp.name) / "c"
        ac.ejecutar(semilla=7, salida=otra)
        self.assertNotEqual(huellas(self.salida)["repuestos.csv"], huellas(otra)["repuestos.csv"])
        self.assertEqual(huellas(self.salida)["ventas_mensuales.csv"], huellas(otra)["ventas_mensuales.csv"])

    def test_salida_del_repositorio_esta_al_dia(self):
        self.assertEqual(huellas(RAIZ / "data" / "processed" / "scrum-55"), huellas(self.salida))

    def test_corre_desde_otra_carpeta(self):
        destino = Path(self._tmp.name) / "d"
        resultado = subprocess.run([sys.executable, str(SRC / "adaptar_carparts.py"), "--salida", str(destino)],
                                   cwd=self._tmp.name, capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(huellas(destino), huellas(self.salida))


if __name__ == "__main__":
    unittest.main()
