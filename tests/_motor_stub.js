// Motor de reemplazo para construir y probar la app mientras el frente A termina src/simulador/motor.js.
// Respeta la API del contrato (nombres, argumentos y forma de lo que devuelve) con cálculos simples y
// deterministas: NO simula futuros. Las cifras son verosímiles, no correctas. Cuando se integre el motor
// real, este archivo deja de usarse.
var Motor = (function () {
  "use strict";
  function prov(datos, id) { return datos.proveedores.filter(function (p) { return p.proveedor_id === id; })[0]; }
  function rep(datos, id) { return datos.repuestos.filter(function (r) { return r.repuesto_id === id; })[0]; }

  function costoPuesto(r, p, tc) {
    var fab = r.costo_unitario_usd * tc;
    var flete = p.incoterm === "CIF" ? 0 : fab * p.flete_pct_aplicado / 100;
    var gastos = (fab + flete) * p.gastos_pct_cif / 100;
    return { fabrica_bs: fab, flete_bs: flete, gastos_bs: gastos, total_bs: fab + flete + gastos, flete_incluido: p.incoterm === "CIF" };
  }

  function pronostico(ventas) {
    var u = ventas.map(function (v) { return v[1]; }), ult = u.slice(-12);
    var media = ult.reduce(function (a, b) { return a + b; }, 0) / ult.length;
    var conVenta = u.filter(function (x) { return x > 0; }).length;
    var intermitente = conVenta < u.length * 0.75;
    return { metodo: intermitente ? "SBA" : "media", unidades_mes: intermitente ? media * 0.95 : media };
  }

  function simular(datos, repId, provId, sup, opc) {
    var r = rep(datos, repId), p = prov(datos, provId), f = pronostico(datos.ventas[repId]);
    var dia = Math.max(f.unidades_mes / 30, 0.02) * (1 + sup.venta_pct / 100);
    var plazo = p.plazo_normal_dias + sup.atraso_dias, disp = r.stock_al_2026_11_10 + r.en_transito_al_2026_11_10;
    var base = Math.max(0, Math.ceil(dia * plazo + dia * 10 - disp));
    var cant = { A: base, B: Math.ceil(base + dia * 30), C: Math.ceil(base + dia * 60), D: Math.ceil(base + dia * 60) };
    var subida = (sup.tc_90 - sup.tc_base) / sup.tc_base;
    var out = {}, mejor = "A", maxG = -Infinity, pts = {};
    ["A", "B", "C", "D"].forEach(function (k, i) {
      var c = costoPuesto(r, p, sup.tc_base), q = cant[k];
      var precio = r.precio_venta_bs * (sup.precio_sigue_dolar ? sup.tc_90 / sup.tc_base : 1);
      var vend = Math.min(q + disp, dia * 90);
      var pedidos = k === "D" ? 2 : 1;
      var costoQ = c.total_bs * q * (k === "D" ? 1 + subida / 2 : 1);
      var capital = c.total_bs * Math.max(0, q + disp - dia * plazo);
      var g = vend * precio - costoQ - datos.parametros.costo_pedido_bs * pedidos - capital * datos.parametros.costo_capital_mensual * 3 + subida * 900 * i;
      var riesgo = Math.max(1, Math.min(95, Math.round(60 - i * 15 + sup.atraso_dias - sup.venta_pct / 2)));
      out[k] = {
        cantidad: q,
        costo: { fabrica_bs: c.fabrica_bs * q, flete_bs: c.flete_bs * q * pedidos, gastos_bs: c.gastos_bs * q, total_bs: costoQ, pedidos: pedidos },
        margen_dias: Math.round((disp + q) / dia - plazo),
        riesgo_quiebre: k === "D" ? Math.max(1, riesgo + 6) : riesgo,
        unidades_perdidas: Math.round(riesgo * dia / 10 * 10) / 10,
        capital_inmovilizado_bs: capital,
        dias_venta_capital: Math.round(Math.max(0, q + disp - dia * plazo) / dia),
        ganancia_media_bs: g,
        ganancia_p10_bs: g * 0.62,
        puntaje: 0
      };
      if (g > maxG) { maxG = g; mejor = k; }
    });
    var reparto = { A: 18, B: 24, C: 31, D: 27 }, suma = 0;
    ["A", "B", "C", "D"].forEach(function (k) { pts[k] = reparto[k]; });
    pts[mejor] += 12; ["A", "B", "C", "D"].forEach(function (k) { suma += pts[k]; });
    ["A", "B", "C", "D"].forEach(function (k) { out[k].puntaje = Math.round(pts[k] * 100 / suma); });
    out.mejor = ["A", "B", "C", "D"].reduce(function (a, k) { return out[k].puntaje > out[a].puntaje ? k : a; }, "A");
    return out;
  }

  function quiebreDolar(datos, repId, provId, sup, opc) {
    var r = rep(datos, repId);
    if (r.clase_abc === "C") return null;
    var v = Math.round((sup.tc_base + 0.35 + (r.adi % 1)) * 20) / 20;
    return { valor: v, antes: "A", despues: "C" };
  }

  function sensibilidad(datos, repId, provId, sup, opc) {
    var r = rep(datos, repId), escala = r.precio_venta_bs * 20;
    return [
      { supuesto: "atraso", rango_bs: escala * 1.0, de: 0, a: 30 },
      { supuesto: "dolar", rango_bs: escala * 0.62, de: 9, a: 15 },
      { supuesto: "venta", rango_bs: escala * 0.35, de: -30, a: 30 }
    ];
  }

  function alertas(datos, tc) {
    var filas = datos.repuestos.map(function (r) {
      var p = prov(datos, r.proveedor_id), f = pronostico(datos.ventas[r.repuesto_id]);
      var dia = Math.max(f.unidades_mes / 30, 0.01), disp = r.stock_al_2026_11_10 + r.en_transito_al_2026_11_10;
      var hasta = (disp - r.punto_pedido_s) / dia;
      var est = disp <= r.punto_pedido_s ? 0 : (hasta < r.plazo_normal_dias ? 1 : 2);
      var cant = Math.max(est < 2 ? 1 : 0, r.nivel_maximo_S - disp);
      return { id: r.repuesto_id, est: est, etiqueta: ["Pedir ya", "Vigilar", "Cubierto"][est], stock: r.stock_al_2026_11_10,
        en_camino: r.en_transito_al_2026_11_10, punto_pedido: r.punto_pedido_s, plazo: r.plazo_normal_dias,
        margen_dias: Math.round(hasta), cantidad_sugerida: cant, costo_bs: cant * costoPuesto(r, p, tc).total_bs };
    });
    return filas.sort(function (a, b) { return a.est - b.est || a.margen_dias - b.margen_dias; });
  }

  function planPresupuesto(al, presupuesto_bs) {
    var acum = 0;
    return al.filter(function (a) { return a.cantidad_sugerida > 0; }).map(function (a) {
      acum += a.costo_bs;
      var o = {}; for (var k in a) o[k] = a[k];
      o.acumulado_bs = acum; o.alcanza = acum <= presupuesto_bs; return o;
    });
  }

  function compararProveedores(datos, repId, tc) {
    var r = rep(datos, repId);
    return datos.proveedores.map(function (p) {
      var c = costoPuesto(r, p, tc), o = {}; for (var k in p) o[k] = p[k];
      o.costo = c; return o;
    }).sort(function (a, b) { return a.costo.total_bs - b.costo.total_bs; });
  }

  function pasado(datos, politica) {
    var t = { lo_justo: [41, 18200, 96, 61400], cubrir_60: [9, 31700, 58, 66900], dos_pedidos: [17, 22900, 131, 63100] }[politica];
    return { ventas_perdidas: t[0], capital_promedio_bs: t[1], pedidos: t[2], ganancia_bs: t[3] };
  }

  return { costoPuesto: costoPuesto, pronostico: pronostico, simular: simular, quiebreDolar: quiebreDolar,
    sensibilidad: sensibilidad, alertas: alertas, planPresupuesto: planPresupuesto,
    compararProveedores: compararProveedores, pasado: pasado, ES_STUB: true };
})();
if (typeof module !== "undefined") module.exports = Motor;
