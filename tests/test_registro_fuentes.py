import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "hu-02"
sys.path.insert(0, str(SRC))
from registro_fuentes import actualizar, consultar, leer_csv
CAMPOS_CATALOGO = ["conjunto", "descripcion", "archivo", "fuente", "tipo_dato", "responsable",
                   "columnas_requeridas", "columna_fecha"]


def escribir(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)


class RegistroTest(unittest.TestCase):
    """Cada prueba arma su propia carpeta con dos conjuntos de prueba y su catálogo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.stock = self.raiz / "HU-18" / "stock_inicial.csv"
        escribir(self.stock, [
            {"codigo_unico": "REP-0001", "fecha_corte": "2026-08-31", "stock_inicial": "20"},
            {"codigo_unico": "REP-0002", "fecha_corte": "2026-08-31", "stock_inicial": "5"},
        ])
        escribir(self.raiz / "HU-17" / "catalogo.csv", [
            {"codigo_repuesto": "FIL-001", "descripcion": "Filtro de aceite"},
        ])
        self.catalogo = self.raiz / "conjuntos.csv"
        escribir(self.catalogo, [
            dict(zip(CAMPOS_CATALOGO, ["stock_inicial", "Stock", "HU-18/stock_inicial.csv", "Equipo (HU-18)",
                                       "FICTICIO", "Sabrina", "codigo_unico|fecha_corte|stock_inicial",
                                       "fecha_corte"])),
            dict(zip(CAMPOS_CATALOGO, ["catalogo", "Catálogo", "HU-17/catalogo.csv", "Equipo (HU-17)",
                                       "FICTICIO", "Sabrina", "codigo_repuesto|descripcion", ""])),
        ])
        self.conjuntos = {c["conjunto"]: c for c in leer_csv(self.catalogo)}
        self.registro = self.raiz / "registro.csv"
        self.historial = self.raiz / "historial.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def cargar(self, nombres, fecha):
        return actualizar(nombres, self.raiz, self.conjuntos, self.registro, self.historial, fecha)

    def estado(self, nombre):
        return {f["conjunto"]: f for f in leer_csv(self.registro)}[nombre]

    def test_criterio_1_cada_conjunto_muestra_fuente_y_ultima_actualizacion(self):
        self.cargar(["stock_inicial", "catalogo"], "2026-10-20 10:00 UTC")

        tabla = {nombre: (fuente, vigente, aviso) for nombre, fuente, vigente, aviso in
                 consultar(self.conjuntos, self.registro)}

        self.assertEqual(set(tabla), {"stock_inicial", "catalogo"})
        self.assertEqual(tabla["stock_inicial"],
                         ("Equipo (HU-18) [FICTICIO]", "2026-10-20 10:00 UTC (datos al 2026-08-31)", ""))
        self.assertEqual(tabla["catalogo"], ("Equipo (HU-17) [FICTICIO]", "2026-10-20 10:00 UTC", ""))

    def test_criterio_1_un_conjunto_nunca_cargado_lo_dice(self):
        self.cargar(["catalogo"], "2026-10-20 10:00 UTC")

        tabla = {r[0]: r for r in consultar(self.conjuntos, self.registro)}

        self.assertEqual(tabla["stock_inicial"][2], "SIN CARGA VÁLIDA")

    def test_criterio_2_una_actualizacion_exitosa_cambia_la_fecha(self):
        self.cargar(["stock_inicial"], "2026-10-20 10:00 UTC")
        escribir(self.stock, [
            {"codigo_unico": "REP-0001", "fecha_corte": "2026-09-30", "stock_inicial": "18"},
        ])

        fallos = self.cargar(["stock_inicial"], "2026-10-26 15:30 UTC")

        e = self.estado("stock_inicial")
        self.assertEqual(fallos, [])
        self.assertEqual((e["ultima_actualizacion"], e["fecha_corte_datos"], e["registros"], e["estado_ultima_carga"]),
                         ("2026-10-26 15:30 UTC", "2026-09-30", "1", "OK"))
        self.assertEqual([h["resultado"] for h in leer_csv(self.historial)], ["OK", "OK"])

    def test_criterio_3_si_la_carga_falla_conserva_la_fecha_y_muestra_el_fallo(self):
        self.cargar(["stock_inicial", "catalogo"], "2026-10-20 10:00 UTC")
        antes = self.estado("stock_inicial")
        # fallo provocado: el archivo nuevo llega sin la columna stock_inicial
        escribir(self.stock, [{"codigo_unico": "REP-0001", "fecha_corte": "2026-09-30"}])

        fallos = self.cargar(["stock_inicial", "catalogo"], "2026-10-26 15:30 UTC")

        e = self.estado("stock_inicial")
        self.assertEqual(fallos, [("stock_inicial", "faltan columnas: stock_inicial")])
        self.assertEqual((e["ultima_actualizacion"], e["fecha_corte_datos"], e["registros"], e["sha256"]),
                         (antes["ultima_actualizacion"], antes["fecha_corte_datos"], antes["registros"], antes["sha256"]))
        self.assertEqual((e["estado_ultima_carga"], e["fecha_ultimo_intento"]), ("FALLO", "2026-10-26 15:30 UTC"))
        # el conjunto que sí cargó bien avanza aunque el otro falle
        self.assertEqual(self.estado("catalogo")["ultima_actualizacion"], "2026-10-26 15:30 UTC")
        tabla = {r[0]: r for r in consultar(self.conjuntos, self.registro)}
        self.assertEqual(tabla["stock_inicial"][2], "2026-10-20 10:00 UTC (datos al 2026-08-31)")
        self.assertEqual(tabla["stock_inicial"][3],
                         "FALLÓ la carga del 2026-10-26 15:30 UTC: faltan columnas: stock_inicial")
        self.assertEqual([(h["conjunto"], h["resultado"]) for h in leer_csv(self.historial)][-2:],
                         [("stock_inicial", "FALLO"), ("catalogo", "OK")])

    def test_criterio_3_otros_fallos_tambien_conservan_la_fecha(self):
        casos = {
            "archivo borrado": (lambda: self.stock.unlink(), "no se encontró el archivo"),
            "archivo vacío": (lambda: self.stock.write_text("codigo_unico,fecha_corte,stock_inicial\n",
                                                            encoding="utf-8"), "no tiene registros"),
            "fecha mal escrita": (lambda: self.stock.write_text(
                "codigo_unico,fecha_corte,stock_inicial\nREP-0001,31/08/2026,20\n", encoding="utf-8"),
                "formato inválido"),
            "no es texto": (lambda: self.stock.write_bytes(b"\xff\xfe\x00\x01PK\x03\x04"), "UTF-8"),
            "ninguna fecha": (lambda: self.stock.write_text(
                "codigo_unico,fecha_corte,stock_inicial\nREP-0001,,20\n", encoding="utf-8"), "ninguna fila tiene fecha"),
        }
        for caso, (romper, motivo) in casos.items():
            with self.subTest(caso=caso):
                self.tearDown()
                self.setUp()
                self.cargar(["stock_inicial"], "2026-10-20 10:00 UTC")
                romper()
                fallos = self.cargar(["stock_inicial"], "2026-10-26 15:30 UTC")
                self.assertEqual(len(fallos), 1)
                self.assertIn(motivo, fallos[0][1])
                self.assertEqual(self.estado("stock_inicial")["ultima_actualizacion"], "2026-10-20 10:00 UTC")

    def test_un_rango_de_fechas_y_un_dato_pendiente_no_son_fallos(self):
        self.stock.write_text("codigo_unico,fecha_corte,stock_inicial\n"
                              "REP-0001,2025-09 a 2026-08,20\nREP-0002,,5\nREP-0003,2026-06,7\n", encoding="utf-8")

        fallos = self.cargar(["stock_inicial"], "2026-10-20 10:00 UTC")

        self.assertEqual(fallos, [])
        self.assertEqual(self.estado("stock_inicial")["fecha_corte_datos"], "2026-08")

    def test_despues_de_un_fallo_una_carga_buena_limpia_el_aviso(self):
        self.cargar(["stock_inicial"], "2026-10-20 10:00 UTC")
        self.stock.unlink()
        self.cargar(["stock_inicial"], "2026-10-21 10:00 UTC")
        escribir(self.stock, [{"codigo_unico": "REP-0001", "fecha_corte": "2026-09-30", "stock_inicial": "18"}])

        self.cargar(["stock_inicial"], "2026-10-22 10:00 UTC")

        e = self.estado("stock_inicial")
        self.assertEqual((e["ultima_actualizacion"], e["estado_ultima_carga"], e["detalle_fallo"]),
                         ("2026-10-22 10:00 UTC", "OK", ""))

    def test_desde_la_linea_de_comandos_el_fallo_se_muestra_y_sale_con_error(self):
        comando = [sys.executable, str(SRC / "registro_fuentes.py"), "actualizar", "--todos",
                   "--raiz", str(self.raiz), "--catalogo", str(self.catalogo),
                   "--registro", str(self.registro), "--historial", str(self.historial)]
        bien = subprocess.run(comando + ["--fecha", "2026-10-20 10:00 UTC"], capture_output=True, text=True)
        self.stock.unlink()

        mal = subprocess.run(comando + ["--fecha", "2026-10-26 15:30 UTC"], capture_output=True, text=True)

        self.assertEqual(bien.returncode, 0, bien.stdout + bien.stderr)
        self.assertEqual(mal.returncode, 1, mal.stdout + mal.stderr)
        self.assertIn("FALLO stock_inicial: no se encontró el archivo HU-18/stock_inicial.csv", mal.stdout)
        self.assertIn("2026-10-20 10:00 UTC (datos al 2026-08-31)", mal.stdout)


if __name__ == "__main__":
    unittest.main()
