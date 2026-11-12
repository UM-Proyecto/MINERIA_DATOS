"""Pruebas de la verificación de datos de HU-09 (Sabrina Adrian Zelaya).

Son sus pruebas de conciliación de inventario y plazo. Las de alertas pasaron a tests/test_generar_alertas.py, junto
con la lógica única, y las del modo demostración se retiraron con ese modo el 12-11-2026.
"""
import copy
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src/hu-09"))
from verificar_datos import (CAMPOS_DEMANDA, FUENTES, cargar_integracion, equivalencias_hu17, ejecutar, leer_csv,
                             normalizar)


def escribir_csv(ruta, filas, campos=None):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos or list(filas[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


PRONOSTICO = {"sistema_codigos": "REP", "codigo_repuesto": "REP-0001", "proveedor": "", "metodo": "caso_de_prueba",
              "validado": "true", "fecha_emision": "2026-10-20", "inicio_horizonte": "2026-10-21",
              "fin_horizonte": "2026-12-04", "tipo_pronostico": "TASA_CONSTANTE", "fecha_objetivo": "", "demanda": "4",
              "unidad_temporal": "unidades/dia", "distribucion": "", "tipo_dato": "SINTETICO",
              "fuente": "Caso sintético controlado"}


class IntegracionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        for ruta, _ in FUENTES.values():
            destino = self.raiz / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ / ruta, destino)
        # La configuración real de integración, con las fechas y políticas del caso de prueba original.
        self.config = json.loads((RAIZ / "data/raw/hu-09/configuracion.json").read_text(encoding="utf-8"))
        self.config.update(fecha_evaluacion="2026-10-20", max_antiguedad_stock_dias=20,
                           permitir_pendientes_con_conteo_coincidente=True, tipo_dias_plazo="naturales")
        destino = self.raiz / self.config["demanda"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        escribir_csv(destino, [PRONOSTICO], CAMPOS_DEMANDA)
        self.ruta_config = self.raiz / "config.json"
        self.guardar_config()

    def guardar_config(self):
        self.ruta_config.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    def cargar(self):
        self.guardar_config()
        return cargar_integracion(self.ruta_config, self.raiz)

    def tabla(self, nombre):
        ruta, campos = FUENTES[nombre]
        return leer_csv(self.raiz / ruta, campos.split())

    def modificar_tabla(self, nombre, filas):
        escribir_csv(self.raiz / FUENTES[nombre][0], filas)

    def test_deduplicacion_preserva_lineas_legitimas(self):
        dep = self.tabla("depuracion")
        plantilla = next(r for r in dep if r["id_movimiento"] == "1015")
        dep.append(dict(plantilla, id_movimiento="2000", cantidad="3"))  # otra línea válida de la misma orden
        self.modificar_tabla("depuracion", dep)
        conc = self.tabla("conciliacion")
        for r in conc:
            if r["codigo_unico"] == "REP-0006":
                r.update(entradas="103", stock_registrado="133", conteo_fisico="133")
        self.modificar_tabla("conciliacion", conc)
        _, registros, _ = self.cargar()
        s = next(r for r, _ in registros if r["codigo_unico"] == "REP-0006")
        self.assertEqual(s["stock_registrado"], 133)
        self.assertEqual(s["duplicados_excluidos"], "1016")

    def test_ajustes_aplicados_se_cuentan_una_vez(self):
        for _ in range(2):
            _, registros, _ = self.cargar()
            stocks = {r["codigo_unico"]: r for r, _ in registros}
            self.assertEqual((stocks["REP-0002"]["stock_registrado"], stocks["REP-0002"]["stock_ajustado"]), (55, 53))
            self.assertEqual((stocks["REP-0004"]["stock_registrado"], stocks["REP-0004"]["stock_ajustado"]), (28, 18))
            self.assertEqual(stocks["REP-0004"]["ajustes_mismo_corte"], "1")

    def test_rechazos_repetidos_y_discrepancias_no_cambian_stock(self):
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0007")
        self.assertEqual((r["stock_registrado"], r["stock_ajustado"], r["ajustes_rechazados"]), (9, 9, 4))
        self.assertIsNone(r["stock_disponible"])
        self.assertIn("DIFERENCIA_CONTEO_PENDIENTE", r["motivos"])

    def test_ajustes_duplicados_o_sin_respaldo_se_rechazan(self):
        ajustes = self.tabla("ajustes")
        self.modificar_tabla("ajustes", ajustes + [ajustes[0]])
        with self.assertRaisesRegex(ValueError, "duplicado"):
            self.cargar()
        self.modificar_tabla("ajustes", ajustes)
        self.modificar_tabla("historial", [r for r in self.tabla("historial") if r["accion"] != "AJUSTE_APLICADO"])
        with self.assertRaisesRegex(ValueError, "Respaldo"):
            self.cargar()

    def test_ajustes_futuros_no_se_usan_retrospectivamente(self):
        self.config["fecha_evaluacion"] = "2026-09-30"
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0004")
        self.assertEqual(r["stock_ajustado"], 28)
        self.assertIn("AJUSTE_POSTERIOR_A_EVALUACION", r["motivos"])
        self.assertIsNone(r["stock_disponible"])

    def test_reservas_desconocidas_y_pendientes_no_se_ignoran(self):
        self.config["disponibilidad"] = {"politica": "no_confirmada", "motivo": "Sin información"}
        self.config["permitir_pendientes_con_conteo_coincidente"] = False
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0001")
        self.assertIn("RESERVAS_Y_BLOQUEOS_DESCONOCIDOS", r["motivos"])
        self.assertIn("MOVIMIENTOS_PENDIENTES_REVISION", r["motivos"])
        self.assertIsNone(r["reservas"])

    def test_reservas_confirmadas_se_restan_sin_inventarlas(self):
        self.config["disponibilidad"] = {"politica": "confirmadas", "motivo": "Confirmación de prueba", "confirmaciones": {
            "REP-0002": {"reservas": "3", "bloqueos": "2", "fecha": "2026-09-30", "fuente": "Registro sintético", "tipo_dato": "SINTETICO"}}}
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0002")
        self.assertEqual(r["stock_disponible"], 48)  # 55 - ajuste 2 - reservas 3 - bloqueos 2
        self.assertEqual(r["naturaleza_disponibilidad"], "SINTETICO")
        self.config["disponibilidad"]["confirmaciones"]["REP-0002"]["reservas"] = "100"
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0002")
        self.assertIn("RESERVAS_Y_BLOQUEOS_SUPERAN_STOCK", r["motivos"])

    def test_plazo_de_hu31_no_es_condicion_de_pago_y_vence(self):
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0004")
        self.assertEqual(r["plazo_dias"], 3)  # la cotización dice Crédito 30 días
        self.config["fecha_evaluacion"] = "2026-11-10"
        _, registros, _ = self.cargar()
        r = next(r for r, _ in registros if r["codigo_unico"] == "REP-0004")
        self.assertIsNone(r["plazo_dias"])
        self.assertEqual(r["plazo_referencia_dias"], 3)
        self.assertIn("COTIZACION_VENCIDA", r["motivos"])

    def test_alias_hu17_y_rechazo_de_rp_sin_equivalencia(self):
        eq = equivalencias_hu17(self.tabla("depuracion"))
        self.assertEqual(normalizar("TOY-FA01", "REP", eq), "REP-0002")
        with self.assertRaises(ValueError):
            normalizar("RP001", "RP", eq)
        with self.assertRaises(ValueError):
            normalizar("REP-9999", "REP", eq)

    def test_pronosticos_duplicados_y_negativos_se_rechazan(self):
        ruta = self.raiz / self.config["demanda"]
        filas = leer_csv(ruta, CAMPOS_DEMANDA)
        escribir_csv(ruta, filas + [filas[0]])
        with self.assertRaisesRegex(ValueError, "duplicada"):
            self.cargar()
        filas[0]["demanda"] = "-1"
        escribir_csv(ruta, filas)
        with self.assertRaises(ValueError):
            self.cargar()

    def test_csv_de_mae_no_cumple_contrato_de_demanda(self):
        shutil.copyfile(RAIZ / "data/processed/hu-07/comparacion_pronosticos.csv", self.raiz / self.config["demanda"])
        with self.assertRaisesRegex(ValueError, "faltan columnas"):
            self.cargar()

    def test_cabecera_sola_y_demanda_vacia_no_son_cero(self):
        ruta = self.raiz / self.config["demanda"]
        escribir_csv(ruta, [], CAMPOS_DEMANDA)
        _, registros, _ = self.cargar()
        self.assertTrue(all(d is None for _, d in registros))
        resultado = ejecutar(self.ruta_config, raiz=self.raiz)
        self.assertEqual(len(resultado["filas"]), 10)

    def test_regeneracion_identica_conserva_entradas_y_svg(self):
        originales = [self.raiz / p for p, _ in FUENTES.values()] + [self.ruta_config, self.raiz / self.config["demanda"]]
        antes = {p: p.read_bytes() for p in originales}
        r = ejecutar(self.ruta_config, raiz=self.raiz)
        primera = {p: p.read_bytes() for p in r["artefactos"]}
        ejecutar(self.ruta_config, raiz=self.raiz)
        self.assertEqual(primera, {p: p.read_bytes() for p in r["artefactos"]})
        self.assertEqual(antes, {p: p.read_bytes() for p in originales})
        filas = leer_csv(next(p for p in r["artefactos"] if p.name == "dataset_consolidado.csv"), ["verificado", "stock_disponible"])
        self.assertTrue(all(f["stock_disponible"] == "" for f in filas if f["verificado"] == "false"))

    def test_error_no_sobrescribe_salida_y_modos_separados(self):
        r = ejecutar(self.ruta_config, raiz=self.raiz)
        antes = {p: p.read_bytes() for p in r["artefactos"]}
        with self.assertRaisesRegex(ValueError, "fuera de HU-09"):
            ejecutar(self.ruta_config, salida=self.raiz / "data/processed/hu-07", raiz=self.raiz)
        self.config["fecha_stock"] = "2026-11-01"
        self.guardar_config()
        with self.assertRaises(ValueError):
            ejecutar(self.ruta_config, raiz=self.raiz)
        self.assertEqual(antes, {p: p.read_bytes() for p in r["artefactos"]})

    def test_no_admite_reservas_cero_sin_confirmacion_ni_modo_demostracion(self):
        self.config["disponibilidad"] = {"politica": "asumir_libre_solo_simulacion", "motivo": "prueba"}
        with self.assertRaisesRegex(ValueError, "Política de disponibilidad inválida"):
            self.cargar()
        self.config["disponibilidad"] = {"politica": "no_confirmada", "motivo": "prueba"}
        self.config["modo"] = "DEMOSTRACION_SINTETICA"
        with self.assertRaisesRegex(ValueError, "Modo inválido"):
            self.cargar()


class RepositorioTest(unittest.TestCase):
    def test_integracion_actual_no_inventa_datos_y_preserva_otras_hu(self):
        fuentes = [RAIZ / p for p, _ in FUENTES.values()] + [RAIZ / "src/hu-07/comparar_pronosticos.py", RAIZ / "data/processed/hu-07/comparacion_pronosticos.csv"]
        antes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes}
        with tempfile.TemporaryDirectory() as t:
            r = ejecutar(salida=Path(t) / "csv", reporte=Path(t) / "reporte/VERIFICACION.md")
            self.assertEqual(Counter(f["verificado"] for f in r["filas"]), {False: 10})
            self.assertTrue(all("RESERVAS_Y_BLOQUEOS_DESCONOCIDOS" in f["motivos"] and f["stock_disponible"] is None for f in r["filas"]))
            self.assertEqual(sum(f["plazo_dias"] is not None for f in r["filas"]), 1)
        self.assertEqual(antes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes})

    def test_cli_desde_otro_directorio_y_error_controlado(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            cmd = [sys.executable, str(RAIZ / "src/hu-09/verificar_datos.py"), "--salida", str(t / "csv"), "--reporte", str(t / "reporte/VERIFICACION.md")]
            r = subprocess.run(cmd, cwd=t, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(b"0 de 10 repuestos verificados", r.stdout)
            error = subprocess.run(cmd + ["--config", str(t / "ausente.json")], cwd=t, capture_output=True)
            self.assertEqual(error.returncode, 1)
            self.assertIn(b"HU-09:", error.stderr)


if __name__ == "__main__":
    unittest.main()
