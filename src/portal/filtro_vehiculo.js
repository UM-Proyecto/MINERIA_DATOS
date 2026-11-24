/*
 * Filtro del catálogo por vehículo: marca → modelo → año (decisión D9, 24-11-2026).
 *
 * Lo usan la tienda (src/tienda/plantilla_tienda.html) y el catálogo del área de la empresa
 * (src/simulador/plantilla_app.html); los dos generadores lo incrustan después del motor. Trabaja sobre la tabla
 * repuesto ↔ vehículo que arma src/scrum-74/armar_aplicaciones.py, que es ILUSTRATIVA: un prototipo académico, no un
 * catálogo de compatibilidades del fabricante. Por eso las pantallas muestran siempre un rótulo que lo dice.
 *
 *   FiltroVehiculo.indice(filas)              -> {id: [aplicaciones]} con filas [id, marca, modelo, desde, hasta, motor]
 *   FiltroVehiculo.marcas(filas)              -> marcas con al menos una aplicación, en orden alfabético
 *   FiltroVehiculo.modelos(filas, marca)      -> modelos de esa marca (vacío si no hay marca)
 *   FiltroVehiculo.anios(filas, marca, modelo)-> años cubiertos por ese modelo, del más nuevo al más viejo
 *   FiltroVehiculo.coincide(apps, sel)        -> true si alguna aplicación cumple {marca, modelo, anio}; sin
 *                                                selección, true siempre; con selección, un repuesto sin
 *                                                aplicaciones no coincide
 *   FiltroVehiculo.resumen(apps, max)         -> «Toyota Hilux 2005–2015, Isuzu D-Max 2012–2019 y 3 más»
 *
 * Los repuestos cargados en el portal (tabla D1) no tienen aplicaciones: resumen() devuelve
 * «Compatibilidad no registrada» y, con un filtro de vehículo activo, no aparecen.
 */
var FiltroVehiculo = (function () {
  "use strict";
  var SIN_DATO = "Compatibilidad no registrada";

  function unicos(xs) { return xs.filter(function (x, i) { return xs.indexOf(x) === i; }); }
  function alfa(a, b) { return String(a).localeCompare(String(b), "es"); }
  // TOYOTA -> Toyota, para el texto corrido; los selectores muestran la marca como en el sitio.
  function nombreMarca(m) { return String(m).charAt(0) + String(m).slice(1).toLowerCase(); }

  function indice(filas) {
    var r = {};
    (filas || []).forEach(function (f) { (r[f[0]] = r[f[0]] || []).push(f); });
    return r;
  }
  function marcas(filas) { return unicos((filas || []).map(function (f) { return f[1]; })).sort(alfa); }
  function modelos(filas, marca) {
    if (!marca) return [];
    return unicos((filas || []).filter(function (f) { return f[1] === marca; }).map(function (f) { return f[2]; })).sort(alfa);
  }
  function anios(filas, marca, modelo) {
    if (!marca || !modelo) return [];
    var s = {};
    (filas || []).forEach(function (f) {
      if (f[1] === marca && f[2] === modelo) for (var y = f[3]; y <= f[4]; y++) s[y] = true;
    });
    return Object.keys(s).map(Number).sort(function (a, b) { return b - a; });
  }
  function coincide(apps, sel) {
    sel = sel || {};
    if (!sel.marca) return true;
    var anio = sel.anio ? Number(sel.anio) : null;
    return (apps || []).some(function (f) {
      return f[1] === sel.marca && (!sel.modelo || f[2] === sel.modelo) && (anio === null || (f[3] <= anio && anio <= f[4]));
    });
  }
  function resumen(apps, max) {
    if (!apps || !apps.length) return SIN_DATO;
    max = max || 2;
    // Un mismo modelo con dos motores (Hilux 2.5 diésel y 2.7 gasolina) se cuenta una vez, con el rango más amplio.
    var vistos = {}, orden = [];
    apps.forEach(function (f) {
      var k = f[1] + " " + f[2];
      if (!vistos[k]) { vistos[k] = [f[3], f[4]]; orden.push(k); }
      else { vistos[k][0] = Math.min(vistos[k][0], f[3]); vistos[k][1] = Math.max(vistos[k][1], f[4]); }
    });
    var txt = orden.slice(0, max).map(function (k) {
      var i = k.indexOf(" ");
      return nombreMarca(k.slice(0, i)) + k.slice(i) + " " + vistos[k][0] + "–" + vistos[k][1];
    });
    var resto = orden.length - max;
    return txt.join(", ") + (resto > 0 ? " y " + resto + " más" : "");
  }

  return {indice: indice, marcas: marcas, modelos: modelos, anios: anios, coincide: coincide, resumen: resumen,
          nombreMarca: nombreMarca, SIN_DATO: SIN_DATO};
})();
if (typeof module !== "undefined" && module.exports) module.exports = FiltroVehiculo;
