/*
 * Servidor del portal de MULTIPARTES (SCRUM-73, SCRUM-77 y SCRUM-78), para Cloudflare Pages en modo avanzado
 * (_worker.js) con una base D1.
 *
 * armar_portal.py antepone a este archivo el motor del simulador (motor.js) y dos constantes, DATOS (datos_app.json)
 * y APP_HTML (la app generada). El servidor:
 *  - sirve la app en «/» marcada como portal;
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
const TC_URL = "https://raw.githubusercontent.com/UM-Proyecto/MINERIA_DATOS/main/data/processed/scrum-54/tco_bcb_diario.csv";
const TIPOS_CLIENTE = ["Taller mecánico", "Flota de empresa", "Repuestera", "Particular"];

const ESQUEMA = [
  `CREATE TABLE IF NOT EXISTS cotizaciones (
     numero INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, cliente_id TEXT, cliente_nombre TEXT,
     repuesto_id TEXT NOT NULL, cantidad INTEGER NOT NULL CHECK (cantidad >= 1), tc REAL NOT NULL, tc_fecha TEXT NOT NULL,
     precio_lista_bs REAL NOT NULL, pct_aplicado REAL NOT NULL, total_bs REAL NOT NULL,
     convertida INTEGER NOT NULL DEFAULT 0, fecha_venta TEXT)`,
  `CREATE TABLE IF NOT EXISTS clientes (
     cliente_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, tipo TEXT NOT NULL, zona TEXT NOT NULL, alta TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS repuestos (
     repuesto_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, categoria TEXT NOT NULL, descripcion TEXT NOT NULL,
     costo_unitario_usd REAL NOT NULL, margen_pct REAL NOT NULL, stock INTEGER NOT NULL, proveedor_id TEXT NOT NULL,
     fecha_ingreso TEXT NOT NULL, alta TEXT NOT NULL)`,
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

let esquemaListo = false;
async function base(env) {
  if (!env.DB) throw new ErrorPedido(500, "El servidor no tiene la base de datos conectada.");
  if (!esquemaListo) {
    await env.DB.batch(ESQUEMA.map(sql => env.DB.prepare(sql)));
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

async function repuestosCargados(db) {
  return (await db.prepare("SELECT * FROM repuestos ORDER BY repuesto_id").all()).results;
}

// Convierte un repuesto cargado al formato del motor. Sin historial de venta, sin punto de pedido ni en camino:
// el motor lo marca «Sin datos» en las alertas en vez de inventar esas cifras.
function comoRepuesto(r) {
  const prov = DATOS.proveedores.find(p => p.proveedor_id === r.proveedor_id) || {};
  return {
    repuesto_id: r.repuesto_id, codigo_carparts: "", tipo_demanda: "sin historial", clase_abc: "C",
    proveedor_id: r.proveedor_id, proveedor: prov.nombre || r.proveedor_id, origen: prov.origen || "",
    incoterm: prov.incoterm || "", plazo_normal_dias: prov.plazo_normal_dias,
    costo_unitario_usd: r.costo_unitario_usd, margen_pct: r.margen_pct,
    precio_venta_usd: Math.round(r.costo_unitario_usd * (1 + r.margen_pct / 100) * 100) / 100,
    stock_al_2026_11_10: r.stock, en_transito_al_2026_11_10: 0, punto_pedido_s: "", nivel_maximo_S: "",
    cargado: true, fecha_ingreso: r.fecha_ingreso,
  };
}

function datosCon(cargados) {
  const d = Object.assign({}, DATOS);
  d.repuestos = DATOS.repuestos.concat(cargados.map(comoRepuesto));
  return d;
}

async function existeCliente(db, id) {
  if (DATOS.clientes.lista.some(c => c.cliente_id === id)) return true;
  return !!(await db.prepare("SELECT 1 FROM clientes WHERE cliente_id = ?").bind(id).first());
}

// ------------------------------------------------------------------ rutas

async function api(req, env, url) {
  const ruta = url.pathname, m = req.method;

  if (ruta === "/api/salud" && m === "GET") return json({ ok: true });
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
    const db = await base(env);
    return json((await repuestosCargados(db)).map(r => ({
      repuesto_id: r.repuesto_id, nombre: r.nombre, categoria: r.categoria, descripcion: r.descripcion,
      precio_venta_usd: comoRepuesto(r).precio_venta_usd, stock: r.stock, proveedor_id: r.proveedor_id, fecha_ingreso: r.fecha_ingreso,
    })));
  }

  // SCRUM-73: cada cotización se guarda sola al emitirse. El cliente no necesita cuenta.
  if (ruta === "/api/cotizaciones" && m === "POST") {
    const b = await leerJson(req);
    const db = await base(env);
    const repId = texto(b.repuesto_id, "el repuesto", 20, true);
    const cantidad = numero(b.cantidad, "La cantidad", 1, 100000, true);
    const clienteId = texto(b.cliente_id, "el cliente", 20, false);
    const nombre = texto(b.cliente_nombre, "El nombre del cliente", 80, false);
    if (clienteId && !(await existeCliente(db, clienteId))) return error(400, "Ese cliente no existe.");
    const d = datosCon(await repuestosCargados(db));
    if (!d.repuestos.some(r => r.repuesto_id === repId)) return error(400, "Ese repuesto no existe.");
    const tc = await dolar();
    const c = Motor.cotizar(d, repId, cantidad, tc.valor);
    const r = await db.prepare(`INSERT INTO cotizaciones (fecha, cliente_id, cliente_nombre, repuesto_id, cantidad, tc, tc_fecha,
        precio_lista_bs, pct_aplicado, total_bs) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING numero, fecha`)
      .bind(ahora(), clienteId, nombre, repId, cantidad, tc.valor, tc.fecha, c.precio_lista_bs, c.pct_aplicado, c.total_bs).first();
    return json(Object.assign({ numero: r.numero, fecha: r.fecha, tc_fecha: tc.fecha }, c), 201);
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
      const cols = ["numero", "fecha", "cliente_id", "cliente_nombre", "repuesto_id", "cantidad", "tc", "tc_fecha", "precio_lista_bs", "pct_aplicado", "total_bs", "convertida", "fecha_venta"];
      const celda = v => { const s = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
      const csv = [cols.join(",")].concat(filas.map(f => cols.map(c => celda(f[c])).join(","))).join("\n") + "\n";
      return new Response(csv, { headers: { "content-type": "text/csv; charset=utf-8", "content-disposition": 'attachment; filename="cotizaciones.csv"', "cache-control": "no-store" } });
    }
    const tot = await db.prepare("SELECT COUNT(*) AS n, SUM(convertida) AS v FROM cotizaciones").first();
    return json({ filas: filas, total: tot.n || 0, convertidas: tot.v || 0, no_convertidas: (tot.n || 0) - (tot.v || 0) });
  }
  const venta = ruta.match(/^\/api\/cotizaciones\/(\d+)\/venta$/);
  if (venta && m === "POST") {
    await exigir(env, req, "importador");
    const db = await base(env);
    const r = await db.prepare("UPDATE cotizaciones SET convertida = 1, fecha_venta = ? WHERE numero = ? AND convertida = 0 RETURNING numero")
      .bind(ahora(), Number(venta[1])).first();
    if (!r) return error(404, "No existe esa cotización o ya estaba marcada como venta.");
    return json({ numero: r.numero, convertida: 1 });
  }

  // Ventas que salieron de cotizaciones, para el tablero de clientes (SCRUM-76).
  if (ruta === "/api/ventas-clientes" && m === "GET") {
    await exigir(env, req, "importador");
    const db = await base(env);
    const f = (await db.prepare("SELECT fecha_venta, repuesto_id, cliente_id, cantidad FROM cotizaciones WHERE convertida = 1 AND cliente_id IS NOT NULL ORDER BY numero").all()).results;
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
    const n = await db.prepare("SELECT COUNT(*) AS n FROM clientes").first();
    const id = "CLI-N" + String((n.n || 0) + 1).padStart(3, "0");
    await db.prepare("INSERT INTO clientes (cliente_id, nombre, tipo, zona, alta) VALUES (?, ?, ?, ?, ?)").bind(id, nombre, tipo, zona, ahora()).run();
    return json({ cliente_id: id, nombre: nombre, tipo: tipo, zona: zona }, 201);
  }
  if (ruta === "/api/repuestos" && m === "POST") {
    await exigir(env, req, "importador");
    const b = await leerJson(req);
    const db = await base(env);
    const nombre = texto(b.nombre, "El nombre", 80, true);
    const categoria = texto(b.categoria, "La categoría", 60, true);
    const descripcion = texto(b.descripcion, "La descripción", 200, false) || "";
    const costo = numero(b.costo_unitario_usd, "El costo en USD", 0.01, 100000, false);
    const margen = numero(b.margen_pct, "El margen", 0, 300, false);
    const stock = numero(b.stock, "El stock", 0, 1000000, true);
    const prov = texto(b.proveedor_id, "el proveedor", 20, true);
    const fecha = texto(b.fecha_ingreso, "La fecha de ingreso", 10, true);
    if (!DATOS.proveedores.some(p => p.proveedor_id === prov)) return error(400, "Ese proveedor no existe.");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha) || isNaN(Date.parse(fecha + "T00:00:00Z"))) return error(400, "La fecha va como AAAA-MM-DD.");
    const n = await db.prepare("SELECT COUNT(*) AS n FROM repuestos").first();
    const id = "REP-N" + String((n.n || 0) + 1).padStart(3, "0");
    await db.prepare(`INSERT INTO repuestos (repuesto_id, nombre, categoria, descripcion, costo_unitario_usd, margen_pct, stock,
        proveedor_id, fecha_ingreso, alta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind(id, nombre, categoria, descripcion, costo, margen, stock, prov, fecha, ahora()).run();
    return json({ repuesto_id: id, nombre: nombre }, 201);
  }

  // SCRUM-78: el proveedor ve solo sus repuestos, su estado y lo que se le pediría.
  if (ruta === "/api/proveedor" && m === "GET") {
    const s = await exigir(env, req, "proveedor");
    const db = await base(env);
    const d = datosCon(await repuestosCargados(db));
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
      if (url.pathname.startsWith("/api/")) return await api(req, env, url);
      if (req.method !== "GET" && req.method !== "HEAD") return error(405, "Método no permitido.");
      // La app es la misma para todos; qué pantallas ve cada rol lo decide la sesión, y cada dato guardado lo
      // protege la API. El marcador PORTAL hace que la app hable con este servidor.
      const html = APP_HTML.replace("</head>", "<script>window.PORTAL=1</script></head>");
      return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache", "x-content-type-options": "nosniff", "referrer-policy": "same-origin" } });
    } catch (e) {
      if (e instanceof ErrorPedido) return error(e.status, e.message);
      return error(500, "Error del servidor.");
    }
  },
};
