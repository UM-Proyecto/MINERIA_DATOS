// Guía de estudio del portal (docs/GUIA_ESTUDIO_PORTAL.md): calcula CADA cifra que cita la guía, con el mismo motor
// (src/simulador/motor.js) y los mismos datos (data/processed/simulador/datos_app.json) que usa el portal.
// Imprime un JSON {clave: texto ya formateado}. generar_guia.py lo vuelca en la plantilla; ninguna cifra se escribe a mano.
// Uso: node src/guia/hechos.js
"use strict";
const path = require("path");
const RAIZ = path.resolve(__dirname, "../..");
const M = require(path.join(RAIZ, "src/simulador/motor.js"));
const d = require(path.join(RAIZ, "data/processed/simulador/datos_app.json"));

const MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const MC = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const nf = (x, dec = 0) => { const v = Number(x), p = Math.abs(v).toFixed(dec).split("."); return (v < 0 ? "−" : "") + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".") + (p[1] ? "," + p[1] : ""); };
const bs = (x, dec = 0) => "Bs " + nf(x, dec);
const pc = (x, dec = 0) => nf(x * 100, dec) + " %";
const mesL = m => MC[+m.slice(5, 7) - 1] + "-" + m.slice(0, 4);
const fecha = f => `${+f.slice(8, 10)}-${MC[+f.slice(5, 7) - 1]}-${f.slice(0, 4)}`;
const H = {};
const pon = (k, v) => { if (k in H) throw new Error("clave repetida: " + k); H[k] = String(v); };

// ---- datos y dólar
const tc = d.tc.oficial.valor;
pon("generado", fecha(d.generado));
pon("n_repuestos", d.repuestos.length);
const conteo = d.clasificacion.conteo;
pon("n_series_carparts", nf(Object.values(conteo).reduce((s, x) => s + x, 0)));
pon("n_intermitentes_carparts", nf(conteo.intermitente));
pon("n_irregulares_carparts", nf(conteo.irregular));
const meses = d.ventas["REP-0001"].map(x => x[0]);
pon("n_meses", meses.length); pon("mes_ini", mesL(meses[0])); pon("mes_fin", mesL(meses[meses.length - 1]));
pon("tc", nf(tc, 2)); pon("tc_fecha", fecha(d.tc.oficial.fecha));
pon("tc_serie_n", d.tc.serie.length); pon("tc_serie_ini", fecha(d.tc.serie[0][0])); pon("tc_serie_ini_valor", nf(d.tc.serie[0][1], 2));
pon("tc_paralelo", nf(d.tc.paralelo.valor, 2)); pon("tc_paralelo_fecha", fecha(d.tc.paralelo.fecha));
pon("simulaciones", nf(d.parametros.simulaciones)); pon("semilla", d.parametros.semilla);
pon("costo_pedido", bs(d.parametros.costo_pedido_bs)); pon("costo_capital", nf(d.parametros.costo_capital_mensual * 100, 1) + " %");

// ---- repuesto de ejemplo: REP-0022 (el primero de la lista del simulador y el más probable de la predicción)
const ID = "REP-0022", r = d.repuestos.find(x => x.repuesto_id === ID), prov = d.proveedores.find(p => p.proveedor_id === r.proveedor_id);
const nombre = id => d.catalogo.repuestos.find(c => c.repuesto_id === id).nombre;
pon("ej_id", ID); pon("ej_nombre", nombre(ID)); pon("ej_codigo", r.codigo_carparts);
pon("ej_tipo", r.tipo_demanda); pon("ej_clase", r.clase_abc); pon("ej_adi", nf(r.adi, 2)); pon("ej_cv2", nf(r.cv2, 2));
pon("ej_meses_venta", r.meses_con_venta); pon("ej_unidades", r.unidades_totales);
pon("ej_prov", prov.nombre.replace(" (ficticio)", "")); pon("ej_incoterm", prov.incoterm); pon("ej_plazo", prov.plazo_normal_dias);
pon("ej_desvio", prov.desvio_plazo_dias); pon("ej_a_tiempo", prov.pct_entregas_a_tiempo);
pon("ej_usd", nf(r.costo_unitario_usd, 2)); pon("ej_gastos_pct", nf(prov.gastos_pct_cif, 3));
const cp = M.costoPuesto(r, prov, tc);
pon("ej_fabrica_bs", bs(cp.fabrica_bs, 2)); pon("ej_gastos_bs", bs(cp.gastos_bs, 2)); pon("ej_costo_puesto", bs(cp.total_bs, 2)); pon("ej_costo_usd", nf(cp.total_usd, 2));
pon("flete_china_pct", nf(d.proveedores.find(p => p.origen === "China").flete_pct_fob_origen, 1));
// mismo repuesto con un proveedor FOB de China, para mostrar el flete
const pFob = d.proveedores.find(p => p.origen === "China" && p.incoterm === "FOB");
const cpF = M.costoPuesto(r, pFob, tc);
pon("fob_prov", pFob.nombre.replace(" (ficticio)", "")); pon("fob_flete_pct", nf(pFob.flete_pct_aplicado, 1));
pon("fob_fabrica", bs(cpF.fabrica_bs, 2)); pon("fob_flete", bs(cpF.flete_bs, 2)); pon("fob_gastos", bs(cpF.gastos_bs, 2)); pon("fob_total", bs(cpF.total_bs, 2));

// pronóstico SBA, paso a paso sobre la serie real
const serie = d.ventas[ID].map(x => x[1]);
const pr = M.pronostico(d.ventas[ID], r.tipo_demanda);
let z = null, p = null, q = 0;
for (const v of serie) { q++; if (v > 0) { if (z === null) { z = v; p = q; } else { z += 0.1 * (v - z); p += 0.1 * (q - p); } q = 0; } }
pon("sba_z", nf(z, 2)); pon("sba_p", nf(p, 2)); pon("sba_mes", nf(pr.unidades_mes, 2)); pon("sba_dia", nf(pr.unidades_mes / 30, 3));
pon("ej_promedio_simple", nf(serie.reduce((s, x) => s + x, 0) / serie.length, 2));
pon("ej_ultimos12", serie.slice(-12).join(", "));

// política (s, S) y alerta
const al = M.alertas(d, tc), a = al.find(x => x.id === ID);
pon("ej_s", r.punto_pedido_s); pon("ej_S", r.nivel_maximo_S); pon("ej_stock", a.stock); pon("ej_camino", a.en_camino);
pon("ej_posicion", a.stock + a.en_camino);
pon("ej_posicion_vs_s", a.stock + a.en_camino <= r.punto_pedido_s ? "está en el punto de pedido o por debajo: hay que pedir" : "está por encima del punto de pedido: todavía no hace falta pedir");
pon("ej_estado", a.etiqueta); pon("ej_cant_sugerida", a.cantidad_sugerida); pon("ej_costo_sugerido", bs(a.costo_bs, 2));
pon("al_pedir", al.filter(x => x.est === 0).length); pon("al_vigilar", al.filter(x => x.est === 1).length); pon("al_cubierto", al.filter(x => x.est === 2).length);

// Monte Carlo
const sup = {tc_base: tc, tc_90: tc, venta_pct: 0, atraso_dias: 0, precio_sigue_dolar: true};
const S = M.simular(d, ID, r.proveedor_id, sup, {n: d.parametros.simulaciones, semilla: d.parametros.semilla, horizonte_dias: 90});
for (const L of ["A", "B", "C", "D"]) {
  pon(`mc_${L}_cant`, S[L].cantidad); pon(`mc_${L}_puntaje`, S[L].puntaje); pon(`mc_${L}_riesgo`, S[L].riesgo_quiebre);
  pon(`mc_${L}_gan`, bs(S[L].ganancia_media_bs)); pon(`mc_${L}_p10`, bs(S[L].ganancia_p10_bs));
}
pon("mc_mejor", S.mejor);
const Q = M.quiebreDolar(d, ID, r.proveedor_id, sup, {semilla: d.parametros.semilla, horizonte_dias: 90});
pon("mc_quiebre", nf(Q.valor, 2)); pon("mc_quiebre_antes", Q.antes); pon("mc_quiebre_despues", Q.despues);
const SE = M.sensibilidad(d, ID, r.proveedor_id, sup, {semilla: d.parametros.semilla, horizonte_dias: 90});
pon("sens_1", {dolar: "el dólar", venta: "la venta", atraso: "el atraso del proveedor"}[SE[0].supuesto]); pon("sens_1_bs", bs(SE[0].rango_bs));
pon("sens_3_bs", bs(SE[SE.length - 1].rango_bs));

// ---- cotización con tramos: 12 unidades del repuesto más vendido
const T = M.dashboard(d, tc), top = T.repuestos[0];
const c = M.cotizar(d, top.id, 12, tc);
pon("cot_id", top.id); pon("cot_nombre", nombre(top.id)); pon("cot_lista", bs(c.precio_lista_bs, 2)); pon("cot_pct", c.pct_aplicado);
pon("cot_unit", bs(c.precio_unitario_bs, 2)); pon("cot_sub", bs(c.subtotal_bs, 2)); pon("cot_desc", bs(c.descuento_bs, 2)); pon("cot_total", bs(c.total_bs, 2));
pon("tramo1", M.TRAMOS_EJEMPLO[0].desde); pon("tramo1_pct", M.TRAMOS_EJEMPLO[0].pct); pon("tramo2", M.TRAMOS_EJEMPLO[1].desde); pon("tramo2_pct", M.TRAMOS_EJEMPLO[1].pct);

// ---- tablero
pon("db_total", bs(T.total.monto_bs)); pon("db_unidades", nf(T.total.unidades));
pon("db_ult12", bs(T.ult12_bs)); pon("db_prev12", bs(T.prev12_bs)); pon("db_var12", ((T.ult12_bs >= T.prev12_bs) ? "+" : "−") + nf(Math.abs(T.ult12_bs - T.prev12_bs) / T.prev12_bs * 100) + " %");
pon("db_top_rep", top.id); pon("db_top_rep_u", top.unidades);
pon("db_top_cli", T.clientes[0].nombre.replace(" (ficticio)", "")); pon("db_top_cli_pct", nf(T.clientes[0].pct_total, 1) + " %"); pon("db_top5", nf(T.top5_pct) + " %");
const dm = T.demanda_mes, pico = dm.reduce((b, x, i) => x.unidades > dm[b].unidades ? i : b, 0);
pon("db_pico_mes", mesL(dm[pico].mes)); pon("db_pico_u", dm[pico].unidades); pon("db_prom_mes", nf(T.total.unidades / dm.length, 1));
const pm = i => dm.slice(i - 11, i + 1).reduce((s, x) => s + x.unidades, 0) / 12;
pon("db_pm_ult", nf(pm(dm.length - 1), 1)); pon("db_pm_prev", nf(pm(dm.length - 13), 1));
pon("db_ult12_u", dm.slice(-12).reduce((s, x) => s + x.unidades, 0));
pon("db_ult_mes", mesL(T.ultimo_mes));
const du = pm(dm.length - 1) - pm(dm.length - 13), dbv = T.ult12_bs - T.prev12_bs;
pon("db_dir_u", Math.abs(du) / pm(dm.length - 13) < 0.05 ? "se mantiene" : du > 0 ? "sube" : "baja");
pon("db_dir_bs", dbv >= 0 ? "sube" : "baja");
pon("db_mezcla", (du < 0) === (dbv >= 0) ? (dbv >= 0 ? ", porque se vendieron menos unidades pero más caras" : ", porque se vendieron más unidades pero más baratas") : "");

// ---- rotación y ABC por dinero
const R = M.rotacion(d, tc), A_ = R.repuestos.filter(f => f.clase_abc === "A");
pon("rt_A", A_.length); pon("rt_A_pct", nf(A_.reduce((s, f) => s + f.valor12_bs, 0) / R.valor12_total_bs * 100) + " %");
pon("rt_total12", bs(R.valor12_total_bs)); pon("rt_acum", R.acumulacion); pon("rt_acum_bs", bs(R.valor_acumulado_bs)); pon("rt_baja", R.baja_rotacion);
pon("rt_A_alta", R.matriz.A.alta); pon("rt_C_baja", R.matriz.C.baja);
const r1 = R.repuestos[0], r2 = R.repuestos[1];
pon("rt_1_id", r1.id); pon("rt_1_bs", bs(r1.valor12_bs)); pon("rt_1_pct", nf(r1.pct_acumulado, 1) + " %");
pon("rt_2_id", r2.id); pon("rt_2_bs", bs(r2.valor12_bs)); pon("rt_2_pct", nf(r2.pct_acumulado, 1) + " %");
const rej = R.repuestos.find(f => f.id === ID);
pon("rt_ej_u12", rej.u12); pon("rt_ej_cob", nf(rej.cobertura_meses, 1)); pon("rt_ej_rot", nf(rej.rotacion_anual, 1));

// ---- temporadas
const TM = M.temporadas(d).total;
pon("tm_pico", MES[TM.mes_pico - 1]); pon("tm_pico_i", nf(TM.indice[TM.mes_pico - 1], 1));
pon("tm_flojo", MES[TM.mes_flojo - 1]); pon("tm_flojo_i", nf(TM.indice[TM.mes_flojo - 1], 1));
pon("tm_media", nf(TM.media, 1)); pon("tm_pico_prom", nf(TM.promedio_mes[TM.mes_pico - 1], 1));
pon("tm_fuertes", TM.meses_fuertes.map(m => MES[m - 1]).join(", ")); pon("tm_n_fuertes", TM.meses_fuertes.length);

// ---- clientes
const C = M.tableroClientes(d, tc);
pon("cli_n", d.clientes.lista.length); pon("cli_tipo_top", C.por_tipo[0].tipo); pon("cli_tipo_top_pct", nf(C.por_tipo[0].monto_bs / C.total.monto_bs * 100) + " %");

// ---- predicción
const P = d.prediccion, V = P.validacion, Mo = V.modelo, MY = V.modelo_corte_youden, Re = V.regla_mes_anterior;
pon("pr_entreno", nf(V.entreno.casos)); pon("pr_entreno_desde", mesL(V.entreno.desde)); pon("pr_entreno_hasta", mesL(V.entreno.hasta));
pon("pr_prueba", nf(V.prueba.casos)); pon("pr_prueba_desde", mesL(V.prueba.desde)); pon("pr_prueba_hasta", mesL(V.prueba.hasta)); pon("pr_prueba_pos", V.prueba.positivos);
pon("pr_auc", nf(Mo.auc, 2)); pon("pr_auc_regla", nf(Re.auc, 2)); pon("pr_brier", nf(Mo.brier, 3)); pon("pr_brier_base", nf(V.brier_tasa_base, 3)); pon("pr_brier_regla", nf(Re.brier, 3));
pon("pr_tasa_base", pc(V.tasa_base_entreno)); pon("pr_youden", pc(P.corte_youden)); pon("pr_lambda", nf(P.lambda_l2));
pon("pr_exact50", pc(Mo.exactitud)); pon("pr_sens50", pc(Mo.sensibilidad)); pon("pr_esp50", pc(Mo.especificidad));
pon("pr_sensY", pc(MY.sensibilidad)); pon("pr_espY", pc(MY.especificidad)); pon("pr_exactY", pc(MY.exactitud));
pon("pr_vp", Mo.vp); pon("pr_fp", Mo.fp); pon("pr_fn", Mo.fn); pon("pr_vn", Mo.vn);
pon("pr_mes", MES[+P.mes_predicho.slice(5, 7) - 1] + " de " + P.mes_predicho.slice(0, 4));
const niv = k => P.predicciones.filter(x => x.nivel === k).length;
pon("pr_alta", niv("alta")); pon("pr_media", niv("media")); pon("pr_baja", niv("baja"));
// el cálculo de la probabilidad de REP-0022, término por término
const pe = P.predicciones.find(x => x.repuesto_id === ID), co = P.coeficientes;
let zz = co.constante;
P.variables.forEach((v, i) => {
  const x = pe.variables[v.clave], s = (x - co.medias[i]) / co.desvios[i], b = co.estandarizados.find(e => e.clave === v.clave).coef;
  zz += b * s;
  pon(`pr_x${i}`, nf(x, v.clave === "frecuencia_12m" ? 2 : 0)); pon(`pr_s${i}`, nf(s, 2)); pon(`pr_b${i}`, nf(b, 3));
});
pon("pr_const", nf(co.constante, 3)); pon("pr_z", nf(zz, 2)); pon("pr_p_calc", pc(1 / (1 + Math.exp(-zz)), 1)); pon("pr_p", pc(pe.probabilidad, 1));
if (Math.abs(1 / (1 + Math.exp(-zz)) - pe.probabilidad) > 0.001) throw new Error("La probabilidad recalculada no coincide con la del modelo");
const fuerte = co.estandarizados.slice().sort((x, y) => Math.abs(y.coef) - Math.abs(x.coef))[0];
pon("pr_var_fuerte", P.variables.find(v => v.clave === fuerte.clave).nombre.toLowerCase());

process.stdout.write(JSON.stringify(H, null, 1));
