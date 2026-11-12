"""Pruebas del motor del simulador de compras (src/simulador/motor.js y su referencia motor_ref.py).

La app usa motor.js. motor_ref.py repite el cálculo en Python y estas pruebas comprueban que los dos dan lo
mismo en 20 casos fijos, además de las reglas de negocio del contrato. Las pruebas que necesitan JavaScript
llaman a `node`; si no está instalado, se saltan con un mensaje.

Los datos se arman con tests/_datos_motor.py desde los CSV de SCRUM-55 y SCRUM-54, con las claves del contrato.
"""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MOTOR_JS = RAIZ / "src" / "simulador" / "motor.js"
sys.path.insert(0, str(RAIZ / "src" / "simulador"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_ref as ref  # noqa: E402
import _datos_motor  # noqa: E402

NODE = shutil.which("node")
SIN_NODE = "node no está instalado: se salta la comparación con motor.js"
TOL = 1e-9

SUP_BASE = {"tc_base": 11.75, "tc_90": 11.75, "venta_pct": 0, "atraso_dias": 0, "precio_sigue_dolar": False}


def sup(**cambios):
    s = dict(SUP_BASE)
    s.update(cambios)
    return s


# Veinte casos fijos: repuestos, proveedores, supuestos y semillas variados, y todas las funciones del motor.
CASOS = [
    {"f": "costoPuesto", "rep": "REP-0001", "prov": "PROV-US-03", "tc": 11.99},
    {"f": "compararProveedores", "rep": "REP-0013", "tc": 11.75},
    {"f": "pronostico", "rep": "REP-0005", "tipo": None},
    {"f": "pronostico", "rep": "REP-0019", "tipo": "suave"},
    {"f": "simular", "rep": "REP-0001", "prov": None, "sup": sup(), "opc": {"n": 300}},
    {"f": "simular", "rep": "REP-0020", "prov": "PROV-CN-01",
     "sup": sup(tc_90=13.0, venta_pct=20, atraso_dias=10, precio_sigue_dolar=True), "opc": {"n": 300, "semilla": 99}},
    {"f": "simular", "rep": "REP-0022", "prov": "PROV-BR-01", "sup": sup(tc_base=11.99, tc_90=10.5, venta_pct=-20),
     "opc": {"n": 300, "semilla": 12345}},
    {"f": "simular", "rep": "REP-0009", "prov": None, "sup": sup(tc_90=12.2, atraso_dias=25, precio_sigue_dolar=True),
     "opc": {"n": 300, "semilla": 7}},
    {"f": "simular", "rep": "REP-0013", "prov": "PROV-US-03", "sup": sup(venta_pct=30), "opc": {"n": 300, "semilla": 2}},
    {"f": "simular", "rep": "REP-0029", "prov": "PROV-CN-04", "sup": sup(tc_base=14, tc_90=14.5, atraso_dias=30),
     "opc": {"n": 300, "semilla": 3}},
    {"f": "simular", "rep": "REP-0023", "prov": None, "sup": sup(venta_pct=-30, precio_sigue_dolar=True),
     "opc": {"n": 300, "semilla": 4}},
    {"f": "simular", "rep": "REP-0005", "prov": "PROV-US-01", "sup": sup(tc_90=12.8),
     "opc": {"n": 250, "semilla": 4294967295, "horizonte_dias": 120}},
    {"f": "quiebreDolar", "rep": "REP-0001", "prov": None, "sup": sup(), "opc": {"n": 120}},
    {"f": "quiebreDolar", "rep": "REP-0022", "prov": "PROV-CN-02", "sup": sup(atraso_dias=15), "opc": {"n": 120, "semilla": 5}},
    {"f": "sensibilidad", "rep": "REP-0020", "prov": None, "sup": sup(tc_90=12.0), "opc": {"n": 120}},
    {"f": "alertas", "tc": 11.75},
    {"f": "planPresupuesto", "tc": 11.99, "presupuesto": 5000},
    {"f": "pasado", "politica": "lo_justo"},
    {"f": "pasado", "politica": "cubrir_60"},
    {"f": "pasado", "politica": "dos_pedidos"},
]

RUNNER_JS = r"""
const fs = require("fs");
const M = require(process.argv[2]);
const D = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const C = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const rep = id => D.repuestos.find(r => r.repuesto_id === id);
const prov = id => D.proveedores.find(p => p.proveedor_id === id);
function correr(c) {
  switch (c.f) {
    case "costoPuesto": return M.costoPuesto(rep(c.rep), prov(c.prov), c.tc);
    case "compararProveedores": return M.compararProveedores(D, c.rep, c.tc);
    case "pronostico": return M.pronostico(D.ventas[c.rep], c.tipo === null ? undefined : c.tipo);
    case "simular": return M.simular(D, c.rep, c.prov, c.sup, c.opc);
    case "quiebreDolar": return M.quiebreDolar(D, c.rep, c.prov, c.sup, c.opc);
    case "sensibilidad": return M.sensibilidad(D, c.rep, c.prov, c.sup, c.opc);
    case "alertas": return M.alertas(D, c.tc);
    case "planPresupuesto": return M.planPresupuesto(M.alertas(D, c.tc), c.presupuesto);
    case "pasado": return M.pasado(D, c.politica);
    case "mulberry": { const r = M._interno.mulberry32(c.semilla); const v = []; for (let i = 0; i < c.k; i++) v.push(r()); return v; }
    case "costosAsignados": return D.repuestos.map(r => M.costoPuesto(r, prov(r.proveedor_id), c.tc).total_bs);
    case "simular30": return D.repuestos.map(r => {
      const t = process.hrtime.bigint();
      const s = M.simular(D, r.repuesto_id, null, c.sup, c.opc);
      return { id: r.repuesto_id, ms: Number(process.hrtime.bigint() - t) / 1e6, s: s };
    });
    case "quiebre30": return D.repuestos.map(r => {
      const t = process.hrtime.bigint();
      const q = M.quiebreDolar(D, r.repuesto_id, null, c.sup, c.opc);
      const ms = Number(process.hrtime.bigint() - t) / 1e6;
      const en = v => M.simular(D, r.repuesto_id, null, Object.assign({}, c.sup, { tc_90: v }), c.opc).mejor;
      return q ? { id: r.repuesto_id, ms: ms, q: q, bajo: en(Math.round(q.valor * 100 - 5) / 100), alto: en(q.valor) }
               : { id: r.repuesto_id, ms: ms, q: null, en9: en(9), en15: en(15) };
    });
  }
  throw new Error("caso desconocido " + c.f);
}
process.stdout.write(JSON.stringify(C.map(correr)));
"""


def correr_ref(datos, c):
    """Ejecuta un caso con motor_ref.py y devuelve el resultado normalizado como JSON."""
    rep = lambda rid: ref.buscar_repuesto(datos, rid)  # noqa: E731
    f = c["f"]
    if f == "costoPuesto":
        r = ref.costo_puesto(rep(c["rep"]), ref.buscar_proveedor(datos, c["prov"]), c["tc"])
    elif f == "compararProveedores":
        r = ref.comparar_proveedores(datos, c["rep"], c["tc"])
    elif f == "pronostico":
        r = ref.pronostico(datos["ventas"][c["rep"]], c["tipo"])
    elif f == "simular":
        r = ref.simular(datos, c["rep"], c["prov"], c["sup"], c["opc"])
    elif f == "quiebreDolar":
        r = ref.quiebre_dolar(datos, c["rep"], c["prov"], c["sup"], c["opc"])
    elif f == "sensibilidad":
        r = ref.sensibilidad(datos, c["rep"], c["prov"], c["sup"], c["opc"])
    elif f == "alertas":
        r = ref.alertas(datos, c["tc"])
    elif f == "planPresupuesto":
        r = ref.plan_presupuesto(ref.alertas(datos, c["tc"]), c["presupuesto"])
    elif f == "pasado":
        r = ref.pasado(datos, c["politica"])
    elif f == "mulberry":
        g = ref.mulberry32(c["semilla"])
        r = [g() for _ in range(c["k"])]
    else:
        raise ValueError(f)
    return json.loads(json.dumps(r))


def diferencias(a, b, ruta="$"):
    """Lista de diferencias entre dos resultados: números con tolerancia 1e-9, enteros y textos exactos."""
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return [] if a == b and type(a) is type(b) else ["%s: %r != %r" % (ruta, a, b)]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, int) and isinstance(b, int):
            return [] if a == b else ["%s: %r != %r" % (ruta, a, b)]
        return [] if abs(a - b) <= TOL * max(1.0, abs(a), abs(b)) else ["%s: %r != %r" % (ruta, a, b)]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return ["%s: claves %s != %s" % (ruta, sorted(a), sorted(b))]
        out = []
        for k in a:
            out += diferencias(a[k], b[k], "%s.%s" % (ruta, k))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return ["%s: largo %d != %d" % (ruta, len(a), len(b))]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diferencias(x, y, "%s[%d]" % (ruta, i))
        return out
    return ["%s: tipos %s != %s" % (ruta, type(a).__name__, type(b).__name__)]


class _ConDatos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datos = _datos_motor.cargar()
        cls.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(cls.tmp.name)
        cls.ruta_datos = carpeta / "datos.json"
        cls.ruta_datos.write_text(json.dumps(cls.datos), encoding="utf-8")
        cls.runner = carpeta / "runner.js"
        cls.runner.write_text(RUNNER_JS, encoding="utf-8")
        cls.carpeta = carpeta

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def js(self, casos):
        if not NODE:
            self.skipTest(SIN_NODE)
        ruta = self.carpeta / "casos.json"
        ruta.write_text(json.dumps(casos), encoding="utf-8")
        res = subprocess.run([NODE, str(self.runner), str(MOTOR_JS), str(self.ruta_datos), str(ruta)],
                             capture_output=True, text=True, timeout=600)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)


class EquivalenciaJsPython(_ConDatos):
    """(a) y (h): motor.js y motor_ref.py dan lo mismo, y la comparación sabe fallar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._res_js = None

    def resultados_js(self):
        if type(self)._res_js is None:
            type(self)._res_js = self.js(CASOS)
        return type(self)._res_js

    def test_veinte_casos_fijos_iguales(self):
        self.assertEqual(len(CASOS), 20)
        res_js = self.resultados_js()
        for i, c in enumerate(CASOS):
            with self.subTest(caso=i, f=c["f"]):
                dif = diferencias(res_js[i], correr_ref(self.datos, c))
                self.assertEqual(dif, [], "\n".join(dif[:10]))

    def test_casos_no_triviales(self):
        """Evita que la equivalencia pase por comparar resultados vacíos."""
        res_js = self.resultados_js()
        sim = [r for c, r in zip(CASOS, res_js) if c["f"] == "simular"]
        self.assertEqual(len(sim), 8)
        self.assertTrue(all(any(r[L]["ganancia_media_bs"] != 0 for L in "ABCD") for r in sim))
        self.assertGreater(len({r["mejor"] for r in sim} | {r["A"]["puntaje"] for r in sim}), 2)
        self.assertTrue(any(r is not None for c, r in zip(CASOS, res_js) if c["f"] == "quiebreDolar"))
        self.assertTrue(all(r["pedidos"] > 0 for c, r in zip(CASOS, res_js) if c["f"] == "pasado"))

    def test_mulberry32_bit_a_bit(self):
        casos = [{"f": "mulberry", "semilla": s, "k": 50} for s in (0, 1, 20261112, 4294967295)]
        for c, r in zip(casos, self.js(casos)):
            self.assertEqual(r, correr_ref(self.datos, c))  # igualdad exacta, sin tolerancia

    def test_control_negativo_detecta_un_parametro_distinto(self):
        """(h) Si un lado usa otro costo por pedido, la comparación del caso 5 tiene que fallar."""
        caso = CASOS[4]
        res_js = self.resultados_js()[4]
        self.assertEqual(diferencias(res_js, correr_ref(self.datos, caso)), [])
        alterado = copy.deepcopy(self.datos)
        alterado["parametros"]["costo_pedido_bs"] = 351
        self.assertNotEqual(diferencias(res_js, correr_ref(alterado, caso)), [])
        # Lo mismo con el costo del capital en «¿Qué hubiera pasado?» (caso 18).
        alterado = copy.deepcopy(self.datos)
        alterado["parametros"]["costo_capital_mensual"] = 0.016
        self.assertEqual(diferencias(self.resultados_js()[17], correr_ref(self.datos, CASOS[17])), [])
        self.assertNotEqual(diferencias(self.resultados_js()[17], correr_ref(alterado, CASOS[17])), [])


class CostoPuesto(_ConDatos):
    """(b) Con el proveedor asignado y 11,75 Bs/USD se reproduce costo_puesto_bs de repuestos.csv."""

    def test_reproduce_repuestos_csv_en_python(self):
        self.assertEqual(len(self.datos["repuestos"]), 30)
        for r in self.datos["repuestos"]:
            c = ref.costo_puesto(r, ref.buscar_proveedor(self.datos, r["proveedor_id"]), 11.75)
            self.assertEqual(c["total_bs"], r["costo_puesto_bs"], r["repuesto_id"])
            self.assertEqual(c["total_usd"], r["costo_puesto_usd"], r["repuesto_id"])
            self.assertAlmostEqual(c["fabrica_bs"] + c["flete_bs"] + c["gastos_bs"], c["total_bs"], places=6)
            if c["flete_incluido"]:
                self.assertEqual(c["flete_bs"], 0)

    def test_reproduce_repuestos_csv_en_js(self):
        totales = self.js([{"f": "costosAsignados", "tc": 11.75}])[0]
        self.assertEqual(totales, [r["costo_puesto_bs"] for r in self.datos["repuestos"]])

    def test_comparar_proveedores_ordenado(self):
        filas = ref.comparar_proveedores(self.datos, "REP-0007", 11.75)
        self.assertEqual(len(filas), 10)
        self.assertEqual([f["total_bs"] for f in filas], sorted(f["total_bs"] for f in filas))
        self.assertEqual(sum(f["asignado"] for f in filas), 1)
        self.assertEqual(len({f["fabrica_bs"] for f in filas}), 1)  # mismo precio de fábrica para todos


class SimulacionTreintaRepuestos(_ConDatos):
    """(c) Puntajes y riesgo con n = 1500 en los 30 repuestos, y el tiempo por repuesto."""

    def test_puntajes_y_riesgo(self):
        filas = self.js([{"f": "simular30", "sup": SUP_BASE, "opc": {"n": 1500}}])[0]
        self.assertEqual(len(filas), 30)
        for f in filas:
            s = f["s"]
            total = sum(s[L]["puntaje"] for L in "ABCD")
            self.assertLessEqual(abs(total - 100), 1, f["id"])
            self.assertIn(s["mejor"], "ABCD")
            for L in "ABCD":
                self.assertIsInstance(s[L]["riesgo_quiebre"], int)
                self.assertTrue(0 <= s[L]["riesgo_quiebre"] <= 100)
                self.assertIsInstance(s[L]["puntaje"], int)
                self.assertGreaterEqual(s[L]["cantidad"], 0)
            self.assertLessEqual(s["A"]["cantidad"], s["B"]["cantidad"])
            self.assertLessEqual(s["B"]["cantidad"], s["C"]["cantidad"])
            self.assertEqual(s["C"]["cantidad"], s["D"]["cantidad"])
            self.assertEqual(s["D"]["pedidos"], 2 if s["D"]["cantidad"] > 1 else 1)
        tiempos = sorted(f["ms"] for f in filas)
        print("\n[motor] simular n=1500: mediana %.1f ms, máximo %.1f ms por repuesto" % (tiempos[15], tiempos[-1]))
        self.assertLess(tiempos[-1], 300)


class QuiebreDolar(_ConDatos):
    """(d) Bajo el valor gana `antes` y desde el valor gana `despues`, con la misma semilla."""

    def test_quiebre_en_los_30(self):
        filas = self.js([{"f": "quiebre30", "sup": SUP_BASE, "opc": {"n": 400}}])[0]
        con = [f for f in filas if f["q"] is not None]
        for f in con:
            self.assertEqual(f["bajo"], f["q"]["antes"], f["id"])
            self.assertEqual(f["alto"], f["q"]["despues"], f["id"])
            self.assertNotEqual(f["q"]["antes"], f["q"]["despues"])
            self.assertTrue(9 < f["q"]["valor"] <= 15)
        for f in filas:
            if f["q"] is None:
                self.assertEqual(f["en9"], f["en15"], f["id"])
        self.assertGreaterEqual(len(con), 10)
        pares = {}
        for f in con:
            k = "%s→%s" % (f["q"]["antes"], f["q"]["despues"])
            pares[k] = pares.get(k, 0) + 1
        print("\n[motor] quiebre de dólar en %d de 30 repuestos: %s; valores %s; máximo %.0f ms" % (
            len(con), pares, sorted({f["q"]["valor"] for f in con}), max(f["ms"] for f in filas)))


class Alertas(_ConDatos):
    """(e) 30 filas, orden por estado y margen, y la regla del estado 0."""

    def test_alertas(self):
        filas = ref.alertas(self.datos, 11.75)
        self.assertEqual(len(filas), 30)
        self.assertEqual(len({f["id"] for f in filas}), 30)
        claves = [(f["est"], f["margen_dias"]) for f in filas]
        self.assertEqual(claves, sorted(claves))
        for f in filas:
            self.assertEqual(f["etiqueta"], ["Pedir ya", "Vigilar", "Cubierto"][f["est"]])
            self.assertEqual(f["est"] == 0, f["stock"] + f["en_camino"] <= f["punto_pedido"], f["id"])
            if f["est"] < 2:
                self.assertGreaterEqual(f["cantidad_sugerida"], 1)
            self.assertGreaterEqual(f["cantidad_sugerida"], 0)
        self.assertTrue(any(f["est"] == 0 for f in filas), "ninguna fila en «Pedir ya»: la prueba no diría nada")


class PlanPresupuesto(_ConDatos):
    """(f) Acumulado que no baja y `alcanza` falso desde el primero que pasa el presupuesto."""

    def test_plan(self):
        alertas = ref.alertas(self.datos, 11.75)
        total = sum(f["costo_bs"] for f in alertas)
        for presupuesto in (0, 1500, 5000, total / 2, total + 1):
            with self.subTest(presupuesto=presupuesto):
                filas = ref.plan_presupuesto(alertas, presupuesto)
                acum = [f["acumulado_bs"] for f in filas]
                self.assertEqual(acum, sorted(acum))
                primero = next((i for i, f in enumerate(filas) if f["acumulado_bs"] > presupuesto + 1e-9), len(filas))
                self.assertEqual([f["alcanza"] for f in filas], [i < primero for i in range(len(filas))])
                orden = [(f["est"], "ABC".index(f["clase"])) for f in filas]
                self.assertEqual(orden, sorted(orden))
        # Con 1.500 Bs entra una parte y otra no: la regla se prueba en los dos lados del corte.
        plan = ref.plan_presupuesto(alertas, 1500)
        self.assertTrue(plan[0]["alcanza"])
        self.assertFalse(plan[-1]["alcanza"])
        self.assertTrue(all(isinstance(f["cantidad_sugerida"], int) for f in plan))


class Pasado(_ConDatos):
    """(g) Determinista, tres políticas con métricas, y el TCO del día en las órdenes desde el 27-06-2026."""

    def test_pasado(self):
        tco = {f: v for f, v in self.datos["tc"]["serie"]}
        for politica in ("lo_justo", "cubrir_60", "dos_pedidos"):
            with self.subTest(politica=politica):
                r1 = ref.pasado(self.datos, politica)
                self.assertEqual(r1, ref.pasado(self.datos, politica))
                for k in ("ventas_perdidas", "capital_promedio_bs", "pedidos", "ganancia_bs"):
                    self.assertIn(k, r1)
                self.assertGreater(r1["pedidos"], 0)
                self.assertGreater(r1["capital_promedio_bs"], 0)
                despues = [o for o in r1["ordenes"] if o["fecha"] >= "2026-06-27"]
                antes = [o for o in r1["ordenes"] if o["fecha"] < "2026-06-27"]
                self.assertTrue(despues and antes)
                for o in despues:
                    self.assertEqual(o["tc"], tco[o["fecha"]], o)
                for o in antes:
                    self.assertEqual(o["tc"], 6.96, o)
                self.assertTrue(all("2025-11-01" <= o["fecha"] <= "2026-10-31" for o in r1["ordenes"]))


if __name__ == "__main__":
    unittest.main()
