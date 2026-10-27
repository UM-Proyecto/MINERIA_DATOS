import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "hu-07"))
from comparar_pronosticos import evaluar


class ComparacionTest(unittest.TestCase):
    def test_reserva_los_mismos_dias_y_no_usa_la_prueba_para_pronosticar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "movimientos.csv"
            filas = []
            inicio = date(2026, 9, 1)
            for i in range(10):
                filas.append({
                    "fecha": (inicio + timedelta(days=i)).isoformat(),
                    "codigo_unico": "REP-TEST",
                    "tipo_movimiento": "SALIDA" if i in (7, 8, 9) else "ENTRADA",
                    "cantidad": 10 if i == 8 else 2,
                    "estado": "ORIGINAL",
                })
            filas.append({**filas[8], "estado": "DUPLICADO"})
            with ruta.open("w", newline="", encoding="utf-8") as archivo:
                escritor = csv.DictWriter(archivo, fieldnames=filas[0].keys())
                escritor.writeheader()
                escritor.writerows(filas)

            resultado, ultimo_entrenamiento, primera_evaluacion = evaluar(ruta, dias_prueba=2)

            self.assertEqual((ultimo_entrenamiento, primera_evaluacion), (date(2026, 9, 8), date(2026, 9, 9)))
            self.assertEqual({fila["periodos_evaluados"] for fila in resultado}, {2})
            self.assertEqual({fila["mae"] for fila in resultado if fila["metodo"] == "ultimo_periodo"}, {"4.000"})
            self.assertEqual({fila["salidas_duplicadas_excluidas"] for fila in resultado}, {1})

    def test_compara_meses_y_selecciona_solo_con_un_ano_reservado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "movimientos.csv"
            with ruta.open("w", newline="", encoding="utf-8") as archivo:
                escritor = csv.DictWriter(
                    archivo,
                    fieldnames=["fecha", "codigo_unico", "tipo_movimiento", "cantidad", "estado"],
                )
                escritor.writeheader()
                for i in range(730):
                    escritor.writerow({
                        "fecha": (date(2024, 1, 1) + timedelta(days=i)).isoformat(),
                        "codigo_unico": "REP-TEST",
                        "tipo_movimiento": "SALIDA",
                        "cantidad": 1,
                        "estado": "ORIGINAL",
                    })

            resultado, _, _ = evaluar(ruta, dias_prueba=365)

            self.assertEqual({fila["periodos_evaluados"] for fila in resultado}, {365})
            self.assertTrue(all("2025-01:0.000" in fila["mae_por_mes"] for fila in resultado))
            self.assertEqual({fila["seleccion"] for fila in resultado}, {"ultimo_periodo"})


if __name__ == "__main__":
    unittest.main()
