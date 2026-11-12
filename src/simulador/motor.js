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

  return {
    costoPuesto: costoPuesto, pronostico: pronostico, simular: simular, quiebreDolar: quiebreDolar,
    sensibilidad: sensibilidad, alertas: alertas, planPresupuesto: planPresupuesto,
    compararProveedores: compararProveedores, pasado: pasado,
    _interno: { mulberry32: mulberry32, normalIH: normalIH, expSerie: expSerie, redondear: redondear, volatilidadDiaria: volatilidadDiaria }
  };
})();

if (typeof module !== "undefined") module.exports = Motor;
