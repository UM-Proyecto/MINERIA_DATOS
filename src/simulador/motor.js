/*
 * Motor del simulador de compras de MULTIPARTES (SCRUM-53, 56 a 63, 66, 67, 69 y 70).
 *
 * Un solo motor para la app y para las pruebas: no toca el DOM y corre igual en el navegador y en Node.
 * motor_ref.py repite cada cálculo en Python, paso por paso, para la prueba de equivalencia. Por eso:
 *  - el azar sale de mulberry32 (aritmética uint32, igual en los dos lenguajes);
 *  - la normal se arma sumando 12 sorteos uniformes (Irwin-Hall), sin logaritmos ni cosenos;
 *  - la exponencial del dólar lognormal se calcula con una serie propia (expSerie), no con Math.exp,
 *    porque Math.exp de V8 y math.exp de Python pueden diferir en el último bit;
 *  - las sumas se hacen siempre en el mismo orden y los redondeos son «mitad hacia arriba».
 * Si cambias una fórmula aquí, cámbiala igual en motor_ref.py: la prueba lo exige.
 *
 * Los supuestos marcados SINTÉTICO están explicados en docs/simulador/MOTOR.md.
 */
"use strict";

var Motor = (function () {
  // Stock de seguridad: los mismos z por clase que usa la regla (s, S) de SCRUM-55.
  var Z_CLASE = { A: 1.65, B: 1.28, C: 0.84 };
  var ALFA_SBA = 0.1;
  var ALTERNATIVAS = ["A", "B", "C", "D"];
  var ORDEN_CLASE = { A: 0, B: 1, C: 2 };
  var ETIQUETAS = ["Pedir ya", "Vigilar", "Cubierto", "Sin datos"];
  var EPS = 1e-9;
  // Atraso extra cuando el proveedor no cumple (SINTÉTICO): uniforme entre 5 y 20 días.
  var ATRASO_EXTRA_MIN = 5;
  var ATRASO_EXTRA_RANGO = 15;
  // Dólar oficial fijo antes de que el BCB publicara el TCO diario.
  var TC_FIJO = 6.96;
  var INICIO_TCO = "2026-06-27";
  // Rango de búsqueda del dólar de quiebre: 9,00 a 15,00 Bs en pasos de 0,05 (121 puntos).
  var QUIEBRE_PASOS = 120;
  var N_ANALISIS = 400;

  function num(x) { return Number(x); }

  // ---------------------------------------------------------------- utilidades numéricas

  function mulberry32(semilla) {
    var a = semilla >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = Math.imul(a ^ (a >>> 15), a | 1);
      t = (t + Math.imul(t ^ (t >>> 7), t | 61)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Normal estándar aproximada: suma de 12 uniformes menos 6 (media 0, desvío 1, cola cortada en ±6).
  function normalIH(r) {
    var s = 0;
    for (var i = 0; i < 12; i++) s += r();
    return s - 6;
  }

  // e^x con serie de Taylor sobre x/16 y cuatro cuadrados. Exacta a 1e-15 para |x| < 2.
  function expSerie(x) {
    var y = x / 16;
    var s = 1;
    for (var k = 20; k >= 1; k--) s = 1 + s * y / k;
    s = s * s; s = s * s; s = s * s; s = s * s;
    return s;
  }

  function redondear(x, dec) {
    var f = Math.pow(10, dec);
    return Math.floor(x * f + 0.5 + EPS) / f;
  }

  function techo(x) { return Math.ceil(x - EPS); }

  function media(v) {
    if (!v.length) return 0;
    var s = 0;
    for (var i = 0; i < v.length; i++) s += v[i];
    return s / v.length;
  }

  function desvio(v) {
    if (!v.length) return 0;
    var m = media(v), s = 0;
    for (var i = 0; i < v.length; i++) s += (v[i] - m) * (v[i] - m);
    return Math.sqrt(s / v.length);
  }

  // Desvío de los cambios diarios relativos del TCO real (sin logaritmos, ver encabezado).
  function volatilidadDiaria(serie) {
    var c = [];
    for (var i = 1; i < serie.length; i++) c.push(num(serie[i][1]) / num(serie[i - 1][1]) - 1);
    return desvio(c);
  }

  // ---------------------------------------------------------------- búsquedas

  function buscarRepuesto(datos, id) {
    for (var i = 0; i < datos.repuestos.length; i++) if (datos.repuestos[i].repuesto_id === id) return datos.repuestos[i];
    throw new Error("Repuesto desconocido: " + id);
  }

  function buscarProveedor(datos, id) {
    for (var i = 0; i < datos.proveedores.length; i++) if (datos.proveedores[i].proveedor_id === id) return datos.proveedores[i];
    throw new Error("Proveedor desconocido: " + id);
  }

  function valores(ventas) {
    var v = [];
    for (var i = 0; i < ventas.length; i++) v.push(Array.isArray(ventas[i]) ? num(ventas[i][1]) : num(ventas[i]));
    return v;
  }

  function ultimos(v, n) { return v.length > n ? v.slice(v.length - n) : v.slice(); }

  // ---------------------------------------------------------------- costo puesto

  // Costo por unidad puesto en Santa Cruz. Igual que SCRUM-55: el costo puesto en USD se redondea a centavos
  // y recién después se pasa a bolivianos; así reproduce costo_puesto_bs de repuestos.csv.
  function costoPuesto(rep, prov, tc) {
    var usd = num(rep.costo_unitario_usd);
    tc = num(tc);
    var incluido = prov.incoterm === "CIF";
    var fp = incluido ? 0 : num(prov.flete_pct_aplicado);
    var g = num(prov.gastos_pct_cif);
    var totalUsd = redondear(usd * ((1 + fp / 100) * (1 + g / 100)), 2);
    var total = redondear(totalUsd * tc, 2);
    var fabrica = redondear(usd * tc, 2);
    var flete = redondear(usd * fp / 100 * tc, 2);
    return {
      fabrica_bs: fabrica, flete_bs: flete, gastos_bs: redondear(total - fabrica - flete, 2), total_bs: total,
      total_usd: totalUsd, incoterm: prov.incoterm, flete_incluido: incluido
    };
  }

  // ---------------------------------------------------------------- pronóstico

  function pronostico(ventas, tipo) {
    var v = valores(ventas);
    if (tipo === undefined || tipo === null) {
      var conVenta = 0;
      for (var i = 0; i < v.length; i++) if (v[i] > 0) conVenta++;
      tipo = conVenta > 0 && v.length / conVenta <= 1.32 ? "suave" : "intermitente";
    }
    if (tipo === "intermitente" || tipo === "irregular") {
      var z = null, p = null, q = 0;
      for (var j = 0; j < v.length; j++) {
        q += 1;
        if (v[j] > 0) {
          if (z === null) { z = v[j]; p = q; }
          else { z = z + ALFA_SBA * (v[j] - z); p = p + ALFA_SBA * (q - p); }
          q = 0;
        }
      }
      return { metodo: "SBA", unidades_mes: z === null ? 0 : (1 - ALFA_SBA / 2) * z / p };
    }
    return { metodo: "media", unidades_mes: media(ultimos(v, 12)) };
  }

  // Cantidad «lo justo»: venta esperada en el plazo + reserva − (stock + en camino), mínimo 0.
  function necesidad(tasaDia, sigmaMes, clase, plazo, posicion) {
    var reserva = Z_CLASE[clase] * sigmaMes * Math.sqrt(plazo / 30);
    return { reserva: reserva, cantidad: Math.max(0, techo(tasaDia * plazo + reserva - posicion)) };
  }

  // ---------------------------------------------------------------- simulación de 90 días

  function plazoSorteado(r, prov, atraso) {
    var z = normalIH(r);
    var u = r();
    var extra = ATRASO_EXTRA_MIN + ATRASO_EXTRA_RANGO * r();
    var dias = num(prov.plazo_normal_dias) + num(atraso) + num(prov.desvio_plazo_dias) * z;
    if (u < (100 - num(prov.pct_entregas_a_tiempo)) / 100) dias += extra;
    return Math.max(1, Math.floor(dias + 0.5));
  }

  function simular(datos, repId, provId, sup, opc) {
    opc = opc || {};
    var par = datos.parametros;
    var n = opc.n !== undefined ? opc.n : num(par.simulaciones);
    var semilla = opc.semilla !== undefined ? opc.semilla : num(par.semilla);
    var H = opc.horizonte_dias !== undefined ? opc.horizonte_dias : 90;
    var rep = buscarRepuesto(datos, repId);
    var prov = buscarProveedor(datos, provId || rep.proveedor_id);
    var tcb = num(sup.tc_base), tc90 = num(sup.tc_90);
    var f = 1 + num(sup.venta_pct) / 100;
    var atraso = num(sup.atraso_dias);
    var sigue = !!sup.precio_sigue_dolar;
    var cped = num(par.costo_pedido_bs), tasaCap = num(par.costo_capital_mensual);

    var hist = valores(datos.ventas[repId]);
    var ult = ultimos(hist, 24);
    var pr = pronostico(datos.ventas[repId], rep.tipo_demanda);
    var tasa = pr.unidades_mes * f / 30;
    var sigma = desvio(ult) * f;
    var plazoEsp = num(prov.plazo_normal_dias) + atraso;
    var stock = num(rep.stock_al_2026_11_10), camino = num(rep.en_transito_al_2026_11_10);
    var pos = stock + camino;
    var nec = necesidad(tasa, sigma, rep.clase_abc, plazoEsp, pos);
    // El simulador evalúa un pedido que se hace hoy: «lo justo» es al menos 1 unidad (ver MOTOR.md, decisiones).
    var qA = Math.max(1, nec.cantidad);
    var qB = qA + techo(30 * tasa);
    var qC = qA + techo(60 * tasa);
    var cant = { A: [qA, 0], B: [qB, 0], C: [qC, 0], D: [Math.floor((qC + 1) / 2), qC - Math.floor((qC + 1) / 2)] };
    var cp = costoPuesto(rep, prov, tcb);
    var cu = cp.total_usd;
    var precio = num(rep.precio_venta_bs);
    var diaCamino = Math.floor(num(rep.plazo_normal_dias) / 2);
    var s90 = volatilidadDiaria(datos.tc.serie) * Math.sqrt(90);
    var nMeses = Math.ceil(H / 30);

    var acum = {};
    for (var a = 0; a < 4; a++) acum[ALTERNATIVAS[a]] = { gan: [], sumGan: 0, perd: 0, quiebres: 0, cap: 0, gana: 0 };
    var r = mulberry32(semilla);
    var meses = [];
    for (var i = 0; i < n; i++) {
      // Sorteos en orden fijo: no dependen de los supuestos, así cada futuro es el mismo al mover el dólar.
      for (var m = 0; m < nMeses; m++) meses[m] = ult[Math.floor(r() * ult.length)] * f;
      var zd = normalIH(r);
      var p1 = plazoSorteado(r, prov, atraso);
      var p2 = plazoSorteado(r, prov, atraso);
      var tcFin = tc90 * expSerie(s90 * zd - s90 * s90 / 2);
      var tc30 = tcb + (tcFin - tcb) * 30 / H;
      var mejorGan = 0, mejorAlt = -1;
      for (a = 0; a < 4; a++) {
        var L = ALTERNATIVAS[a];
        var q1 = cant[L][0], q2 = cant[L][1];
        var c1 = cu * tcb, c2 = cu * tc30;
        var viejo = stock, nuevo = 0, vendNuevo = 0, perd = 0, ingreso = 0, capSum = 0;
        for (var d = 0; d < H; d++) {
          if (d === diaCamino) viejo += camino;
          if (d === p1) nuevo += q1;
          if (q2 > 0 && d === 30 + p2) nuevo += q2;
          var mi = Math.floor(d / 30);
          if (mi > nMeses - 1) mi = nMeses - 1;
          var dem = meses[mi] / 30;
          var vv = Math.min(viejo, dem);
          viejo -= vv;
          var resto = dem - vv;
          var vn = Math.min(nuevo, resto);
          nuevo -= vn;
          vendNuevo += vn;
          resto -= vn;
          perd += resto;
          var precioDia = sigue ? precio * (tcb + (tcFin - tcb) * d / H) / tcb : precio;
          ingreso += (vv + vn) * precioDia;
          var pagado2 = q2 > 0 && d >= 30;
          var cap;
          if (vendNuevo <= q1) cap = (q1 - vendNuevo) * c1 + (pagado2 ? q2 * c2 : 0);
          else cap = (q1 + q2 - vendNuevo) * c2;
          capSum += cap;
        }
        var pedidos = (q1 > 0 ? 1 : 0) + (q2 > 0 ? 1 : 0);
        var residual = (q1 + q2 - vendNuevo) * cu * tcFin;
        var gan = ingreso - (q1 * c1 + q2 * c2) - cped * pedidos - capSum * tasaCap / 30 + residual;
        var ac = acum[L];
        ac.gan.push(gan);
        ac.sumGan += gan;
        ac.perd += perd;
        if (perd > 1e-6) ac.quiebres += 1;
        ac.cap += capSum / H;
        if (mejorAlt < 0 || gan > mejorGan) { mejorGan = gan; mejorAlt = a; }
      }
      acum[ALTERNATIVAS[mejorAlt]].gana += 1;
    }

    var puntajes = repartirCien(ALTERNATIVAS.map(function (L) { return acum[L].gana; }), n);
    var res = {};
    var mejor = "A";
    for (a = 0; a < 4; a++) {
      L = ALTERNATIVAS[a];
      ac = acum[L];
      var q = cant[L][0] + cant[L][1];
      var nped = (cant[L][0] > 0 ? 1 : 0) + (cant[L][1] > 0 ? 1 : 0);
      var orden = ac.gan.slice().sort(function (x, y) { return x - y; });
      var capital = n ? ac.cap / n : 0;
      res[L] = {
        cantidad: q, cantidad_hoy: cant[L][0], cantidad_30_dias: cant[L][1], pedidos: nped,
        costo: {
          fabrica_bs: redondear(cp.fabrica_bs * q, 2), flete_bs: redondear(cp.flete_bs * q, 2),
          gastos_bs: redondear(cp.gastos_bs * q, 2), total_bs: redondear(cp.total_bs * q, 2),
          pedidos_bs: cped * nped, flete_incluido: cp.flete_incluido
        },
        margen_dias: tasa > 0 ? redondear((pos + q - tasa * plazoEsp) / tasa, 0) : null,
        riesgo_quiebre: n ? redondear(100 * ac.quiebres / n, 0) : 0,
        unidades_perdidas: n ? ac.perd / n : 0,
        capital_inmovilizado_bs: capital,
        dias_venta_capital: tasa > 0 && cu > 0 ? redondear(capital / (tasa * cu * tcb), 0) : null,
        ganancia_media_bs: n ? ac.sumGan / n : 0,
        ganancia_p10_bs: n ? orden[Math.floor(0.1 * (n - 1))] : 0,
        futuros_ganados: ac.gana,
        puntaje: puntajes[a]
      };
      if (ac.gana > acum[mejor].gana) mejor = L;
    }
    res.mejor = mejor;
    res.info = {
      metodo: pr.metodo, unidades_mes: pr.unidades_mes, venta_dia: tasa, plazo_esperado: plazoEsp,
      reserva: nec.reserva, stock: stock, en_camino: camino, costo_unitario_bs: cp.total_bs,
      precio_bs: precio, volatilidad_90: s90, n: n, semilla: semilla
    };
    return res;
  }

  // Reparte 100 puntos según los futuros ganados (resto mayor), para que la suma dé siempre 100.
  function repartirCien(cuentas, n) {
    if (!n) return cuentas.map(function () { return 0; });
    var crudo = cuentas.map(function (c) { return 100 * c / n; });
    var base = crudo.map(function (x) { return Math.floor(x + EPS); });
    var falta = 100 - base.reduce(function (s, x) { return s + x; }, 0);
    var idx = crudo.map(function (x, i) { return i; });
    idx.sort(function (i, j) { var di = crudo[i] - base[i], dj = crudo[j] - base[j]; return di !== dj ? dj - di : i - j; });
    for (var k = 0; k < falta && k < idx.length; k++) base[idx[k]] += 1;
    return base;
  }

  function conSupuesto(sup, clave, valor) {
    var s = {};
    for (var k in sup) if (Object.prototype.hasOwnProperty.call(sup, k)) s[k] = sup[k];
    s[clave] = valor;
    return s;
  }

  function opcAnalisis(opc) {
    opc = opc || {};
    return { n: opc.n !== undefined ? opc.n : N_ANALISIS, semilla: opc.semilla, horizonte_dias: opc.horizonte_dias };
  }

  // ---------------------------------------------------------------- dólar de quiebre y sensibilidad

  function quiebreDolar(datos, repId, provId, sup, opc) {
    var o = opcAnalisis(opc);
    var memo = {};
    function mejorEn(k) {
      if (memo[k] === undefined) memo[k] = simular(datos, repId, provId, conSupuesto(sup, "tc_90", (900 + 5 * k) / 100), o).mejor;
      return memo[k];
    }
    var antes = mejorEn(0), alFinal = mejorEn(QUIEBRE_PASOS);
    if (antes === alFinal) return null;
    var lo = 0, hi = QUIEBRE_PASOS, despues = alFinal;
    while (hi - lo > 1) {
      var mid = Math.floor((lo + hi) / 2);
      var m = mejorEn(mid);
      if (m === antes) lo = mid;
      else { hi = mid; despues = m; }
    }
    return { valor: (900 + 5 * hi) / 100, antes: antes, despues: despues };
  }

  function sensibilidad(datos, repId, provId, sup, opc) {
    var o = opcAnalisis(opc);
    var alt = simular(datos, repId, provId, sup, o).mejor;
    var casos = [["dolar", "tc_90", 9, 15], ["venta", "venta_pct", -30, 30], ["atraso", "atraso_dias", 0, 30]];
    var filas = casos.map(function (c, i) {
      var de = simular(datos, repId, provId, conSupuesto(sup, c[1], c[2]), o)[alt].ganancia_media_bs;
      var a = simular(datos, repId, provId, conSupuesto(sup, c[1], c[3]), o)[alt].ganancia_media_bs;
      return { supuesto: c[0], rango_bs: Math.abs(a - de), de: de, a: a, alternativa: alt, _i: i };
    });
    filas.sort(function (x, y) { return x.rango_bs !== y.rango_bs ? y.rango_bs - x.rango_bs : x._i - y._i; });
    filas.forEach(function (x) { delete x._i; });
    return filas;
  }

  // ---------------------------------------------------------------- alertas y presupuesto

  // Número finito y no negativo, o null. Un dato vacío no se convierte en cero (criterio de HU-09).
  function datoValido(x) {
    if (x === null || x === undefined || (typeof x === "string" && x.trim() === "")) return null;
    var v = Number(x);
    if (!isFinite(v) || v < 0) return null;
    return v;
  }

  // Lógica única de alertas (SCRUM-66 unida con HU-09). Ver motor_ref.alertas para el detalle.
  function alertas(datos, tc) {
    var filas = [];
    for (var i = 0; i < datos.repuestos.length; i++) {
      var rep = datos.repuestos[i];
      var prov = null;
      for (var j = 0; j < datos.proveedores.length; j++) if (datos.proveedores[j].proveedor_id === rep.proveedor_id) { prov = datos.proveedores[j]; break; }
      var ventas = datos.ventas[rep.repuesto_id] || [];
      var stock = datoValido(rep.stock_al_2026_11_10), camino = datoValido(rep.en_transito_al_2026_11_10);
      var s = datoValido(rep.punto_pedido_s), S = datoValido(rep.nivel_maximo_S);
      var plazo = prov ? datoValido(prov.plazo_normal_dias) : null;
      var motivos = [];
      if (stock === null || camino === null) motivos.push("STOCK_FALTANTE");
      if (plazo === null) motivos.push("PLAZO_FALTANTE");
      if (ventas.length === 0 || ventas.some(function (v) { return datoValido(v[1]) === null; })) motivos.push("DEMANDA_FALTANTE");
      if (s === null || S === null) motivos.push("REGLA_FALTANTE");
      var base = {id: rep.repuesto_id, clase: rep.clase_abc, tipo_demanda: rep.tipo_demanda, proveedor_id: rep.proveedor_id};
      if (motivos.length) {
        filas.push(Object.assign(base, {
          est: 3, etiqueta: ETIQUETAS[3], motivos: motivos, stock: stock, en_camino: camino,
          punto_pedido: s, nivel_maximo: S, plazo: plazo, margen_dias: null,
          demanda_entrega: null, faltante_previsto: null, cantidad_sugerida: 0,
          costo_bs: null, venta_mes: null, _m: null, _f: 0
        }));
        continue;
      }
      var pr = pronostico(ventas, rep.tipo_demanda);
      var tasa = pr.unidades_mes / 30;
      var pos = stock + camino;
      var demanda = tasa * plazo;
      var faltante = demanda > pos ? demanda - pos : 0;
      var margen = tasa > 0 ? (pos - s) / tasa : null;
      var est = pos <= s ? 0 : (margen !== null && margen < plazo ? 1 : 2);
      var cantidad = Math.max(Math.floor(S - pos + 0.5), 0);
      if (est < 2) cantidad = Math.max(cantidad, 1);
      var cp = costoPuesto(rep, prov, tc);
      filas.push(Object.assign(base, {
        est: est, etiqueta: ETIQUETAS[est], motivos: [], stock: stock, en_camino: camino,
        punto_pedido: s, nivel_maximo: S, plazo: plazo,
        margen_dias: margen === null ? null : Math.floor(margen + EPS),
        demanda_entrega: demanda, faltante_previsto: faltante,
        cantidad_sugerida: cantidad, costo_bs: redondear(cantidad * cp.total_bs, 2),
        venta_mes: pr.unidades_mes, _m: margen, _f: faltante
      }));
    }
    filas.sort(function (x, y) {
      if (x.est !== y.est) return x.est - y.est;
      if (x._f !== y._f) return y._f - x._f;
      if (x._m !== y._m) {
        if (x._m === null) return 1;
        if (y._m === null) return -1;
        return x._m - y._m;
      }
      return x.id < y.id ? -1 : x.id > y.id ? 1 : 0;
    });
    filas.forEach(function (x) { delete x._m; delete x._f; });
    return filas;
  }

  function planPresupuesto(filasAlertas, presupuesto) {
    presupuesto = num(presupuesto);
    var filas = filasAlertas.filter(function (x) { return x.cantidad_sugerida > 0; }).map(function (x) {
      var c = {};
      for (var k in x) if (Object.prototype.hasOwnProperty.call(x, k)) c[k] = x[k];
      return c;
    });
    filas.sort(function (x, y) {
      if (x.est !== y.est) return x.est - y.est;
      var cx = ORDEN_CLASE[x.clase], cy = ORDEN_CLASE[y.clase];
      if (cx !== cy) return cx - cy;
      if (x.margen_dias !== y.margen_dias) {
        if (x.margen_dias === null) return 1;
        if (y.margen_dias === null) return -1;
        return x.margen_dias - y.margen_dias;
      }
      return x.id < y.id ? -1 : x.id > y.id ? 1 : 0;
    });
    var acum = 0, sigue = true;
    filas.forEach(function (x) {
      acum = redondear(acum + x.costo_bs, 2);
      sigue = sigue && acum <= presupuesto + EPS;
      x.acumulado_bs = acum;
      x.alcanza = sigue;
    });
    return filas;
  }

  // ---------------------------------------------------------------- proveedores

  function compararProveedores(datos, repId, tc) {
    var rep = buscarRepuesto(datos, repId);
    var filas = datos.proveedores.map(function (p) {
      var c = costoPuesto(rep, p, tc);
      return {
        proveedor_id: p.proveedor_id, nombre: p.nombre, origen: p.origen, incoterm: p.incoterm,
        plazo_normal_dias: num(p.plazo_normal_dias), desvio_plazo_dias: num(p.desvio_plazo_dias),
        pct_entregas_a_tiempo: num(p.pct_entregas_a_tiempo), asignado: p.proveedor_id === rep.proveedor_id,
        fabrica_bs: c.fabrica_bs, flete_bs: c.flete_bs, gastos_bs: c.gastos_bs, total_bs: c.total_bs,
        total_usd: c.total_usd, flete_incluido: c.flete_incluido
      };
    });
    filas.sort(function (x, y) {
      if (x.total_bs !== y.total_bs) return x.total_bs - y.total_bs;
      return x.proveedor_id < y.proveedor_id ? -1 : 1;
    });
    return filas;
  }

  // ---------------------------------------------------------------- ¿qué hubiera pasado?

  function diasDelMes(anio, mes) {
    if (mes === 2) return (anio % 4 === 0 && (anio % 100 !== 0 || anio % 400 === 0)) ? 29 : 28;
    return [4, 6, 9, 11].indexOf(mes) >= 0 ? 30 : 31;
  }

  function dos(x) { return x < 10 ? "0" + x : "" + x; }

  // Días del 1-11-2025 al 31-10-2026: [fecha, mes, días del mes].
  function calendarioPasado() {
    var dias = [];
    var anio = 2025, mes = 11;
    for (var k = 0; k < 12; k++) {
      var dm = diasDelMes(anio, mes);
      for (var d = 1; d <= dm; d++) dias.push([anio + "-" + dos(mes) + "-" + dos(d), anio + "-" + dos(mes), dm]);
      mes += 1;
      if (mes > 12) { mes = 1; anio += 1; }
    }
    return dias;
  }

  function tablaTC(serie) {
    var t = {};
    for (var i = 0; i < serie.length; i++) t[serie[i][0]] = num(serie[i][1]);
    return t;
  }

  function tcDelDia(fecha, tabla, serie) {
    if (fecha < INICIO_TCO) return TC_FIJO;
    if (tabla[fecha] !== undefined) return tabla[fecha];
    var v = TC_FIJO;
    for (var i = 0; i < serie.length; i++) if (serie[i][0] <= fecha) v = num(serie[i][1]);
    return v;
  }

  function pasado(datos, politica) {
    if (["lo_justo", "cubrir_60", "dos_pedidos"].indexOf(politica) < 0) throw new Error("Política desconocida: " + politica);
    var par = datos.parametros;
    var cped = num(par.costo_pedido_bs), tasaCap = num(par.costo_capital_mensual);
    var dias = calendarioPasado();
    var nd = dias.length;
    var serie = datos.tc.serie, tabla = tablaTC(serie);
    var tcs = dias.map(function (x) { return tcDelDia(x[0], tabla, serie); });
    var total = { politica: politica, ventas_perdidas: 0, ventas_atendidas: 0, capital_promedio_bs: 0, pedidos: 0, ganancia_bs: 0, ordenes: [] };

    for (var ri = 0; ri < datos.repuestos.length; ri++) {
      var rep = datos.repuestos[ri];
      var prov = buscarProveedor(datos, rep.proveedor_id);
      var plazo = num(prov.plazo_normal_dias);
      var cu = costoPuesto(rep, prov, 1).total_usd;
      var precio = num(rep.precio_venta_bs), tcRef = num(rep.tc_referencia_bs_por_usd);
      var ventas = datos.ventas[rep.repuesto_id];
      var porMes = {};
      for (var i = 0; i < ventas.length; i++) porMes[ventas[i][0]] = num(ventas[i][1]);
      var stock = num(rep.nivel_maximo_S);
      var llegadas = [], programadas = [];
      var compras = 0, ingreso = 0, capSum = 0, pedidos = 0, perdidas = 0, atendidas = 0;
      var valorInicial = stock * cu * tcs[0];

      var pedir = function (idx, q) {
        compras += q * cu * tcs[idx];
        pedidos += 1;
        llegadas.push([idx + plazo, q]);
        total.ordenes.push({ repuesto_id: rep.repuesto_id, fecha: dias[idx][0], cantidad: q, tc: tcs[idx] });
      };

      for (var di = 0; di < nd; di++) {
        var fecha = dias[di][0], mesActual = dias[di][1];
        var k;
        for (k = 0; k < llegadas.length; k++) if (llegadas[k][0] === di) stock += llegadas[k][1];
        for (k = 0; k < programadas.length; k++) if (programadas[k][0] === di) pedir(di, programadas[k][1]);
        if (fecha.slice(8) === "01") {
          var hist = [];
          for (k = 0; k < ventas.length; k++) if (ventas[k][0] < mesActual) hist.push(ventas[k]);
          var pr = pronostico(hist, rep.tipo_demanda);
          var tasa = pr.unidades_mes / 30;
          var sigma = desvio(ultimos(valores(hist), 24));
          var pos = stock;
          for (k = 0; k < llegadas.length; k++) if (llegadas[k][0] > di) pos += llegadas[k][1];
          for (k = 0; k < programadas.length; k++) if (programadas[k][0] > di) pos += programadas[k][1];
          var qa = necesidad(tasa, sigma, rep.clase_abc, plazo, pos).cantidad;
          if (qa > 0) {
            if (politica === "lo_justo") pedir(di, qa);
            else {
              var qc = qa + techo(60 * tasa);
              if (politica === "cubrir_60") pedir(di, qc);
              else {
                var q1 = Math.floor((qc + 1) / 2), q2 = qc - q1;
                pedir(di, q1);
                if (q2 > 0 && di + 30 < nd) programadas.push([di + 30, q2]);
              }
            }
          }
        }
        var dem = (porMes[mesActual] || 0) / dias[di][2];
        var vend = Math.min(stock, dem);
        stock -= vend;
        perdidas += dem - vend;
        atendidas += vend;
        ingreso += vend * precio * tcs[di] / tcRef;
        capSum += stock * cu * tcs[di];
      }
      var enCamino = 0;
      for (k = 0; k < llegadas.length; k++) if (llegadas[k][0] >= nd) enCamino += llegadas[k][1];
      var valorFinal = (stock + enCamino) * cu * tcs[nd - 1];
      total.ventas_perdidas += perdidas;
      total.ventas_atendidas += atendidas;
      total.capital_promedio_bs += capSum / nd;
      total.pedidos += pedidos;
      total.ganancia_bs += ingreso - compras - cped * pedidos - capSum * tasaCap / 30 + valorFinal - valorInicial;
    }
    return total;
  }

  // ---------------------------------------------------------------- temporadas (SCRUM-75)

  // Venta promedio por mes del año. Los meses son los de la serie re-fechada de SCRUM-55 (enero de 1998 de carparts
  // es agosto de 2022), así que muestran el patrón de carparts corrido siete meses, no las temporadas de Santa Cruz.
  // Un mes vacío o no válido no cuenta como cero: no entra al promedio de su mes.
  function perfilMensual(serie) {
    var suma = [], obs = [], i;
    for (i = 0; i < 12; i++) { suma.push(0); obs.push(0); }
    for (i = 0; i < serie.length; i++) {
      var u = datoValido(serie[i][1]);
      if (u === null) continue;
      var m = Number(String(serie[i][0]).slice(5, 7)) - 1;
      if (!(m >= 0 && m < 12)) continue;
      suma[m] += u;
      obs[m] += 1;
    }
    var prom = [], acum = 0, conDato = 0;
    for (i = 0; i < 12; i++) {
      prom.push(obs[i] ? suma[i] / obs[i] : null);
      if (obs[i]) { acum += prom[i]; conDato++; }
    }
    var media = conDato ? acum / conDato : null;
    var indice = [], fuertes = [], pico = null, flojo = null;
    for (i = 0; i < 12; i++) {
      indice.push(prom[i] === null || !media ? null : prom[i] / media);
      if (prom[i] === null) continue;
      if (media !== null && prom[i] > media + EPS) fuertes.push(i + 1);
      if (pico === null || prom[i] > prom[pico - 1] + EPS) pico = i + 1;
      if (flojo === null || prom[i] < prom[flojo - 1] - EPS) flojo = i + 1;
    }
    return { promedio_mes: prom, observaciones: obs, media: media, indice: indice, meses_fuertes: fuertes,
             mes_pico: pico, mes_flojo: flojo };
  }

  function temporadas(datos) {
    var ids = datos.repuestos.map(function (r) { return r.repuesto_id; });
    var porMes = {}, claves = [];
    var repuestos = ids.map(function (id) {
      var serie = datos.ventas[id] || [];
      for (var i = 0; i < serie.length; i++) {
        var u = datoValido(serie[i][1]);
        if (u === null) continue;
        if (!(serie[i][0] in porMes)) { porMes[serie[i][0]] = 0; claves.push(serie[i][0]); }
        porMes[serie[i][0]] += u;
      }
      var p = perfilMensual(serie);
      p.id = id;
      return p;
    });
    claves.sort();
    var total = perfilMensual(claves.map(function (k) { return [k, porMes[k]]; }));
    return { repuestos: repuestos, total: total };
  }

  // ---------------------------------------------------------------- cotización (SCRUM-72)

  // Tramos de EJEMPLO decididos por Sam el 13-11-2026: 5 % desde 10 unidades y 10 % desde 50.
  var TRAMOS_EJEMPLO = [{ desde: 10, pct: 5 }, { desde: 50, pct: 10 }];

  function cotizar(datos, repId, cantidad, tc, tramos) {
    var rep = buscarRepuesto(datos, repId);
    var q = Number(cantidad);
    if (!isFinite(q) || q < 1 || Math.floor(q) !== q) throw new Error("La cantidad debe ser un número entero de 1 o más");
    tc = num(tc);
    if (!isFinite(tc) || tc <= 0) throw new Error("El dólar debe ser un número mayor que cero");
    var t = (tramos || TRAMOS_EJEMPLO).slice().sort(function (a, b) { return a.desde - b.desde; });
    var prov = buscarProveedor(datos, rep.proveedor_id);
    var costo = costoPuesto(rep, prov, tc).total_bs;
    var lista = redondear(num(rep.precio_venta_usd) * tc, 2);
    var pct = 0, siguiente = null;
    for (var i = 0; i < t.length; i++) {
      if (q >= t[i].desde) pct = t[i].pct;
      else if (siguiente === null) siguiente = { desde: t[i].desde, pct: t[i].pct, faltan: t[i].desde - q };
    }
    // El descuento nunca deja el precio por debajo del costo puesto.
    var maxPct = lista > 0 ? Math.max(0, (1 - costo / lista) * 100) : 0;
    var tope = pct > maxPct + EPS;
    var unitario = tope ? costo : redondear(lista * (1 - pct / 100), 2);
    var subtotal = redondear(lista * q, 2), total = redondear(unitario * q, 2);
    var stock = datoValido(rep.stock_al_2026_11_10);
    var enStock = stock === null ? null : Math.min(stock, q);
    return {
      id: rep.repuesto_id, cantidad: q, tc: tc, precio_lista_bs: lista, costo_puesto_bs: costo,
      pct_tramo: pct, pct_aplicado: tope ? redondear(maxPct, 2) : pct, tope: tope,
      precio_unitario_bs: unitario, subtotal_bs: subtotal, descuento_bs: redondear(subtotal - total, 2), total_bs: total,
      siguiente_tramo: siguiente, stock: stock, en_stock: enStock,
      por_pedir: enStock === null ? null : q - enStock, plazo_dias: num(prov.plazo_normal_dias)
    };
  }

  // ---------------------------------------------------------------- clientes (SCRUM-76)

  // Tablero de clientes SINTÉTICOS. Temporada = meses fuertes de los 30 repuestos juntos (temporadas().total).
  // Monto = unidades × precio de lista con el dólar que se le pasa (en la app, el oficial del día), igual que el cotizador.
  function tableroClientes(datos, tc) {
    tc = num(tc);
    var temporada = temporadas(datos).total.meses_fuertes, enTemp = {};
    temporada.forEach(function (m) { enTemp[m] = true; });
    var precio = {};
    datos.repuestos.forEach(function (r) { precio[r.repuesto_id] = redondear(num(r.precio_venta_usd) * tc, 2); });
    var C = {}, orden = [];
    datos.clientes.lista.forEach(function (c) {
      C[c.cliente_id] = { id: c.cliente_id, nombre: c.nombre, tipo: c.tipo, zona: c.zona, unidades: 0, monto_bs: 0,
        unid_temp: 0, unid_fuera: 0, monto_temp_bs: 0, monto_fuera_bs: 0, _rep: {} };
      orden.push(c.cliente_id);
    });
    var total = { unidades: 0, monto_bs: 0, monto_temp_bs: 0, monto_fuera_bs: 0 };
    datos.clientes.ventas.forEach(function (v) {
      var c = C[v[2]], u = datoValido(v[3]);
      if (!c || u === null || !(v[1] in precio)) return;
      var monto = u * precio[v[1]], t = enTemp[Number(String(v[0]).slice(5, 7))] === true;
      c.unidades += u; c.monto_bs += monto;
      if (t) { c.unid_temp += u; c.monto_temp_bs += monto; total.monto_temp_bs += monto; }
      else { c.unid_fuera += u; c.monto_fuera_bs += monto; total.monto_fuera_bs += monto; }
      c._rep[v[1]] = (c._rep[v[1]] || 0) + u;
      total.unidades += u; total.monto_bs += monto;
    });
    var lista = orden.map(function (id) {
      var c = C[id];
      c.pct_temp = c.monto_bs > 0 ? c.monto_temp_bs / c.monto_bs * 100 : null;
      c.pct_total = total.monto_bs > 0 ? c.monto_bs / total.monto_bs * 100 : null;
      c.top = Object.keys(c._rep).map(function (r) { return { id: r, unidades: c._rep[r] }; })
        .sort(function (a, b) { return b.unidades - a.unidades || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0); }).slice(0, 3);
      delete c._rep;
      return c;
    });
    lista.sort(function (a, b) { return b.monto_bs - a.monto_bs || (a.id < b.id ? -1 : 1); });
    var tipos = {}, ordenTipos = [];
    lista.forEach(function (c) {
      if (!(c.tipo in tipos)) { tipos[c.tipo] = { tipo: c.tipo, clientes: 0, monto_bs: 0, monto_temp_bs: 0 }; ordenTipos.push(c.tipo); }
      tipos[c.tipo].clientes += 1; tipos[c.tipo].monto_bs += c.monto_bs; tipos[c.tipo].monto_temp_bs += c.monto_temp_bs;
    });
    var porTipo = ordenTipos.map(function (t) { return tipos[t]; })
      .sort(function (a, b) { return b.monto_bs - a.monto_bs || (a.tipo < b.tipo ? -1 : 1); });
    return { temporada: temporada, clientes: lista, por_tipo: porTipo, total: total };
  }

  // ---------------------------------------------------------------- dashboard (SCRUM-79)

  function mesMenos(mes, k) {
    var a = Number(String(mes).slice(0, 4)), m = Number(String(mes).slice(5, 7)) - 1 - k;
    a += Math.floor(m / 12); m = ((m % 12) + 12) % 12;
    return a + "-" + dos(m + 1);
  }
  function trimestre(mes) { return String(mes).slice(0, 4) + "-T" + (Math.floor((Number(String(mes).slice(5, 7)) - 1) / 3) + 1); }
  function porClave(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

  // Todo sale de las compras por cliente (datos.clientes.ventas): suman lo mismo que las ventas reales por repuesto y,
  // en el portal, incluyen las cotizaciones marcadas como venta. Dinero = unidades × precio de lista con el dólar
  // oficial del día, igual que el cotizador y el tablero de clientes (carparts no trae precios históricos).
  // Ventas válidas, una fila por mes, repuesto y cliente, con su monto en Bs. La usan dashboard y tableroEmpresa.
  function filasDeVentas(datos, tc) {
    var precio = {};
    datos.repuestos.forEach(function (r) { precio[r.repuesto_id] = redondear(num(r.precio_venta_usd) * tc, 2); });
    var nombre = {};
    datos.clientes.lista.forEach(function (c) { nombre[c.cliente_id] = c.nombre; });
    var filas = [];
    datos.clientes.ventas.forEach(function (v) {
      var u = datoValido(v[3]), mes = String(v[0]);
      if (u === null || !(v[1] in precio) || !(v[2] in nombre) || !/^\d{4}-\d{2}$/.test(mes)) return;
      filas.push({ mes: mes, rep: v[1], cli: v[2], u: u, bs: u * precio[v[1]] });
    });
    return { filas: filas, nombre: nombre };
  }

  function dashboard(datos, tc) {
    tc = num(tc);
    var V = filasDeVentas(datos, tc), filas = V.filas, nombre = V.nombre;
    var total = { unidades: 0, monto_bs: 0 };
    if (!filas.length) return { meses: [], demanda_mes: [], por_anio: [], total: total, repuestos: [], clientes: [], trimestres: [],
      ultimo_mes: null, ult12_bs: 0, prev12_bs: 0, top5_pct: null };
    var meses = filas.map(function (f) { return f.mes; }).sort(porClave);
    var desde = meses[0], ultimo = meses[meses.length - 1];
    var lista = [];
    for (var k = 0; ; k++) { var m = mesMenos(ultimo, k); lista.unshift(m); if (m === desde) break; }
    var dm = {}, anios = {}, reps = {}, clis = {}, trims = [];
    lista.forEach(function (m) { dm[m] = { mes: m, unidades: 0, monto_bs: 0 }; var t = trimestre(m); if (trims[trims.length - 1] !== t) trims.push(t); });
    var r6 = mesMenos(ultimo, 5), p6 = mesMenos(ultimo, 11), r12 = mesMenos(ultimo, 11), p12 = mesMenos(ultimo, 23);
    var ult12 = 0, prev12 = 0;
    filas.forEach(function (f) {
      total.unidades += f.u; total.monto_bs += f.bs;
      dm[f.mes].unidades += f.u; dm[f.mes].monto_bs += f.bs;
      var a = f.mes.slice(0, 4);
      if (!anios[a]) anios[a] = { anio: a, unidades: 0, monto_bs: 0, meses: {} };
      anios[a].unidades += f.u; anios[a].monto_bs += f.bs; anios[a].meses[f.mes] = true;
      if (!reps[f.rep]) reps[f.rep] = { id: f.rep, unidades: 0, monto_bs: 0 };
      reps[f.rep].unidades += f.u; reps[f.rep].monto_bs += f.bs;
      if (!clis[f.cli]) clis[f.cli] = { id: f.cli, nombre: nombre[f.cli], unidades: 0, monto_bs: 0, ult6_bs: 0, prev6_bs: 0, ultima_compra: f.mes, _t: {} };
      var c = clis[f.cli];
      c.unidades += f.u; c.monto_bs += f.bs; c._t[trimestre(f.mes)] = (c._t[trimestre(f.mes)] || 0) + f.bs;
      if (f.mes > c.ultima_compra) c.ultima_compra = f.mes;
      if (f.mes >= r6) c.ult6_bs += f.bs; else if (f.mes >= p6) c.prev6_bs += f.bs;
      if (f.mes >= r12) ult12 += f.bs; else if (f.mes >= p12) prev12 += f.bs;
    });
    var porAnio = Object.keys(anios).sort(porClave).map(function (a) {
      var x = anios[a]; return { anio: a, unidades: x.unidades, monto_bs: x.monto_bs, meses: Object.keys(x.meses).length };
    });
    var repuestos = Object.keys(reps).map(function (k) { var x = reps[k]; x.pct_unidades = x.unidades / total.unidades * 100; return x; })
      .sort(function (a, b) { return b.unidades - a.unidades || b.monto_bs - a.monto_bs || porClave(a.id, b.id); });
    var clientes = Object.keys(clis).map(function (k) {
      var c = clis[k];
      c.trimestres = trims.map(function (t) { return c._t[t] || 0; });
      c.pct_total = c.monto_bs / total.monto_bs * 100;
      c.variacion_pct = c.prev6_bs > 0 ? (c.ult6_bs - c.prev6_bs) / c.prev6_bs * 100 : null;
      c.tendencia = c.ult6_bs === 0 && c.prev6_bs === 0 ? "sin compras" : c.prev6_bs === 0 ? "nuevo" :
        c.variacion_pct >= 10 ? "sube" : c.variacion_pct <= -10 ? "baja" : "estable";
      delete c._t;
      return c;
    }).sort(function (a, b) { return b.monto_bs - a.monto_bs || porClave(a.id, b.id); });
    var top5 = clientes.slice(0, 5).reduce(function (s, c) { return s + c.monto_bs; }, 0);
    return {
      meses: lista, demanda_mes: lista.map(function (m) { return dm[m]; }), por_anio: porAnio, total: total,
      repuestos: repuestos, clientes: clientes, trimestres: trims, ultimo_mes: ultimo,
      ult12_bs: ult12, prev12_bs: prev12, top5_pct: total.monto_bs > 0 ? top5 / total.monto_bs * 100 : null
    };
  }

  // ---------------------------------------------------------------- tablero para la gerencia (SCRUM-79, versión empresarial)

  // El tablero de ventas en lenguaje simple. Junta dashboard (ventas), alertas (qué pedir) y rotacion (dinero parado)
  // y lo resume para un período: "12m" (los 12 meses que terminan en el último mes con ventas) o "todo".
  // Devuelve también una frase de conclusión por gráfico, armada con estas mismas cifras: la página solo la muestra.
  // Lo que es de hoy (almacén, qué pedir, dinero parado) y las ventas por año no dependen del período.
  var TIPO_PLURAL = { "Taller mecánico": "los talleres mecánicos", "Repuestera": "las repuesteras",
    "Flota de empresa": "las flotas de empresa", "Particular": "los particulares", "Tienda web": "las ventas de la tienda web" };
  var MES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  var DONA_MAX = 5, NOMBRE_CORTO_MAX = 44, CONECTORES = ["con", "de", "del", "para", "y", "a", "en"];

  // Entero con punto de miles: 13445.4 -> "13.445". Formato boliviano, igual en motor_ref.py.
  function miles(x) {
    var n = redondear(Math.abs(x), 0), s = String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (x < 0 && n !== 0 ? "−" : "") + s;
  }
  function bsTxt(x) { return "Bs " + miles(x); }
  function pl(n, uno, varios) { return n === 1 ? uno : varios; }
  function mayuscula(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function minuscula(s) { return s.charAt(0).toLowerCase() + s.slice(1); }
  function mesLargo(m) { return MES_LARGO[Number(m.slice(5, 7)) - 1] + " de " + m.slice(0, 4); }

  // Porcentajes enteros que suman exactamente 100 (método del resto mayor). Sin total, todos 0.
  function enteros100(valores) {
    var tot = valores.reduce(function (s, v) { return s + v; }, 0);
    if (!(tot > 0)) return valores.map(function () { return 0; });
    var crudo = valores.map(function (v) { return v / tot * 100; });
    var base = crudo.map(function (c) { return Math.floor(c); });
    var resto = 100 - base.reduce(function (s, v) { return s + v; }, 0);
    var orden = crudo.map(function (c, i) { return i; }).sort(function (a, b) {
      return (crudo[b] - base[b]) - (crudo[a] - base[a]) || a - b;
    });
    for (var k = 0; k < resto; k++) base[orden[k]] += 1;
    return base;
  }

  // Nombre para las barras: entero si entra; si no, se corta en una palabra (sin dejar un conector al final) y lleva «…».
  function nombreCorto(s) {
    s = String(s);
    if (s.length <= NOMBRE_CORTO_MAX) return s;
    var p = s.slice(0, s.lastIndexOf(" ", NOMBRE_CORTO_MAX - 1)).split(" ");
    while (p.length > 1 && CONECTORES.indexOf(p[p.length - 1].toLowerCase()) >= 0) p.pop();
    return p.join(" ").replace(/,$/, "") + "…";
  }

  // Suma por clave en el orden de las filas y ordena de mayor a menor monto (empate: por clave).
  function sumarPor(filas, clave) {
    var acc = {}, orden = [];
    filas.forEach(function (f) {
      var k = clave(f);
      if (!acc[k]) { acc[k] = { clave: k, monto_bs: 0, unidades: 0 }; orden.push(k); }
      acc[k].monto_bs += f.bs; acc[k].unidades += f.u;
    });
    return orden.map(function (k) { return acc[k]; })
      .sort(function (a, b) { return b.monto_bs - a.monto_bs || porClave(a.clave, b.clave); });
  }

  function variacion(ahora, antes) { return antes > 0 ? (ahora - antes) / antes * 100 : null; }

  function tableroEmpresa(datos, tc, periodo) {
    periodo = periodo === "todo" ? "todo" : "12m";
    tc = num(tc);
    // Hoy: semáforo del almacén, qué pedir ya y dinero parado. No dependen del período.
    var sem = [0, 0, 0, 0], costoPedir = 0;
    alertas(datos, tc).forEach(function (a) { sem[a.est] += 1; if (a.est === 0) costoPedir += num(a.costo_bs); });
    var R = rotacion(datos, tc);
    var estados = [["pedir", "Pedir ya", sem[0]], ["vigilar", "Vigilar", sem[1]], ["suficiente", "Con stock suficiente", sem[2]],
      ["sin_datos", "Sin datos para decidir", sem[3]]].filter(function (e) { return e[0] !== "sin_datos" || e[2] > 0; });
    var pctAlm = enteros100(estados.map(function (e) { return e[2]; }));
    var almacen = estados.map(function (e, i) { return { clave: e[0], etiqueta: e[1], repuestos: e[2], pct: pctAlm[i] }; });
    var nRep = sem[0] + sem[1] + sem[2] + sem[3];
    var conclAlm = (sem[0] > 0 ? sem[0] + " " + pl(sem[0], "repuesto está por agotarse y hay que pedirlo ya.", "repuestos están por agotarse y hay que pedirlos ya.")
      : "Ningún repuesto está por agotarse.") +
      (sem[1] > 0 ? " " + sem[1] + " más " + pl(sem[1], "hay que vigilarlo", "hay que vigilarlos") + "." : "") +
      " " + mayuscula(sem[2] + " " + pl(sem[2], "tiene", "tienen") + " stock suficiente.") +
      (sem[3] > 0 ? " De " + sem[3] + " no hay datos para decidir." : "");
    var hoy = {
      pedir_ya: { repuestos: sem[0], costo_bs: costoPedir },
      dinero_parado: { valor_bs: R.valor_acumulado_bs, repuestos: R.acumulacion },
      almacen: almacen, almacen_total: nRep
    };

    var T = dashboard(datos, tc), V = filasDeVentas(datos, tc);
    if (!T.meses.length) {
      return { periodo: periodo, vacio: true, hoy: hoy, conclusiones: { almacen: conclAlm } };
    }
    var ultimo = T.ultimo_mes, desde = periodo === "todo" ? T.meses[0] : mesMenos(ultimo, 11);
    if (desde < T.meses[0]) desde = T.meses[0];
    var filas = V.filas.filter(function (f) { return f.mes >= desde; });

    // Tarjetas: período y comparación de los últimos 12 meses contra los 12 anteriores (siempre la misma).
    var r12 = mesMenos(ultimo, 11), p12 = mesMenos(ultimo, 23), c = { ult12_bs: 0, prev12_bs: 0, ult12_u: 0, prev12_u: 0 };
    V.filas.forEach(function (f) {
      if (f.mes >= r12) { c.ult12_bs += f.bs; c.ult12_u += f.u; } else if (f.mes >= p12) { c.prev12_bs += f.bs; c.prev12_u += f.u; }
    });
    c.var_bs_pct = variacion(c.ult12_bs, c.prev12_bs); c.var_u_pct = variacion(c.ult12_u, c.prev12_u);
    var totBs = filas.reduce(function (s, f) { return s + f.bs; }, 0), totU = filas.reduce(function (s, f) { return s + f.u; }, 0);

    // Ventas de cada mes del período, promedio y mejor mes (empate: el primero).
    var meses = T.demanda_mes.filter(function (x) { return x.mes >= desde; })
      .map(function (x) { return { mes: x.mes, monto_bs: x.monto_bs, unidades: x.unidades }; });
    var mejor = meses[0];
    meses.forEach(function (x) { if (x.monto_bs > mejor.monto_bs) mejor = x; });
    var promMes = totBs / meses.length;

    // Tipos de cliente (dona): si hubiera más de DONA_MAX, los menores se juntan en «Otros».
    var tipoDe = {};
    datos.clientes.lista.forEach(function (x) { tipoDe[x.cliente_id] = x.tipo || "Sin tipo"; });
    var tipos = sumarPor(filas, function (f) { return tipoDe[f.cli]; });
    if (tipos.length > DONA_MAX) {
      var otros = { clave: "Otros", monto_bs: 0, unidades: 0 };
      tipos.slice(DONA_MAX - 1).forEach(function (t) { otros.monto_bs += t.monto_bs; otros.unidades += t.unidades; });
      tipos = tipos.slice(0, DONA_MAX - 1).concat([otros]);
    }
    var pctTipos = enteros100(tipos.map(function (t) { return t.monto_bs; }));
    tipos = tipos.map(function (t, i) { return { tipo: t.clave, monto_bs: t.monto_bs, unidades: t.unidades, pct: pctTipos[i] }; });

    // Categorías del catálogo, clientes y repuestos del período, ordenados por monto.
    var cat = {}, nomRep = {};
    ((datos.catalogo && datos.catalogo.repuestos) || []).forEach(function (x) { cat[x.repuesto_id] = x.categoria; nomRep[x.repuesto_id] = x.nombre; });
    var conPct = function (lista) { return lista.map(function (x) { x.pct = totBs > 0 ? x.monto_bs / totBs * 100 : 0; return x; }); };
    var categorias = conPct(sumarPor(filas, function (f) { return cat[f.rep] || "Sin categoría"; })
      .map(function (x) { return { categoria: x.clave, monto_bs: x.monto_bs, unidades: x.unidades }; }));
    var clientes = conPct(sumarPor(filas, function (f) { return f.cli; }).map(function (x) {
      return { id: x.clave, nombre: String(V.nombre[x.clave]).replace(" (ficticio)", ""), monto_bs: x.monto_bs, unidades: x.unidades }; }));
    var repuestos = conPct(sumarPor(filas, function (f) { return f.rep; }).map(function (x) {
      var n = nomRep[x.clave] || x.clave;
      return { id: x.clave, nombre: n, nombre_corto: nombreCorto(n), monto_bs: x.monto_bs, unidades: x.unidades }; }));
    var suma = function (lista) { return lista.reduce(function (s, x) { return s + x.monto_bs; }, 0); };
    var top5 = clientes.slice(0, 5), top10 = repuestos.slice(0, 10);
    var top5Pct = totBs > 0 ? suma(top5) / totBs * 100 : 0, top10Pct = totBs > 0 ? suma(top10) / totBs * 100 : 0;

    var porAnio = T.por_anio.map(function (a) { return { anio: a.anio, monto_bs: a.monto_bs, unidades: a.unidades, meses: a.meses, completo: a.meses >= 12 }; });

    // Conclusiones, una por gráfico.
    var tipo0 = tipos[0], quien = TIPO_PLURAL[tipo0.tipo] || "los clientes de tipo «" + tipo0.tipo + "»";
    var conclTipos = tipo0.pct > 50 ? "Más de la mitad de lo que vendemos se lo llevan " + quien + " (" + tipo0.pct + " %)."
      : mayuscula(quien) + " son los que más compran: se llevan el " + tipo0.pct + " % de lo que vendemos.";
    var cat0 = categorias[0], catN = categorias[categorias.length - 1];
    var conclCat = "Lo que más vendemos es " + minuscula(cat0.categoria) + ": el " + miles(cat0.pct) + " % de las ventas." +
      (categorias.length > 1 ? " Lo que menos, " + minuscula(catN.categoria) + " (" + miles(catN.pct) + " %)." : "");
    var conclCli = "Estos " + top5.length + " clientes (de " + clientes.length + ") dejan el " + miles(top5Pct) + " % de las ventas." +
      (top5Pct >= 50 ? " Si uno deja de comprar, se nota." : " Las ventas están repartidas entre muchos clientes.");
    var conclRep = "Estos " + top10.length + " repuestos (de " + repuestos.length + ") dejan el " + miles(top10Pct) + " % de las ventas." +
      (top10Pct >= 50 ? " Conviene no quedarse nunca sin ellos." : "");
    var comp = porAnio.filter(function (a) { return a.completo; }), conclAnio;
    if (comp.length >= 2) {
      var x = comp[comp.length - 2], y = comp[comp.length - 1], dBs = variacion(y.monto_bs, x.monto_bs), dU = variacion(y.unidades, x.unidades);
      if (Math.abs(dBs) < 5) {
        conclAnio = Math.abs(dU) < 5 ? x.anio + " y " + y.anio + " vendieron casi lo mismo, en dinero y en piezas."
          : x.anio + " y " + y.anio + " vendieron lo mismo en dinero, aunque en " + y.anio + " salieron " + (dU > 0 ? "más" : "menos") +
            " piezas: se vendieron repuestos más " + (dU > 0 ? "baratos" : "caros") + ".";
      } else {
        conclAnio = y.anio + " vendió " + miles(Math.abs(dBs)) + " % " + (dBs > 0 ? "más" : "menos") + " que " + x.anio + " en dinero.";
      }
    } else if (comp.length === 1) {
      conclAnio = comp[0].anio + " es el único año completo: " + bsTxt(comp[0].monto_bs) + ".";
    } else {
      conclAnio = "Todavía no hay un año completo para comparar.";
    }

    return {
      periodo: periodo, vacio: false, desde: desde, hasta: ultimo, meses_periodo: meses.length,
      tarjetas: { ventas_bs: totBs, unidades: totU, comparacion: c },
      hoy: hoy,
      meses: meses, promedio_mes_bs: promMes, mejor_mes: { mes: mejor.mes, monto_bs: mejor.monto_bs },
      tipos_cliente: tipos, categorias: categorias, clientes: clientes, clientes_total: clientes.length,
      top_clientes: top5, top_clientes_pct: top5Pct, repuestos: repuestos, repuestos_total: repuestos.length,
      top_repuestos: top10, top_repuestos_pct: top10Pct, por_anio: porAnio,
      conclusiones: {
        meses: mayuscula(mesLargo(mejor.mes)) + " fue el mejor mes (" + bsTxt(mejor.monto_bs) + "). En promedio, cada mes se venden " + bsTxt(promMes) + ".",
        tipos_cliente: conclTipos, almacen: conclAlm, categorias: conclCat, top_clientes: conclCli, top_repuestos: conclRep, anios: conclAnio
      }
    };
  }

  // ---------------------------------------------------------------- rotación e importancia (SCRUM-81)

  var ROT_ALTA_MESES = 3, ROT_MEDIA_MESES = 12, ACUM_MESES = 24, ABC_CORTES = [0.80, 0.95];

  // ABC por valor vendido en los últimos 12 meses (Pareto 80/95, por el acumulado ANTERIOR, como SCRUM-55) cruzado
  // con la rotación: cobertura = meses que dura el stock de hoy al ritmo de los últimos 12 meses.
  function rotacion(datos, tc) {
    tc = num(tc);
    var filas = datos.repuestos.map(function (r) {
      var id = r.repuesto_id, serie = datos.ventas[id] || [], v = [], k;
      for (k = 0; k < serie.length; k++) v.push(datoValido(Array.isArray(serie[k]) ? serie[k][1] : serie[k]));
      var stock = datoValido(r.stock_al_2026_11_10), transito = datoValido(r.en_transito_al_2026_11_10) || 0;
      var smax = datoValido(r.nivel_maximo_S), pv = redondear(num(r.precio_venta_usd) * tc, 2), cp = num(r.costo_puesto_usd) * tc;
      var validos = v.filter(function (x) { return x !== null; });
      if (validos.length < 12 || stock === null) {
        return { id: id, sin_datos: true, motivo: validos.length < 12 ? "no tiene 12 meses de ventas" : "no tiene stock registrado",
          u12: null, valor12_bs: 0, stock: stock, transito: transito, nivel_maximo: smax };
      }
      var u12 = ultimos(validos, 12).reduce(function (s, x) { return s + x; }, 0), sin = 0;
      for (k = validos.length - 1; k >= 0 && validos[k] === 0; k--) sin++;
      var cob = u12 > 0 ? stock / (u12 / 12) : null, rot = stock > 0 ? u12 / stock : null;
      var clase = u12 === 0 ? "baja" : cob <= ROT_ALTA_MESES + EPS ? "alta" : cob <= ROT_MEDIA_MESES + EPS ? "media" : "baja";
      var motivosAcum = [];
      if (smax !== null && stock + transito > smax) motivosAcum.push("stock y tránsito superan el nivel máximo");
      if (cob !== null && cob > ACUM_MESES + EPS) motivosAcum.push("stock para más de " + ACUM_MESES + " meses");
      if (u12 === 0 && stock > 0) motivosAcum.push("sin ventas en 12 meses y con stock");
      return {
        id: id, sin_datos: false, u12: u12, valor12_bs: u12 * pv, stock: stock, transito: transito, nivel_maximo: smax,
        cobertura_meses: cob, rotacion_anual: rot, meses_sin_venta: sin, clase_rot: clase,
        baja_rotacion: u12 === 0 || (rot !== null && rot < 1 - EPS), acumulacion: motivosAcum.length > 0, motivos_acumulacion: motivosAcum,
        valor_stock_bs: stock * cp
      };
    });
    var total = filas.reduce(function (s, f) { return s + f.valor12_bs; }, 0), acum = 0;
    filas.slice().sort(function (a, b) { return b.valor12_bs - a.valor12_bs || porClave(a.id, b.id); }).forEach(function (f) {
      if (f.sin_datos) { f.clase_abc = null; return; }
      var previo = total > 0 ? acum / total : 1;
      f.clase_abc = previo < ABC_CORTES[0] - EPS ? "A" : previo < ABC_CORTES[1] - EPS ? "B" : "C";
      f.pct_valor = total > 0 ? f.valor12_bs / total * 100 : 0;
      acum += f.valor12_bs;
      f.pct_acumulado = total > 0 ? acum / total * 100 : 0;
    });
    var matriz = {};
    ["A", "B", "C"].forEach(function (a) { matriz[a] = { alta: 0, media: 0, baja: 0 }; });
    filas.forEach(function (f) { if (!f.sin_datos) matriz[f.clase_abc][f.clase_rot] += 1; });
    var orden = { A: 0, B: 1, C: 2 };
    filas.sort(function (a, b) {
      if (a.sin_datos !== b.sin_datos) return a.sin_datos ? 1 : -1;
      return (orden[a.clase_abc] || 0) - (orden[b.clase_abc] || 0) || b.valor12_bs - a.valor12_bs || porClave(a.id, b.id);
    });
    var conDatos = filas.filter(function (f) { return !f.sin_datos; });
    return {
      repuestos: filas, matriz: matriz, valor12_total_bs: total,
      acumulacion: conDatos.filter(function (f) { return f.acumulacion; }).length,
      baja_rotacion: conDatos.filter(function (f) { return f.baja_rotacion; }).length,
      valor_acumulado_bs: conDatos.filter(function (f) { return f.acumulacion; }).reduce(function (s, f) { return s + f.valor_stock_bs; }, 0),
      umbrales: { rot_alta_meses: ROT_ALTA_MESES, rot_media_meses: ROT_MEDIA_MESES, acum_meses: ACUM_MESES, abc: ABC_CORTES }
    };
  }

  return {
    costoPuesto: costoPuesto, pronostico: pronostico, simular: simular, quiebreDolar: quiebreDolar,
    sensibilidad: sensibilidad, alertas: alertas, planPresupuesto: planPresupuesto,
    compararProveedores: compararProveedores, pasado: pasado, temporadas: temporadas, cotizar: cotizar, tableroClientes: tableroClientes,
    dashboard: dashboard, tableroEmpresa: tableroEmpresa, rotacion: rotacion,
    TRAMOS_EJEMPLO: TRAMOS_EJEMPLO,
    _interno: { mulberry32: mulberry32, normalIH: normalIH, expSerie: expSerie, redondear: redondear, volatilidadDiaria: volatilidadDiaria }
  };
})();

if (typeof module !== "undefined") module.exports = Motor;
