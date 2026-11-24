/*
 * Servidor del portal de MULTIPARTES (SCRUM-73, SCRUM-77 y SCRUM-78), para Cloudflare Pages en modo avanzado
 * (_worker.js) con una base D1.
 *
 * armar_portal.py antepone a este archivo el motor del simulador (motor.js). En la versión completa también antepone
 * DATOS_INCLUIDOS (datos_app.json) y APP_INCLUIDA (la app generada); en la liviana (--liviano), el servidor lee esos
 * dos archivos del repositorio público en GitHub, en la rama o commit de la variable FUENTE_REF (por defecto main), y
 * los guarda 10 minutos en memoria. Así el portal toma solo el dólar diario que actualiza SCRUM-71. El servidor:
 *  - sirve la tienda pública en «/» y la app de la empresa en «/empresa», las dos marcadas como portal;
 *  - guarda cada cotización con su número correlativo, recalculada aquí con el motor (no se confía en el precio
 *    que manda el navegador);
 *  - deja al importador cargar repuestos y dar de alta clientes, listar y exportar cotizaciones y marcar las que se
 *    vendieron;
 *  - muestra al proveedor solo sus repuestos.
 * Usuarios de DEMOSTRACIÓN, uno por rol (decisión de Sam del 13-11-2026). El cliente cotiza sin cuenta.
 * El token de sesión se firma con HMAC-SHA256 y la clave SECRETO, que se configura en Cloudflare y no va al repositorio.
 */

const USUARIOS = {
  importador: { clave: "demo-importador", rol: "importador", nombre: "Jefatura de compras (demostración)" },
  proveedor: { clave: "demo-proveedor", rol: "proveedor", proveedor_id: "PROV-CN-03", nombre: "Proveedor China Gama (demostración)" },
};
const HORAS_SESION = 8;
const MAX_CUERPO = 8192;
// D8: la carga masiva por CSV es la única ruta con un cuerpo mayor. 256 KB alcanzan para unas 1500 filas típicas; el
// tope que manda es MAX_FILAS_CSV, porque cada fila puede ser hasta dos escrituras en D1 (100 000 por día gratis).
const MAX_CSV = 256 * 1024;
const MAX_FILAS_CSV = 500;
const REPO = "https://raw.githubusercontent.com/UM-Proyecto/MINERIA_DATOS/";
const TC_URL = REPO + "main/data/processed/scrum-54/tco_bcb_diario.csv";
const TIPOS_CLIENTE = ["Taller mecánico", "Flota de empresa", "Repuestera", "Particular"];
const CLIENTE_WEB = "CLI-WEB";   // ventas de cotizaciones de la tienda, que no tienen cliente registrado

const ESQUEMA = [
  `CREATE TABLE IF NOT EXISTS cotizaciones (
     numero INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, cliente_id TEXT, cliente_nombre TEXT,
     repuesto_id TEXT NOT NULL, cantidad INTEGER NOT NULL CHECK (cantidad >= 1), tc REAL NOT NULL, tc_fecha TEXT NOT NULL,
     precio_lista_bs REAL NOT NULL, pct_aplicado REAL NOT NULL, total_bs REAL NOT NULL,
     convertida INTEGER NOT NULL DEFAULT 0, fecha_venta TEXT, correo TEXT, correo_enviado TEXT)`,
  `CREATE TABLE IF NOT EXISTS clientes (
     cliente_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, tipo TEXT NOT NULL, zona TEXT NOT NULL, alta TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS repuestos (
     repuesto_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, categoria TEXT NOT NULL, descripcion TEXT NOT NULL,
     costo_unitario_usd REAL NOT NULL, margen_pct REAL NOT NULL, stock INTEGER NOT NULL, proveedor_id TEXT NOT NULL,
     fecha_ingreso TEXT NOT NULL, alta TEXT NOT NULL)`,
  // Último número entregado de cada código correlativo (CLI-N…, REP-N…). Ver siguientes().
  `CREATE TABLE IF NOT EXISTS secuencias (nombre TEXT PRIMARY KEY, ultimo INTEGER NOT NULL)`,
  // D6 (decisión de Sam del 24-11-2026): el stock se descuenta al confirmar la venta. El stock vigente de un repuesto
  // es su stock base (el del dataset al 10-11-2026 para REP-0001…0030; la columna stock para los cargados) más la
  // suma de estos movimientos. Cantidad con signo: una venta resta, un ajuste suma o resta.
  `CREATE TABLE IF NOT EXISTS movimientos_stock (
     id INTEGER PRIMARY KEY AUTOINCREMENT, repuesto_id TEXT NOT NULL, cantidad INTEGER NOT NULL CHECK (cantidad <> 0),
     motivo TEXT NOT NULL CHECK (motivo IN ('venta', 'ajuste')), cotizacion INTEGER, fecha TEXT NOT NULL, usuario TEXT NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS movimientos_por_repuesto ON movimientos_stock (repuesto_id)`,
  // Una cotización descuenta stock una sola vez, aunque dos pedidos de venta lleguen juntos.
  `CREATE UNIQUE INDEX IF NOT EXISTS una_venta_por_cotizacion ON movimientos_stock (cotizacion) WHERE motivo = 'venta'`,
  // D8 (decisión de Sam del 24-11-2026): ajustes del importador a los 30 repuestos del dataset. El dataset no se toca;
  // cada columna no nula de esta tabla se pone encima del valor del dataset. El stock no está aquí: un ajuste de stock
  // es un movimiento «ajuste» en movimientos_stock.
  `CREATE TABLE IF NOT EXISTS ajustes_repuestos (
     repuesto_id TEXT PRIMARY KEY, nombre TEXT, categoria TEXT, descripcion TEXT, costo_unitario_usd REAL, margen_pct REAL,
     proveedor_id TEXT, modificado TEXT NOT NULL, usuario TEXT NOT NULL)`,
  // D7: marca de último cambio. Cada escritura del portal (venta, alta, edición, CSV y, con ellas, los movimientos
  // de stock) suma 1 en la misma db.batch. Las cotizaciones nuevas no la tocan: ya cambian MAX(numero).
  `CREATE TABLE IF NOT EXISTS marca (clave TEXT PRIMARY KEY, valor INTEGER NOT NULL, fecha TEXT NOT NULL)`,
];

// ------------------------------------------------------------------ utilidades

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" },
  });
}
const error = (status, mensaje) => json({ error: mensaje }, status);

async function leerJson(req) {
  const texto = await req.text();
  if (texto.length > MAX_CUERPO) throw new ErrorPedido(413, "El pedido es demasiado grande.");
  try { return JSON.parse(texto || "{}"); } catch (e) { throw new ErrorPedido(400, "El cuerpo no es JSON válido."); }
}

class ErrorPedido extends Error {
  constructor(status, mensaje) { super(mensaje); this.status = status; }
}

function texto(v, campo, max, obligatorio) {
  if (v === undefined || v === null || String(v).trim() === "") {
    if (obligatorio) throw new ErrorPedido(400, `Falta ${campo}.`);
    return null;
  }
  const s = String(v).trim().replace(/\s+/g, " ");
  if (s.length > max) throw new ErrorPedido(400, `${campo} tiene más de ${max} caracteres.`);
  return s;
}

function numero(v, campo, min, max, entero) {
  const n = typeof v === "string" && v.trim() === "" ? NaN : Number(v);
  if (!isFinite(n) || n < min || n > max || (entero && Math.floor(n) !== n)) {
    throw new ErrorPedido(400, `${campo} debe ser un número${entero ? " entero" : ""} entre ${min} y ${max}.`);
  }
  return n;
}

const ahora = () => new Date().toISOString().slice(0, 19) + "Z";

const b64url = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const deB64url = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));

async function clave(env) {
  if (!env.SECRETO || String(env.SECRETO).length < 32) throw new ErrorPedido(500, "El servidor no tiene configurada la clave de sesión.");
  return crypto.subtle.importKey("raw", new TextEncoder().encode(env.SECRETO), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

async function firmar(env, datos) {
  const cuerpo = b64url(new TextEncoder().encode(JSON.stringify(datos)));
  const firma = await crypto.subtle.sign("HMAC", await clave(env), new TextEncoder().encode(cuerpo));
  return cuerpo + "." + b64url(firma);
}

async function sesion(env, req) {
  const h = req.headers.get("authorization") || "";
  const m = h.match(/^Bearer ([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$/);
  if (!m) return null;
  let ok = false;
  try { ok = await crypto.subtle.verify("HMAC", await clave(env), deB64url(m[2]), new TextEncoder().encode(m[1])); } catch (e) { return null; }
  if (!ok) return null;
  let d;
  try { d = JSON.parse(new TextDecoder().decode(deB64url(m[1]))); } catch (e) { return null; }
  if (!d || typeof d.exp !== "number" || d.exp < Date.now() / 1000) return null;
  if (!USUARIOS[d.u] || USUARIOS[d.u].rol !== d.rol) return null;
  return d;
}

async function exigir(env, req, rol) {
  const s = await sesion(env, req);
  if (!s) throw new ErrorPedido(401, "Hay que entrar con un usuario.");
  if (s.rol !== rol) throw new ErrorPedido(403, "Este usuario no tiene acceso a esta parte.");
  return s;
}

// ------------------------------------------------------------------ datos y app

let DATOS = null, APP_HTML = null, TIENDA_HTML = null, recursosT = 0;
async function cargarRecursos(env) {
  if (typeof DATOS_INCLUIDOS !== "undefined") { DATOS = DATOS_INCLUIDOS; APP_HTML = APP_INCLUIDA; TIENDA_HTML = TIENDA_INCLUIDA; return; }
  if (DATOS && Date.now() - recursosT < 600e3) return;
  const ref = env.FUENTE_REF || "main";
  try {
    const [d, h, t] = await Promise.all([fetch(REPO + ref + "/data/processed/simulador/datos_app.json"),
                                         fetch(REPO + ref + "/reports/simulador/MULTIPARTES_Simulador_Compras.html"),
                                         fetch(REPO + ref + "/reports/tienda/MULTIPARTES_Tienda.html")]);
    if (!d.ok || !h.ok || !t.ok) throw new Error("GitHub respondió " + d.status + ", " + h.status + " y " + t.status);
    const datos = await d.json(), html = await h.text(), tienda = await t.text();
    if (!datos.repuestos || !html.includes("</head>") || !tienda.includes("</head>")) throw new Error("archivos inesperados");
    DATOS = datos; APP_HTML = html; TIENDA_HTML = tienda; recursosT = Date.now();
  } catch (e) {
    // Si ya había una copia, se sigue con ella; si no, se avisa en vez de responder con datos vacíos.
    if (!DATOS) throw new ErrorPedido(503, "No se pudieron leer los datos del portal. Intente de nuevo en un momento.");
  }
}

let esquemaListo = false;
async function base(env) {
  if (!env.DB) throw new ErrorPedido(500, "El servidor no tiene la base de datos conectada.");
  if (!esquemaListo) {
    await env.DB.batch(ESQUEMA.map(sql => env.DB.prepare(sql)));
    // Las tablas publicadas se crearon antes de que existieran estas columnas; se agregan si faltan, sin tocar las filas.
    // SCRUM-83: correo de la cotización. D8: quién y cuándo modificó por última vez un repuesto cargado.
    for (const [tabla, nuevas] of [["cotizaciones", ["correo", "correo_enviado"]], ["repuestos", ["modificado", "usuario"]]]) {
      const cols = (await env.DB.prepare(`PRAGMA table_info(${tabla})`).all()).results.map(c => c.name);
      for (const c of nuevas) if (!cols.includes(c)) await env.DB.prepare(`ALTER TABLE ${tabla} ADD COLUMN ${c} TEXT`).run();
    }
    esquemaListo = true;
  }
  return env.DB;
}

// ------------------------------------------------------------------ dólar del día

let tcCache = null;
async function dolar() {
  const fijo = { valor: DATOS.tc.oficial.valor, fecha: DATOS.tc.oficial.fecha, fuente: DATOS.tc.oficial.fuente, origen: "incrustado" };
  if (tcCache && Date.now() - tcCache.t < 3600e3) return tcCache.v;
  let v = fijo;
  try {
    const r = await fetch(TC_URL, { cf: { cacheTtl: 900 } });
    if (r.ok) {
      const filas = (await r.text()).trim().split("\n");
      const u = filas[filas.length - 1].split(",");
      const valor = Number(u[1]);
      if (/^\d{4}-\d{2}-\d{2}$/.test(u[0]) && valor > 5 && valor < 30 && u[0] >= fijo.fecha) {
        v = { valor: valor, fecha: u[0], fuente: DATOS.tc.oficial.fuente, origen: "repositorio" };
      }
    }
  } catch (e) { /* sin red: queda el valor incrustado, con su fecha */ }
  tcCache = { t: Date.now(), v: v };
  return v;
}

// ------------------------------------------------------------------ datos combinados

// Lo guardado que cambia los datos del dataset: repuestos cargados y suma de movimientos de stock por repuesto. Las dos
// lecturas van en una db.batch, que D1 cuenta como una sola consulta.
async function leerEstado(db) {
  const [c, m, a] = await db.batch([
    db.prepare("SELECT * FROM repuestos ORDER BY repuesto_id"),
    db.prepare("SELECT repuesto_id, SUM(cantidad) AS s FROM movimientos_stock GROUP BY repuesto_id"),
    db.prepare("SELECT * FROM ajustes_repuestos"),
  ]);
  const mov = {}, ajustes = {};
  m.results.forEach(x => { mov[x.repuesto_id] = Number(x.s) || 0; });
  a.results.forEach(x => { ajustes[x.repuesto_id] = x; });
  return { cargados: c.results, mov: mov, ajustes: ajustes };
}

// Stock base de un repuesto: el del dataset o el que se cargó en el alta. Los movimientos se suman aparte.
function stockBase(est, id) {
  const r = DATOS.repuestos.find(x => x.repuesto_id === id);
  if (r) return Number(r.stock_al_2026_11_10) || 0;
  const c = est.cargados.find(x => x.repuesto_id === id);
  return c ? c.stock : 0;
}
const stockVigente = (est, id) => stockBase(est, id) + (est.mov[id] || 0);

// Convierte un repuesto cargado al formato del motor. Sin historial de venta, sin punto de pedido ni en camino:
// el motor lo marca «Sin datos» en las alertas en vez de inventar esas cifras.
function comoRepuesto(r, est) {
  const prov = DATOS.proveedores.find(p => p.proveedor_id === r.proveedor_id) || {};
  return {
    repuesto_id: r.repuesto_id, codigo_carparts: "", tipo_demanda: "sin historial", clase_abc: "C",
    proveedor_id: r.proveedor_id, proveedor: prov.nombre || r.proveedor_id, origen: prov.origen || "",
    incoterm: prov.incoterm || "", plazo_normal_dias: prov.plazo_normal_dias,
    costo_unitario_usd: r.costo_unitario_usd, margen_pct: r.margen_pct,
    precio_venta_usd: Math.round(r.costo_unitario_usd * (1 + r.margen_pct / 100) * 100) / 100,
    stock_al_2026_11_10: paraMotor(r.stock + ((est && est.mov[r.repuesto_id]) || 0)), en_transito_al_2026_11_10: 0, punto_pedido_s: "", nivel_maximo_S: "",
    cargado: true, fecha_ingreso: r.fecha_ingreso,
  };
}

// Los datos del dataset con lo guardado encima: el stock vigente (base + movimientos) y los repuestos cargados. El
// motor (cotizar, alertas) lee el stock de stock_al_2026_11_10, así que ahí va el vigente. Una venta forzada puede dejar
// el stock en negativo; el motor trata un stock negativo como dato inválido («Sin datos»), así que recibe 0: no hay
// unidades en el almacén. El valor con signo lo dan /api/stock y el historial de movimientos.
const paraMotor = n => Math.max(0, n);
const r2 = n => Math.round(n * 100) / 100;
const dado = v => v !== null && v !== undefined;

// D8: un repuesto del dataset con el ajuste del importador encima. Si cambia el costo, el margen o el proveedor, se
// recalculan el costo puesto (flete y gastos del proveedor, como SCRUM-55) y el precio de venta; si no, quedan los del
// dataset tal cual, centavo por centavo.
function conAjuste(r, a) {
  if (!a) return r;
  const x = Object.assign({}, r);
  if (dado(a.costo_unitario_usd)) x.costo_unitario_usd = a.costo_unitario_usd;
  if (dado(a.margen_pct)) x.margen_pct = a.margen_pct;
  const p = DATOS.proveedores.find(q => q.proveedor_id === (dado(a.proveedor_id) ? a.proveedor_id : r.proveedor_id));
  if (dado(a.proveedor_id) && p) {
    Object.assign(x, { proveedor_id: p.proveedor_id, proveedor: p.nombre, origen: p.origen, incoterm: p.incoterm,
      plazo_normal_dias: p.plazo_normal_dias, desvio_plazo_dias: p.desvio_plazo_dias, pct_entregas_a_tiempo: p.pct_entregas_a_tiempo,
      flete_pct: p.incoterm === "CIF" ? 0 : p.flete_pct_aplicado, gastos_pct: p.gastos_pct_cif });
  }
  if ((dado(a.costo_unitario_usd) || dado(a.margen_pct) || dado(a.proveedor_id)) && p) {
    const fp = p.incoterm === "CIF" ? 0 : Number(p.flete_pct_aplicado), g = Number(p.gastos_pct_cif);
    x.costo_puesto_usd = r2(x.costo_unitario_usd * (1 + fp / 100) * (1 + g / 100));
    x.precio_venta_usd = r2(x.costo_puesto_usd * (1 + x.margen_pct / 100));
    const tc = Number(r.tc_referencia_bs_por_usd);
    if (tc > 0) Object.assign(x, { costo_unitario_bs: r2(x.costo_unitario_usd * tc), costo_puesto_bs: r2(x.costo_puesto_usd * tc), precio_venta_bs: r2(x.precio_venta_usd * tc) });
  }
  return x;
}
function catalogoCon(c, a) {
  if (!a) return c;
  const x = Object.assign({}, c);
  for (const k of ["nombre", "categoria", "descripcion"]) if (dado(a[k])) x[k] = a[k];
  return x;
}

function datosCon(est) {
  const d = Object.assign({}, DATOS);
  d.repuestos = DATOS.repuestos.map(r => {
    const x = conAjuste(r, est.ajustes[r.repuesto_id]);
    return est.mov[r.repuesto_id] ? Object.assign({}, x, { stock_al_2026_11_10: paraMotor(stockVigente(est, r.repuesto_id)) }) : x;
  }).concat(est.cargados.map(r => comoRepuesto(r, est)));
  d.catalogo = Object.assign({}, DATOS.catalogo, { repuestos: DATOS.catalogo.repuestos.map(c => catalogoCon(c, est.ajustes[c.repuesto_id])) });
  return d;
}

// D7: sentencia que suma 1 a la marca de cambios. Va dentro de la misma db.batch que la escritura, así la marca y el
// dato cambian juntos o no cambia ninguno. «cond» es una condición SQL opcional (con sus parámetros) para no contar
// una escritura que al final no ocurrió.
function marcarCambio(db, f, cond, args) {
  return db.prepare(`INSERT INTO marca (clave, valor, fecha) SELECT 'cambios', 1, ? WHERE ${cond || "1"}
      ON CONFLICT (clave) DO UPDATE SET valor = valor + 1, fecha = excluded.fecha`).bind(f, ...(args || []));
}

// ------------------------------------------------------------------ edición de repuestos (D8)

// Categorías admitidas: las del catálogo del dataset. Lista cerrada, para que no vuelva a entrar un filtro de aire en
// «Kit de embrague» por un error de tipeo.
const categorias = () => [...new Set(DATOS.catalogo.repuestos.map(c => c.categoria))];
const EDITABLES = ["nombre", "categoria", "descripcion", "costo_unitario_usd", "margen_pct", "proveedor_id", "stock"];

// Un texto que empieza con =, +, - o @ se toma como fórmula al abrir un CSV exportado en Excel.
function sinFormula(s, campo) {
  if (s && /^[=+\-@]/.test(s)) throw new ErrorPedido(400, `${campo} no puede empezar con =, +, - ni @ (Excel lo tomaría como una fórmula).`);
  return s;
}

function fechaValida(f) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(f)) return false;
  const d = new Date(f + "T00:00:00Z");
  return !isNaN(d) && d.toISOString().slice(0, 10) === f;
}

// Valida los campos de un repuesto con las reglas del alta. En un alta todos son obligatorios salvo la descripción;
// en una edición solo se validan los que «esta» dice que vinieron.
function validarRepuesto(b, alta, esta) {
  const v = {};
  if (alta || esta("nombre")) v.nombre = sinFormula(texto(b.nombre, "El nombre", 80, true), "El nombre");
  if (alta || esta("categoria")) {
    v.categoria = texto(b.categoria, "La categoría", 60, true);
    if (!categorias().includes(v.categoria)) throw new ErrorPedido(400, "La categoría debe ser una de: " + categorias().join(", ") + ".");
  }
  if (alta || esta("descripcion")) v.descripcion = sinFormula(texto(b.descripcion, "La descripción", 200, false) || "", "La descripción");
  if (alta || esta("costo_unitario_usd")) v.costo_unitario_usd = numero(b.costo_unitario_usd, "El costo en USD", 0.01, 100000, false);
  if (alta || esta("margen_pct")) v.margen_pct = numero(b.margen_pct, "El margen", 0, 300, false);
  if (alta || esta("stock")) v.stock = numero(b.stock, "El stock", 0, 1000000, true);
  if (alta || esta("proveedor_id")) {
    v.proveedor_id = texto(b.proveedor_id, "el proveedor", 20, true);
    if (!DATOS.proveedores.some(p => p.proveedor_id === v.proveedor_id)) throw new ErrorPedido(400, "Ese proveedor no existe.");
  }
  if (alta) {
    v.fecha_ingreso = texto(b.fecha_ingreso, "La fecha de ingreso", 10, true);
    if (!fechaValida(v.fecha_ingreso)) throw new ErrorPedido(400, "La fecha va como AAAA-MM-DD.");
  }
  return v;
}

// Valores vigentes de un repuesto, sea del dataset (con su ajuste) o cargado. null si no existe.
function actual(est, id) {
  const c = est.cargados.find(x => x.repuesto_id === id);
  if (c) return { origen: "cargado", nombre: c.nombre, categoria: c.categoria, descripcion: c.descripcion, costo_unitario_usd: c.costo_unitario_usd,
    margen_pct: c.margen_pct, proveedor_id: c.proveedor_id, stock: stockVigente(est, id) };
  const r = DATOS.repuestos.find(x => x.repuesto_id === id);
  if (!r) return null;
  const cat = DATOS.catalogo.repuestos.find(x => x.repuesto_id === id) || {}, a = est.ajustes[id] || {};
  const v = (k, base) => (dado(a[k]) ? a[k] : base);
  return { origen: "dataset", nombre: v("nombre", cat.nombre), categoria: v("categoria", cat.categoria), descripcion: v("descripcion", cat.descripcion || ""),
    costo_unitario_usd: v("costo_unitario_usd", r.costo_unitario_usd), margen_pct: v("margen_pct", r.margen_pct),
    proveedor_id: v("proveedor_id", r.proveedor_id), stock: stockVigente(est, id) };
}

// Sentencias de una edición. Solo cambia lo que es distinto de lo vigente. Un repuesto cargado se actualiza en su
// tabla; uno del dataset, en ajustes_repuestos. El stock nunca se pisa: se registra un movimiento «ajuste» por la
// diferencia, calculada dentro de la sentencia para que una venta que llegue en el medio no se pierda.
function planEdicion(db, est, id, v, usuario, f) {
  const act = actual(est, id), cambios = [], stmts = [];
  const campos = EDITABLES.filter(k => k !== "stock" && k in v && v[k] !== act[k]);
  campos.forEach(k => cambios.push({ campo: k, antes: act[k], despues: v[k] }));
  if (campos.length && act.origen === "cargado") {
    stmts.push(db.prepare(`UPDATE repuestos SET ${campos.map(k => k + " = ?").join(", ")}, modificado = ?, usuario = ? WHERE repuesto_id = ?`)
      .bind(...campos.map(k => v[k]), f, usuario, id));
  } else if (campos.length) {
    stmts.push(db.prepare(`INSERT INTO ajustes_repuestos (repuesto_id, ${campos.join(", ")}, modificado, usuario) VALUES (?, ${campos.map(() => "?").join(", ")}, ?, ?)
        ON CONFLICT (repuesto_id) DO UPDATE SET ${campos.map(k => k + " = excluded." + k).join(", ")}, modificado = excluded.modificado, usuario = excluded.usuario`)
      .bind(id, ...campos.map(k => v[k]), f, usuario));
  }
  if ("stock" in v && v.stock !== act.stock) {
    cambios.push({ campo: "stock", antes: act.stock, despues: v.stock });
    stmts.push(db.prepare(`INSERT INTO movimientos_stock (repuesto_id, cantidad, motivo, fecha, usuario)
        SELECT ?, d, 'ajuste', ?, ? FROM (SELECT ? - ? - COALESCE((SELECT SUM(cantidad) FROM movimientos_stock WHERE repuesto_id = ?), 0) AS d) WHERE d <> 0`)
      .bind(id, f, usuario, v.stock, stockBase(est, id), id));
  }
  return { cambios: cambios, stmts: stmts };
}

// ------------------------------------------------------------------ carga masiva por CSV (D8)

const COLS_CSV = ["repuesto_id", "nombre", "categoria", "descripcion", "costo_unitario_usd", "margen_pct", "stock", "proveedor_id", "fecha_ingreso"];
const NUMERICAS = ["costo_unitario_usd", "margen_pct", "stock"];

// CSV con comillas al estilo de Excel. El separador se decide una sola vez, por el encabezado: punto y coma (Excel en
// español, con coma decimal) o coma (con punto decimal). Devuelve las filas con su número de fila en el archivo.
function parsearCsv(t) {
  t = t.replace(/^\uFEFF/, "");
  const cab = t.split(/\r?\n/, 1)[0];
  const sep = cab.includes(";") ? ";" : ",";
  const filas = [];
  let fila = [], celda = "", q = false, n = 1, inicio = 1;
  const cerrar = () => { fila.push(celda); filas.push({ n: inicio, celdas: fila }); fila = []; celda = ""; inicio = n; };
  for (let i = 0; i < t.length; i++) {
    const ch = t[i];
    if (q) {
      if (ch === '"' && t[i + 1] === '"') { celda += '"'; i++; } else if (ch === '"') q = false; else { if (ch === "\n") n++; celda += ch; }
    } else if (ch === '"') q = true;
    else if (ch === sep) { fila.push(celda); celda = ""; }
    else if (ch === "\n" || ch === "\r") { if (ch === "\r" && t[i + 1] === "\n") i++; n++; cerrar(); }
    else celda += ch;
  }
  if (q) throw new ErrorPedido(400, "El archivo tiene comillas sin cerrar.");
  if (celda !== "" || fila.length) cerrar();
  return { sep: sep, filas: filas.filter(f => f.celdas.some(c => c.trim() !== "")) };
}

// Revisa todas las filas sin escribir nada. Cada fila es un alta (repuesto_id vacío) o una edición de un repuesto que
// existe (celda vacía = no cambia). Devuelve el informe por fila y, si no hay errores, las sentencias a ejecutar.
async function revisarCsv(db, est, texto0, usuario) {
  const { sep, filas } = parsearCsv(texto0);
  if (!filas.length) throw new ErrorPedido(400, "El archivo está vacío.");
  const cab = filas[0].celdas.map(c => c.trim().toLowerCase());
  if (cab.join(",") !== COLS_CSV.join(",")) throw new ErrorPedido(400, "El encabezado debe ser exactamente: " + COLS_CSV.join(sep) + ". Descargue la plantilla.");
  const datos = filas.slice(1);
  if (!datos.length) throw new ErrorPedido(400, "El archivo no tiene filas debajo del encabezado.");
  if (datos.length > MAX_FILAS_CSV) throw new ErrorPedido(413, `El archivo tiene ${datos.length} filas; el máximo es ${MAX_FILAS_CSV}. Divídalo en partes.`);
  const f = ahora(), informe = [], stmts = [], altas = [], vistos = {};
  const existentes = {};
  DATOS.repuestos.concat(est.cargados).forEach(r => { const a = actual(est, r.repuesto_id); existentes[(a.nombre + "|" + a.proveedor_id).toLowerCase()] = r.repuesto_id; });
  for (const fila of datos) {
    const res = { fila: fila.n, repuesto_id: "", accion: "", cambios: [], error: null };
    informe.push(res);
    try {
      if (fila.celdas.length !== COLS_CSV.length) throw new ErrorPedido(400, `Tiene ${fila.celdas.length} columnas y deben ser ${COLS_CSV.length}.`);
      const b = {};
      COLS_CSV.forEach((k, i) => { let c = fila.celdas[i].trim(); if (sep === ";" && NUMERICAS.includes(k)) c = c.replace(",", "."); b[k] = c; });
      const id = b.repuesto_id;
      if (!id) {
        res.accion = "alta";
        const v = validarRepuesto(b, true);
        const clave = (v.nombre + "|" + v.proveedor_id).toLowerCase();
        if (existentes[clave]) throw new ErrorPedido(400, `Ya existe «${v.nombre}» con ese proveedor (${existentes[clave]}). Para cambiarlo, escriba su código en repuesto_id.`);
        if (vistos[clave]) throw new ErrorPedido(400, `Repite el alta de la fila ${vistos[clave]}.`);
        vistos[clave] = fila.n;
        altas.push({ res: res, v: v });
        res.cambios = EDITABLES.map(k => ({ campo: k, antes: null, despues: v[k] }));
      } else {
        res.accion = "edición"; res.repuesto_id = id;
        if (!actual(est, id)) throw new ErrorPedido(400, `No existe el repuesto ${id}. Para un alta, deje repuesto_id vacío.`);
        if (vistos[id]) throw new ErrorPedido(400, `El repuesto ${id} ya aparece en la fila ${vistos[id]}.`);
        vistos[id] = fila.n;
        if (b.fecha_ingreso) throw new ErrorPedido(400, "La fecha de ingreso solo se usa en las altas; déjela vacía.");
        const v = validarRepuesto(b, false, k => b[k] !== "");
        const plan = planEdicion(db, est, id, v, usuario, f);
        res.cambios = plan.cambios;
        if (!plan.cambios.length) res.accion = "sin cambios";
        stmts.push(...plan.stmts);
      }
    } catch (e) {
      if (!(e instanceof ErrorPedido)) throw e;
      res.error = e.message;
    }
  }
  const errores = informe.filter(r => r.error).length;
  return { informe: informe, errores: errores, altas: altas, stmts: stmts, fecha: f };
}

function celdaCsv(v) {
  let s = v === null || v === undefined ? "" : String(v);
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return /[",;\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

// Reserva los próximos «cuantos» códigos de una serie (CLI-N001, REP-N001, …). Antes se usaba COUNT(*) + 1: si se
// borraba una fila, el alta siguiente repetía un código existente y la clave primaria fallaba. Ahora el último número
// entregado queda en la tabla secuencias, y se compara con el máximo que ya existe en la tabla, para que una base
// anterior a este cambio (o una fila cargada a mano) no choque. El UPDATE es una sola sentencia: dos altas al mismo
// tiempo reciben números distintos. Si después falla el INSERT, ese número queda sin usar, y no importa.
async function siguientes(db, serie, tabla, col, prefijo, cuantos) {
  const n = cuantos || 1, desde = prefijo.length + 1;
  const [, r] = await db.batch([
    db.prepare("INSERT OR IGNORE INTO secuencias (nombre, ultimo) VALUES (?, 0)").bind(serie),
    db.prepare(`UPDATE secuencias SET ultimo = MAX(ultimo, (SELECT COALESCE(MAX(CAST(substr(${col}, ${desde}) AS INTEGER)), 0)
        FROM ${tabla} WHERE ${col} LIKE '${prefijo}%')) + ? WHERE nombre = ? RETURNING ultimo`).bind(n, serie),
  ]);
  const ultimo = r.results[0].ultimo;
  return Array.from({ length: n }, (_, i) => prefijo + String(ultimo - n + 1 + i).padStart(3, "0"));
}

async function existeCliente(db, id) {
  if (DATOS.clientes.lista.some(c => c.cliente_id === id)) return true;
  return !!(await db.prepare("SELECT 1 FROM clientes WHERE cliente_id = ?").bind(id).first());
}

// ------------------------------------------------------------------ rutas

async function api(req, env, url) {
  const ruta = url.pathname, m = req.method;

  if (ruta === "/api/salud" && m === "GET") return json({ ok: true });

  // D7: versión de lo guardado, para que el navegador consulte cada 30 s sin volver a bajar todo. Lee dos filas: el
  // máximo número de cotización (sale del índice de la clave primaria) y la marca de cambios. «v» cambia con cada
  // cotización nueva y con cada escritura del portal.
  if (ruta === "/api/version" && m === "GET") {
    const r = await (await base(env)).prepare(`SELECT (SELECT COALESCE(MAX(numero), 0) FROM cotizaciones) AS cotizaciones,
        (SELECT valor FROM marca WHERE clave = 'cambios') AS cambios, (SELECT fecha FROM marca WHERE clave = 'cambios') AS fecha`).first();
    const c = r.cambios || 0;
    return json({ v: r.cotizaciones + "." + c, cotizaciones: r.cotizaciones, cambios: c, fecha: r.fecha || null });
  }
  if (ruta === "/api/tc" && m === "GET") return json(await dolar());

  if (ruta === "/api/entrar" && m === "POST") {
    const b = await leerJson(req);
    const u = USUARIOS[String(b.usuario || "").trim().toLowerCase()];
    if (!u || b.clave !== u.clave) return error(401, "Usuario o clave incorrectos.");
    const s = { u: String(b.usuario).trim().toLowerCase(), rol: u.rol, prov: u.proveedor_id || null, exp: Math.floor(Date.now() / 1000) + HORAS_SESION * 3600 };
    return json({ token: await firmar(env, s), rol: u.rol, nombre: u.nombre, proveedor_id: s.prov });
  }
  if (ruta === "/api/yo" && m === "GET") {
    const s = await sesion(env, req);
    return s ? json({ rol: s.rol, nombre: USUARIOS[s.u].nombre, proveedor_id: s.prov }) : error(401, "Sin sesión.");
  }

  // Catálogo público: repuestos cargados por el importador (sin datos internos).
  if (ruta === "/api/repuestos" && m === "GET") {
    const est = await leerEstado(await base(env));
    return json(est.cargados.map(r => ({
      repuesto_id: r.repuesto_id, nombre: r.nombre, categoria: r.categoria, descripcion: r.descripcion,
      precio_venta_usd: comoRepuesto(r).precio_venta_usd, costo_unitario_usd: r.costo_unitario_usd, margen_pct: r.margen_pct,
      stock: paraMotor(stockVigente(est, r.repuesto_id)), proveedor_id: r.proveedor_id, fecha_ingreso: r.fecha_ingreso,
    })));
  }

  // D6: stock vigente de todos los repuestos (dataset y cargados), para la tienda y el área de la empresa. Público y
  // sin datos internos: solo el código y las unidades.
  if (ruta === "/api/stock" && m === "GET") {
    const est = await leerEstado(await base(env));
    const ids = DATOS.repuestos.map(r => r.repuesto_id).concat(est.cargados.map(r => r.repuesto_id));
    return json({ base: "2026-11-10", repuestos: ids.map(id => ({ repuesto_id: id, stock: stockVigente(est, id) })) });
  }
  // Historial de movimientos de stock (ventas y ajustes), del más nuevo al más viejo.
  if (ruta === "/api/movimientos" && m === "GET") {
    await exigir(env, req, "importador");
    const db = await base(env), rep = url.searchParams.get("repuesto");
    const q = "SELECT * FROM movimientos_stock" + (rep ? " WHERE repuesto_id = ?" : "") + " ORDER BY id DESC LIMIT 1000";
    return json((await (rep ? db.prepare(q).bind(rep) : db.prepare(q)).all()).results);
  }

  // SCRUM-73: cada cotización se guarda sola al emitirse. El cliente no necesita cuenta.
  if (ruta === "/api/cotizaciones" && m === "POST") {
    const b = await leerJson(req);
    const db = await base(env);
    const repId = texto(b.repuesto_id, "el repuesto", 20, true);
    const cantidad = numero(b.cantidad, "La cantidad", 1, 100000, true);
    const clienteId = texto(b.cliente_id, "el cliente", 20, false);
    const nombre = texto(b.cliente_nombre, "El nombre del cliente", 80, false);
    // SCRUM-83: el correo al que se «envía» la cotización. El envío es SIMULADO: se guarda la dirección y la hora,
    // y no sale ningún correo de este servidor.
    const correo = texto(b.correo, "El correo", 120, false);
    if (correo && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(correo)) return error(400, "El correo no tiene una forma válida, por ejemplo nombre@empresa.com.");
    if (clienteId && !(await existeCliente(db, clienteId))) return error(400, "Ese cliente no existe.");
    const d = datosCon(await leerEstado(db));
    if (!d.repuestos.some(r => r.repuesto_id === repId)) return error(400, "Ese repuesto no existe.");
    const tc = await dolar();
    const c = Motor.cotizar(d, repId, cantidad, tc.valor);
    const r = await db.prepare(`INSERT INTO cotizaciones (fecha, cliente_id, cliente_nombre, repuesto_id, cantidad, tc, tc_fecha,
        precio_lista_bs, pct_aplicado, total_bs, correo, correo_enviado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING numero, fecha, correo_enviado`)
      .bind(ahora(), clienteId, nombre, repId, cantidad, tc.valor, tc.fecha, c.precio_lista_bs, c.pct_aplicado, c.total_bs, correo, correo ? ahora() : null).first();
    return json(Object.assign({ numero: r.numero, fecha: r.fecha, tc_fecha: tc.fecha, correo: correo, correo_enviado: r.correo_enviado, cliente_nombre: nombre }, c), 201);
  }
  if (ruta === "/api/cotizaciones" && m === "GET") {
    await exigir(env, req, "importador");
    const db = await base(env);
    const where = [], args = [];
    const cli = url.searchParams.get("cliente"), rep = url.searchParams.get("repuesto"), mes = url.searchParams.get("mes");
    if (cli) { where.push("cliente_id = ?"); args.push(cli); }
    if (rep) { where.push("repuesto_id = ?"); args.push(rep); }
    if (mes) {
      if (!/^\d{4}-\d{2}$/.test(mes)) return error(400, "El mes va como AAAA-MM.");
      where.push("substr(fecha, 1, 7) = ?"); args.push(mes);
    }
    const sql = "SELECT * FROM cotizaciones" + (where.length ? " WHERE " + where.join(" AND ") : "") + " ORDER BY numero DESC LIMIT 5000";
    const filas = (await db.prepare(sql).bind(...args).all()).results;
    if (url.searchParams.get("formato") === "csv") {
      const cols = ["numero", "fecha", "cliente_id", "cliente_nombre", "repuesto_id", "cantidad", "tc", "tc_fecha", "precio_lista_bs", "pct_aplicado", "total_bs", "convertida", "fecha_venta", "correo", "correo_enviado"];
      const celda = v => { const s = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
      const csv = [cols.join(",")].concat(filas.map(f => cols.map(c => celda(f[c])).join(","))).join("\n") + "\n";
      return new Response(csv, { headers: { "content-type": "text/csv; charset=utf-8", "content-disposition": 'attachment; filename="cotizaciones.csv"', "cache-control": "no-store" } });
    }
    const tot = await db.prepare("SELECT COUNT(*) AS n, SUM(convertida) AS v FROM cotizaciones").first();
    return json({ filas: filas, total: tot.n || 0, convertidas: tot.v || 0, no_convertidas: (tot.n || 0) - (tot.v || 0) });
  }
  const venta = ruta.match(/^\/api\/cotizaciones\/(\d+)\/venta$/);
  if (venta && m === "POST") {
    // D6: marcar la venta descuenta del stock la cantidad cotizada. La cotización sola no descuenta ni reserva.
    const s = await exigir(env, req, "importador");
    const b = await leerJson(req);
    const forzar = b.forzar === true;
    const db = await base(env);
    const num = Number(venta[1]);
    const cot = await db.prepare("SELECT numero, repuesto_id, cantidad, convertida FROM cotizaciones WHERE numero = ?").bind(num).first();
    if (!cot || cot.convertida) return error(404, "No existe esa cotización o ya estaba marcada como venta.");
    const est = await leerEstado(db);
    const base0 = stockBase(est, cot.repuesto_id), antes = base0 + (est.mov[cot.repuesto_id] || 0), despues = antes - cot.cantidad;
    if (despues < 0 && !forzar) {
      return json({ error: `No hay stock suficiente: ${cot.repuesto_id} tiene ${antes} unidades y la cotización es de ${cot.cantidad}. ` +
        `Si las unidades sí salieron del almacén, confirme la venta de todos modos; el stock quedará en ${despues}.`,
        stock: antes, cantidad: cot.cantidad, stock_despues: despues }, 409);
    }
    // El movimiento y la marca de venta van en una misma db.batch, que D1 ejecuta como una transacción. Las dos
    // sentencias repiten las condiciones (cotización sin vender y stock suficiente, salvo que se fuerce): si otra
    // venta se coló entre la lectura de arriba y esta escritura, no se escribe nada y se avisa.
    const f = ahora();
    const [, u] = await db.batch([
      db.prepare(`INSERT INTO movimientos_stock (repuesto_id, cantidad, motivo, cotizacion, fecha, usuario)
          SELECT repuesto_id, -cantidad, 'venta', numero, ?, ? FROM cotizaciones c WHERE numero = ? AND convertida = 0
          AND (? = 1 OR ? + COALESCE((SELECT SUM(cantidad) FROM movimientos_stock WHERE repuesto_id = c.repuesto_id), 0) - cantidad >= 0)`)
        .bind(f, s.u, num, forzar ? 1 : 0, base0),
      db.prepare(`UPDATE cotizaciones SET convertida = 1, fecha_venta = ? WHERE numero = ? AND convertida = 0
          AND EXISTS (SELECT 1 FROM movimientos_stock WHERE cotizacion = ? AND motivo = 'venta') RETURNING numero`).bind(f, num, num),
      marcarCambio(db, f, "EXISTS (SELECT 1 FROM movimientos_stock WHERE cotizacion = ? AND motivo = 'venta' AND fecha = ?)", [num, f]),
    ]);
    if (!u.results.length) return error(409, "El stock o la cotización cambiaron mientras se marcaba la venta. Vuelva a cargar la lista e intente de nuevo.");
    return json({ numero: num, convertida: 1, repuesto_id: cot.repuesto_id, cantidad: cot.cantidad, stock_antes: antes, stock_despues: despues, forzada: despues < 0 });
  }

  // Ventas que salieron de cotizaciones, para el tablero de clientes (SCRUM-76).
  if (ruta === "/api/ventas-clientes" && m === "GET") {
    await exigir(env, req, "importador");
    const db = await base(env);
    // Las cotizaciones de la tienda llegan sin cliente registrado: sus ventas se suman a un cliente aparte, «Tienda
    // web (sin cuenta)», en vez de perderse (auditoría del 24-11-2026, error E2).
    const f = (await db.prepare("SELECT fecha_venta, repuesto_id, COALESCE(cliente_id, ?) AS cliente_id, cantidad FROM cotizaciones WHERE convertida = 1 ORDER BY numero").bind(CLIENTE_WEB).all()).results;
    return json(f.map(x => [x.fecha_venta.slice(0, 7), x.repuesto_id, x.cliente_id, x.cantidad]));
  }

  // SCRUM-77: alta de clientes y carga de repuestos.
  if (ruta === "/api/clientes" && m === "GET") {
    await exigir(env, req, "importador");
    const db = await base(env);
    return json((await db.prepare("SELECT * FROM clientes ORDER BY cliente_id").all()).results);
  }
  if (ruta === "/api/clientes" && m === "POST") {
    await exigir(env, req, "importador");
    const b = await leerJson(req);
    const db = await base(env);
    const nombre = texto(b.nombre, "El nombre", 80, true);
    const tipo = texto(b.tipo, "El tipo", 40, true);
    const zona = texto(b.zona, "La zona", 40, true);
    if (!TIPOS_CLIENTE.includes(tipo)) return error(400, "El tipo debe ser uno de: " + TIPOS_CLIENTE.join(", ") + ".");
    const [id] = await siguientes(db, "clientes", "clientes", "cliente_id", "CLI-N");
    const f = ahora();
    await db.batch([db.prepare("INSERT INTO clientes (cliente_id, nombre, tipo, zona, alta) VALUES (?, ?, ?, ?, ?)").bind(id, nombre, tipo, zona, f), marcarCambio(db, f)]);
    return json({ cliente_id: id, nombre: nombre, tipo: tipo, zona: zona }, 201);
  }
  if (ruta === "/api/repuestos" && m === "POST") {
    await exigir(env, req, "importador");
    const b = await leerJson(req);
    const db = await base(env);
    const v = validarRepuesto(b, true);
    const [id] = await siguientes(db, "repuestos", "repuestos", "repuesto_id", "REP-N");
    const f = ahora();
    await db.batch([db.prepare(`INSERT INTO repuestos (repuesto_id, nombre, categoria, descripcion, costo_unitario_usd, margen_pct, stock,
        proveedor_id, fecha_ingreso, alta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind(id, v.nombre, v.categoria, v.descripcion, v.costo_unitario_usd, v.margen_pct, v.stock, v.proveedor_id, v.fecha_ingreso, f), marcarCambio(db, f)]);
    return json({ repuesto_id: id, nombre: v.nombre }, 201);
  }

  // D8: ajustes del importador a los repuestos del dataset, ya aplicados (nombre, categoría, descripción, costo,
  // margen, precio y proveedor). Público, como el resto del catálogo: la tienda los necesita para mostrar el precio.
  if (ruta === "/api/ajustes" && m === "GET") {
    const est = await leerEstado(await base(env)), d = datosCon(est);
    return json(Object.keys(est.ajustes).sort().filter(id => DATOS.repuestos.some(r => r.repuesto_id === id)).map(id => {
      const r = d.repuestos.find(x => x.repuesto_id === id), c = d.catalogo.repuestos.find(x => x.repuesto_id === id) || {};
      return { repuesto_id: id, nombre: c.nombre, categoria: c.categoria, descripcion: c.descripcion, costo_unitario_usd: r.costo_unitario_usd,
        margen_pct: r.margen_pct, costo_puesto_usd: r.costo_puesto_usd, precio_venta_usd: r.precio_venta_usd, proveedor_id: r.proveedor_id,
        modificado: est.ajustes[id].modificado };
    }));
  }

  // D8: plantilla para la carga masiva, con los repuestos actuales. El stock va vacío: una celda vacía no cambia nada,
  // y así una plantilla vieja no deshace las ventas registradas después de bajarla.
  if (ruta === "/api/repuestos/plantilla.csv" && m === "GET") {
    await exigir(env, req, "importador");
    const est = await leerEstado(await base(env));
    const ids = DATOS.repuestos.map(r => r.repuesto_id).concat(est.cargados.map(r => r.repuesto_id));
    const filas = ids.map(id => { const a = actual(est, id);
      return [id, a.nombre, a.categoria, a.descripcion, a.costo_unitario_usd, a.margen_pct, "", a.proveedor_id, ""].map(celdaCsv).join(","); });
    return new Response("\uFEFF" + [COLS_CSV.join(",")].concat(filas).join("\r\n") + "\r\n", { headers: { "content-type": "text/csv; charset=utf-8",
      "content-disposition": 'attachment; filename="plantilla_repuestos.csv"', "cache-control": "no-store", "x-content-type-options": "nosniff" } });
  }

  // D8: carga masiva por CSV. Sin ?aplicar=1 solo revisa y devuelve el informe por fila. Con ?aplicar=1 vuelve a
  // revisar todo y, solo si no hay ningún error, escribe todas las filas en una db.batch (todo o nada).
  if (ruta === "/api/repuestos/csv" && m === "POST") {
    const s = await exigir(env, req, "importador");
    if (Number(req.headers.get("content-length") || 0) > MAX_CSV) throw new ErrorPedido(413, `El archivo pesa más de ${MAX_CSV / 1024} KB. Divídalo en partes.`);
    const t = await req.text();
    if (t.length > MAX_CSV) throw new ErrorPedido(413, `El archivo pesa más de ${MAX_CSV / 1024} KB. Divídalo en partes.`);
    const db = await base(env);
    const est = await leerEstado(db);
    const r = await revisarCsv(db, est, t, s.u);
    const resumen = { filas: r.informe, errores: r.errores, altas: r.altas.length,
      ediciones: r.informe.filter(x => x.accion === "edición" && !x.error).length, sin_cambios: r.informe.filter(x => x.accion === "sin cambios").length };
    if (url.searchParams.get("aplicar") !== "1") return json(Object.assign({ aplicado: false }, resumen));
    if (r.errores) return json(Object.assign({ aplicado: false, error: `No se aplicó nada: ${r.errores} ${r.errores === 1 ? "fila tiene" : "filas tienen"} errores.` }, resumen), 422);
    const stmts = r.stmts.slice();
    if (r.altas.length) {
      const ids = await siguientes(db, "repuestos", "repuestos", "repuesto_id", "REP-N", r.altas.length);
      r.altas.forEach((x, i) => { x.res.repuesto_id = ids[i]; const v = x.v;
        stmts.push(db.prepare(`INSERT INTO repuestos (repuesto_id, nombre, categoria, descripcion, costo_unitario_usd, margen_pct, stock,
            proveedor_id, fecha_ingreso, alta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind(ids[i], v.nombre, v.categoria, v.descripcion, v.costo_unitario_usd, v.margen_pct, v.stock, v.proveedor_id, v.fecha_ingreso, r.fecha)); });
    }
    if (stmts.length) await db.batch(stmts.concat([marcarCambio(db, r.fecha)]));
    return json(Object.assign({ aplicado: true }, resumen));
  }

  // D8: edición de un repuesto, del dataset o cargado. Solo los campos de EDITABLES; el stock es el vigente deseado y
  // se registra como un movimiento «ajuste» por la diferencia.
  const edicion = ruta.match(/^\/api\/repuestos\/(REP-[A-Z0-9]{1,12})$/);
  if (edicion && m === "PATCH") {
    const s = await exigir(env, req, "importador");
    const b = await leerJson(req);
    const otros = Object.keys(b).filter(k => !EDITABLES.includes(k));
    if (otros.length) return error(400, "No se puede editar: " + otros.join(", ") + ". Campos editables: " + EDITABLES.join(", ") + ".");
    const db = await base(env);
    const est = await leerEstado(db), id = edicion[1];
    if (!actual(est, id)) return error(404, "No existe ese repuesto.");
    const v = validarRepuesto(b, false, k => k in b && b[k] !== null);
    if (!Object.keys(v).length) return error(400, "No hay ningún campo para cambiar.");
    const f = ahora(), plan = planEdicion(db, est, id, v, s.u, f);
    if (plan.stmts.length) await db.batch(plan.stmts.concat([marcarCambio(db, f)]));
    return json({ repuesto_id: id, cambios: plan.cambios });
  }

  // SCRUM-78: el proveedor ve solo sus repuestos, su estado y lo que se le pediría.
  if (ruta === "/api/proveedor" && m === "GET") {
    const s = await exigir(env, req, "proveedor");
    const db = await base(env);
    const d = datosCon(await leerEstado(db));
    const tc = await dolar();
    const al = Motor.alertas(d, tc.valor).filter(a => {
      const r = d.repuestos.find(x => x.repuesto_id === a.id);
      return r && r.proveedor_id === s.prov;
    });
    const p = DATOS.proveedores.find(x => x.proveedor_id === s.prov);
    return json({ proveedor: { proveedor_id: p.proveedor_id, nombre: p.nombre, origen: p.origen, incoterm: p.incoterm,
      plazo_normal_dias: p.plazo_normal_dias, pct_entregas_a_tiempo: p.pct_entregas_a_tiempo }, repuestos: al, tc: tc });
  }

  return error(404, "No existe esa dirección.");
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    try {
      await cargarRecursos(env);
      if (url.pathname.startsWith("/api/")) return await api(req, env, url);
      if (req.method !== "GET" && req.method !== "HEAD") return error(405, "Método no permitido.");
      // Catálogos PDF, publicados junto al servidor como archivos estáticos de Pages (auditoría, error E3).
      if (/^\/catalogos\/[a-z0-9_]+\.pdf$/.test(url.pathname)) {
        if (!env.ASSETS) return error(404, "No existe ese catálogo.");
        return env.ASSETS.fetch(req);
      }
      // «/» es la tienda pública (mejora del sitio de MULTIPARTES); «/empresa» es la app del importador y el
      // proveedor. Qué pantallas ve cada rol lo decide la sesión, y cada dato guardado lo protege la API. El
      // marcador PORTAL hace que las dos páginas hablen con este servidor. Es un prototipo: no se indexa.
      const empresa = url.pathname === "/empresa" || url.pathname.startsWith("/empresa/");
      if (!empresa && url.pathname !== "/" && url.pathname !== "/index.html") return error(404, "No existe esa página.");
      const html = (empresa ? APP_HTML : TIENDA_HTML).replace("</head>", "<script>window.PORTAL=1</script></head>");
      return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache", "x-content-type-options": "nosniff",
        "referrer-policy": "same-origin", "x-robots-tag": "noindex, nofollow" } });
    } catch (e) {
      if (e instanceof ErrorPedido) return error(e.status, e.message);
      return error(500, "Error del servidor.");
    }
  },
};
