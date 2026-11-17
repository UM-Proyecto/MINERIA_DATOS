/*
 * Cotización imprimible y correo simulado de MULTIPARTES (SCRUM-83).
 *
 * Lo usan la tienda (src/tienda/plantilla_tienda.html) y el área de la empresa (src/simulador/plantilla_app.html):
 * los dos generadores lo incrustan justo después del motor. No calcula precios: recibe la cotización tal como la
 * guardó el servidor (o la fila de Cotizaciones guardadas) y solo la presenta.
 *
 *   CotizacionDoc.documento(q, op)  -> HTML completo de la cotización, listo para imprimir o guardar en PDF.
 *   CotizacionDoc.correo(q, op)     -> {para, asunto, cuerpo, adjunto} del correo que acompaña a la cotización.
 *   CotizacionDoc.abrir(html)       -> abre el documento en una pestaña nueva (desde un clic del usuario).
 *   CotizacionDoc.correoValido(s)   -> true si la dirección tiene forma de correo.
 *
 * q: numero, fecha (ISO), cantidad, precio_lista_bs, pct_aplicado, total_bs, tc, tc_fecha, repuesto_id, y si las hay,
 *    correo, cliente_nombre, repuesto_nombre, precio_unitario_bs, subtotal_bs y descuento_bs (si faltan, se derivan).
 * op: logo (data URI del logotipo blanco sobre verde), tramos (los de Motor.TRAMOS_EJEMPLO) y validez_dias (7).
 *
 * El envío del correo es SIMULADO: el servidor solo registra la dirección y la hora; no se manda nada.
 */
var CotizacionDoc = (function () {
  "use strict";
  var MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  var NOTA = "Ventas: base pública carparts. Clientes, proveedores, precios y stock: datos de demostración.";
  var DATASET = "https://robjhyndman.com/expsmooth/";

  function esc(s) { return String(s === null || s === undefined ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function nf(x, d) {
    var v = Number(x), neg = v < 0, p = Math.abs(v).toFixed(d === undefined ? 2 : d).split(".");
    return (neg ? "−" : "") + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".") + (p[1] ? "," + p[1] : "");
  }
  function bs(x) { return "Bs " + nf(x, 2); }
  function fecha(iso) { var d = new Date(String(iso).length <= 10 ? iso + "T12:00:00" : iso); return d.getDate() + "-" + MES[d.getMonth()] + "-" + d.getFullYear(); }
  function sumarDias(iso, n) { var d = new Date(String(iso).length <= 10 ? iso + "T12:00:00" : iso); d.setDate(d.getDate() + n); return d.toISOString(); }
  function numeroTxt(n) { return String(n).padStart(6, "0"); }
  function correoValido(s) { return typeof s === "string" && s.length <= 120 && /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s.trim()); }

  // Completa los importes que faltan con la misma aritmética del motor (precio por unidad = total / cantidad).
  function completar(q) {
    var x = {}; for (var k in q) x[k] = q[k];
    x.subtotal_bs = x.subtotal_bs !== undefined ? x.subtotal_bs : Math.round(x.precio_lista_bs * x.cantidad * 100) / 100;
    x.descuento_bs = x.descuento_bs !== undefined ? x.descuento_bs : Math.round((x.subtotal_bs - x.total_bs) * 100) / 100;
    x.precio_unitario_bs = x.precio_unitario_bs !== undefined ? x.precio_unitario_bs : Math.round(x.total_bs / x.cantidad * 100) / 100;
    return x;
  }

  function tramosTxt(tramos, pct) {
    var t = (tramos || []).slice().sort(function (a, b) { return a.desde - b.desde; }), f = [{desde: 1, hasta: t.length ? t[0].desde - 1 : null, pct: 0}];
    t.forEach(function (x, i) { f.push({desde: x.desde, hasta: i + 1 < t.length ? t[i + 1].desde - 1 : null, pct: x.pct}); });
    return f.map(function (x) {
      return '<tr' + (x.pct === pct ? ' class="on"' : "") + "><td>" + (x.hasta === null ? x.desde + " o más" : x.desde + " a " + x.hasta) + " unidades</td><td>" +
        (x.pct ? x.pct + " % de descuento" : "precio de lista") + "</td></tr>";
    }).join("");
  }

  function correo(q, op) {
    q = completar(q); op = op || {};
    var vence = fecha(sumarDias(q.fecha, op.validez_dias || 7)), nom = q.repuesto_nombre || q.repuesto_id;
    return {
      para: q.correo || "",
      asunto: "Cotización N° " + numeroTxt(q.numero) + " de MULTIPARTES: " + nom,
      cuerpo: "Estimado cliente:\n\n" +
        "Le enviamos la cotización N° " + numeroTxt(q.numero) + ", emitida el " + fecha(q.fecha) + ":\n\n" +
        "  " + nom + " (" + q.repuesto_id + ")\n" +
        "  Cantidad: " + nf(q.cantidad, 0) + " unidades\n" +
        "  Precio por unidad: " + bs(q.precio_unitario_bs) + (q.pct_aplicado ? " (incluye " + nf(q.pct_aplicado, Number.isInteger(q.pct_aplicado) ? 0 : 2) + " % de descuento por cantidad)" : "") + "\n" +
        "  Total: " + bs(q.total_bs) + "\n\n" +
        "Los precios están en bolivianos con el dólar oficial del Banco Central de Bolivia de " + nf(q.tc, 2) + " Bs (" + fecha(q.tc_fecha) + "). " +
        "La cotización es válida hasta el " + vence + ". Para hacer el pedido, presente este número en cualquiera de nuestras sucursales.\n\n" +
        "Adjuntamos la cotización en PDF.\n\nAtentamente,\nMULTIPARTES · Santa Cruz de la Sierra",
      adjunto: "Cotizacion_MULTIPARTES_" + numeroTxt(q.numero) + ".pdf",
    };
  }

  function documento(q, op) {
    q = completar(q); op = op || {};
    var vence = fecha(sumarDias(q.fecha, op.validez_dias || 7)), nom = q.repuesto_nombre || q.repuesto_id;
    var pctTxt = q.pct_aplicado ? nf(q.pct_aplicado, Number.isInteger(q.pct_aplicado) ? 0 : 2) + " %" : "—";
    return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
      '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap">' +
      "<title>Cotización N° " + numeroTxt(q.numero) + " · MULTIPARTES</title><style>" +
      "@page{size:A4;margin:14mm}" +
      "*{box-sizing:border-box}body{margin:0;background:#eef0ed;color:#161922;font:13px/1.5 Poppins,system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;font-variant-numeric:tabular-nums}" +
      ".hoja{max-width:794px;margin:24px auto;background:#fff;box-shadow:0 2px 18px rgba(0,0,0,.12)}" +
      ".proto{background:#000;color:#f1f3f5;font-size:11px;padding:6px 28px}.proto b{color:#ffd166}" +
      ".cab{background:#016726;color:#fff;display:flex;justify-content:space-between;align-items:center;gap:16px;padding:18px 28px}" +
      ".cab img{height:64px;width:auto;display:block}.cab .n{text-align:right}.cab .n b{display:block;font-size:20px;letter-spacing:.02em}.cab .n span{font-size:12px;opacity:.9}" +
      ".cuerpo{padding:22px 28px 26px}" +
      ".dos{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px}.dos h2{font-size:10.5px;letter-spacing:1.2px;text-transform:uppercase;color:#5f6670;margin:0 0 4px}" +
      ".dos p{margin:0}" +
      "table{width:100%;border-collapse:collapse}th{font-size:11px;text-align:left;color:#5f6670;font-weight:600;border-bottom:2px solid #016726;padding:6px 8px}" +
      "td{padding:8px;border-bottom:1px solid #e3e6e2;vertical-align:top}td.n,th.n{text-align:right;white-space:nowrap}td small{display:block;color:#5f6670;font-size:11px}" +
      ".tot{margin-left:auto;width:360px;margin-top:10px}.tot td{border:0;padding:3px 8px}.tot tr.t td{border-top:2px solid #016726;font-weight:700;font-size:16px;padding-top:8px}" +
      ".tc{margin-top:14px;font-size:12px;color:#3f4650}" +
      ".tr{width:auto;margin-top:6px}.tr td{border:0;padding:2px 14px 2px 0;font-size:12px}.tr tr.on td{font-weight:700;color:#016a31}" +
      "h3{font-size:12px;margin:18px 0 0}" +
      ".cond{margin-top:18px;border-top:1px solid #e3e6e2;padding-top:12px;font-size:11.5px;color:#3f4650}.cond p{margin:0 0 4px}" +
      ".pie{margin-top:12px;font-size:11px;color:#5f6670}.pie a{color:inherit}" +
      ".acc{max-width:794px;margin:0 auto 24px;text-align:center}.acc button{font:inherit;font-weight:600;background:#01863e;color:#fff;border:0;border-radius:8px;padding:10px 18px;cursor:pointer}" +
      "@media (max-width:600px){.cab{flex-direction:column;align-items:flex-start}.cab .n{text-align:left}.dos{grid-template-columns:1fr}.tot{width:100%}.cuerpo,.cab,.proto{padding-left:16px;padding-right:16px}.hoja{margin:0}" +
      ".items th:nth-child(3),.items td:nth-child(3),.items th:nth-child(4),.items td:nth-child(4){display:none}.items th,.items td{padding:6px 4px;font-size:12px}.items small{white-space:nowrap}}" +
      "@media print{body{background:#fff}.hoja{box-shadow:none;margin:0;max-width:none}.acc{display:none}.cab,.proto{-webkit-print-color-adjust:exact;print-color-adjust:exact}}" +
      "</style></head><body><div class=\"hoja\">" +
      '<div class="proto"><b>PROTOTIPO ACADÉMICO</b> (Minería de Datos, Univalle). No es una cotización oficial de MULTIPARTES.</div>' +
      '<div class="cab">' + (op.logo ? '<img src="' + esc(op.logo) + '" alt="MULTIPARTES Santa Cruz">' : "<b>MULTIPARTES</b>") +
      '<div class="n"><b>COTIZACIÓN N° ' + numeroTxt(q.numero) + "</b><span>Emitida el " + fecha(q.fecha) + " · válida hasta el " + vence + "</span></div></div>" +
      '<div class="cuerpo"><div class="dos"><div><h2>Cliente</h2><p>' + (q.cliente_nombre ? esc(q.cliente_nombre) : "Cliente de la tienda en línea") + "</p>" +
      (q.correo ? "<p>" + esc(q.correo) + "</p>" : "") + "</div>" +
      "<div><h2>Emitida por</h2><p>MULTIPARTES · Santa Cruz de la Sierra</p><p>Tienda en línea</p></div></div>" +
      '<div style="overflow-x:auto"><table class="items"><thead><tr><th>Repuesto</th><th class="n">Cantidad</th><th class="n">Precio de lista</th><th class="n">Descuento</th><th class="n">Precio por unidad</th><th class="n">Importe</th></tr></thead><tbody>' +
      "<tr><td><b>" + esc(nom) + "</b><small>Código " + esc(q.repuesto_id) + "</small></td><td class=\"n\">" + nf(q.cantidad, 0) + '</td><td class="n">' + bs(q.precio_lista_bs) +
      '</td><td class="n">' + pctTxt + '</td><td class="n">' + bs(q.precio_unitario_bs) + '</td><td class="n">' + bs(q.total_bs) + "</td></tr></tbody></table></div>" +
      '<table class="tot"><tr><td>Subtotal a precio de lista</td><td class="n">' + bs(q.subtotal_bs) + "</td></tr>" +
      '<tr><td>Descuento por cantidad</td><td class="n">' + (q.descuento_bs ? "− " + bs(q.descuento_bs) : bs(0)) + "</td></tr>" +
      '<tr class="t"><td>Total</td><td class="n">' + bs(q.total_bs) + "</td></tr></table>" +
      '<p class="tc">Precios en bolivianos con el dólar oficial del Banco Central de Bolivia: <b>' + nf(q.tc, 2) + " Bs por dólar</b>, vigente el " + fecha(q.tc_fecha) + ".</p>" +
      "<h3>Descuento por cantidad</h3><table class=\"tr\">" + tramosTxt(op.tramos, q.pct_aplicado) + "</table>" +
      '<div class="cond"><p><b>Validez:</b> esta cotización vale hasta el ' + vence + ". Pasada esa fecha, el precio se recalcula con el dólar oficial del día.</p>" +
      "<p><b>Disponibilidad:</b> sujeta al stock al momento del pedido; lo que falte llega en el plazo del proveedor.</p>" +
      "<p><b>Cómo pedir:</b> presente el número de cotización en cualquiera de nuestras sucursales.</p></div>" +
      '<p class="pie">' + NOTA + ' Base de datos de ventas: <a href="' + DATASET + '">' + DATASET + "</a>.</p>" +
      '</div></div><div class="acc"><button type="button" onclick="window.print()">Imprimir o guardar en PDF</button></div></body></html>';
  }

  function abrir(html) {
    var url = URL.createObjectURL(new Blob([html], {type: "text/html"}));
    var w = window.open(url, "_blank", "noopener");
    setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
    return !!w;
  }

  return {documento: documento, correo: correo, abrir: abrir, correoValido: correoValido, NOTA: NOTA, DATASET: DATASET, _completar: completar};
})();
if (typeof module !== "undefined" && module.exports) module.exports = CotizacionDoc;
