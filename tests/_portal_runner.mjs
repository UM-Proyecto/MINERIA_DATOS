// Corre el servidor del portal (build/_worker.js) contra una D1 simulada con node:sqlite y devuelve lo que respondió
// cada pedido. Lo usa tests/test_portal.py. Uso: node _portal_runner.mjs RUTA_WORKER
import { DatabaseSync } from "node:sqlite";
import { pathToFileURL } from "node:url";

const RUTA = process.argv[2];
const n = v => (v === undefined ? null : v);
function d1() {
  const db = new DatabaseSync(":memory:");
  class Stmt {
    constructor(sql, args) { this.sql = sql; this.args = args || []; }
    bind(...a) { return new Stmt(this.sql, a); }
    p() { return db.prepare(this.sql); }
    async all() { return { results: this.p().all(...this.args.map(n)).map(r => ({ ...r })) }; }
    async first() { const r = this.p().get(...this.args.map(n)); return r === undefined ? null : { ...r }; }
    async run() { this.p().run(...this.args.map(n)); return { success: true }; }
  }
  return { prepare: sql => new Stmt(sql), batch: async ss => { for (const s of ss) db.prepare(s.sql).run(...s.args.map(n)); return []; } };
}

import { readFileSync } from "node:fs";
const [LIVIANO, DATOS_LOCAL, HTML_LOCAL] = process.argv.slice(3);
let modo = "csv";
globalThis.fetch = async url => {
  if (modo === "falla") throw new Error("sin red");
  url = String(url);
  if (url.endsWith("/datos_app.json")) return modo === "github_404" ? new Response("no", { status: 404 }) : new Response(readFileSync(DATOS_LOCAL));
  if (url.endsWith(".html")) return modo === "github_404" ? new Response("no", { status: 404 }) : new Response(readFileSync(HTML_LOCAL));
  salida.urls = (salida.urls || []).concat(url.replace(/^https:\/\/raw\.githubusercontent\.com\/UM-Proyecto\/MINERIA_DATOS\//, ""));
  return new Response("fecha,tco_bs_por_usd,fuente,fecha_lectura\n2026-11-13,11.67,x,2026-11-13\n2026-11-14,11.65,x,2026-11-14\n");
};

let k = 0;
async function cargar() { k++; return (await import(pathToFileURL(RUTA).href + "?v=" + k)).default; }

const salida = {};
async function pedir(w, env, nombre, metodo, ruta, cuerpo, token, crudo) {
  const h = {};
  if (cuerpo !== undefined) h["content-type"] = "application/json";
  if (token) h.authorization = "Bearer " + token;
  const r = await w.fetch(new Request("https://portal.prueba" + ruta, { method: metodo, headers: h, body: cuerpo === undefined ? undefined : (typeof cuerpo === "string" ? cuerpo : JSON.stringify(cuerpo)) }), env);
  const t = await r.text();
  let b = t; if (!crudo) { try { b = JSON.parse(t); } catch (e) {} }
  salida[nombre] = { status: r.status, tipo: r.headers.get("content-type"), cuerpo: crudo ? t.slice(0, 20000) : b };
  return salida[nombre];
}

const SEC = "x".repeat(40);
const w = await cargar(), env = { DB: d1(), SECRETO: SEC };
await pedir(w, env, "html", "GET", "/");
salida.html.cuerpo = { portal: String(salida.html.cuerpo).includes("window.PORTAL=1"), largo: String(salida.html.cuerpo).length };
await pedir(w, env, "post_raiz", "POST", "/", {});
await pedir(w, env, "no_existe", "GET", "/api/no-existe");
await pedir(w, env, "tc", "GET", "/api/tc");
await pedir(w, env, "cot1", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 10, cliente_nombre: "  Taller   Prueba ", total_bs: 1, precio_lista_bs: 1 });
await pedir(w, env, "cot_cero", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 0 });
await pedir(w, env, "cot_decimal", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 2.5 });
await pedir(w, env, "cot_rep_mal", "POST", "/api/cotizaciones", { repuesto_id: "REP-9999", cantidad: 1 });
await pedir(w, env, "cot_cli_mal", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 1, cliente_id: "CLI-99" });
await pedir(w, env, "cot_json_mal", "POST", "/api/cotizaciones", "{no es json");
await pedir(w, env, "cot_grande", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 1, x: "a".repeat(9000) });
await pedir(w, env, "cot_cli", "POST", "/api/cotizaciones", { repuesto_id: "REP-0001", cantidad: 3, cliente_id: "CLI-01" });

await pedir(w, env, "lista_anon", "GET", "/api/cotizaciones");
await pedir(w, env, "entrar_mal", "POST", "/api/entrar", { usuario: "importador", clave: "otra" });
const imp = (await pedir(w, env, "entrar_imp", "POST", "/api/entrar", { usuario: "Importador ", clave: "demo-importador" })).cuerpo.token;
const prov = (await pedir(w, env, "entrar_prov", "POST", "/api/entrar", { usuario: "proveedor", clave: "demo-proveedor" })).cuerpo.token;
await pedir(w, env, "yo_imp", "GET", "/api/yo", undefined, imp);
const [p1, f1] = imp.split(".");
const falso = Buffer.from(JSON.stringify({ u: "importador", rol: "importador", exp: 9e9 })).toString("base64url") + "." + f1;
await pedir(w, env, "yo_falso", "GET", "/api/yo", undefined, falso);
await pedir(w, env, "lista_prov", "GET", "/api/cotizaciones", undefined, prov);
await pedir(w, env, "lista_imp", "GET", "/api/cotizaciones", undefined, imp);
await pedir(w, env, "lista_mes_mal", "GET", "/api/cotizaciones?mes=2026-1", undefined, imp);
await pedir(w, env, "lista_rep", "GET", "/api/cotizaciones?repuesto=REP-0001", undefined, imp);

await pedir(w, env, "cli_anon", "POST", "/api/clientes", { nombre: "A", tipo: "Particular", zona: "Sur" });
await pedir(w, env, "cli_prov", "POST", "/api/clientes", { nombre: "A", tipo: "Particular", zona: "Sur" }, prov);
await pedir(w, env, "cli_tipo_mal", "POST", "/api/clientes", { nombre: "A", tipo: "Otro", zona: "Sur" }, imp);
await pedir(w, env, "cli_ok", "POST", "/api/clientes", { nombre: "Taller Nuevo", tipo: "Taller mecánico", zona: "Norte" }, imp);
await pedir(w, env, "clientes", "GET", "/api/clientes", undefined, imp);

await pedir(w, env, "rep_neg", "POST", "/api/repuestos", { nombre: "X", categoria: "Y", costo_unitario_usd: 10, margen_pct: 35, stock: -1, proveedor_id: "PROV-CN-03", fecha_ingreso: "2026-11-13" }, imp);
await pedir(w, env, "rep_fecha_mal", "POST", "/api/repuestos", { nombre: "X", categoria: "Y", costo_unitario_usd: 10, margen_pct: 35, stock: 1, proveedor_id: "PROV-CN-03", fecha_ingreso: "13/11/2026" }, imp);
await pedir(w, env, "rep_prov_mal", "POST", "/api/repuestos", { nombre: "X", categoria: "Y", costo_unitario_usd: 10, margen_pct: 35, stock: 1, proveedor_id: "PROV-XX", fecha_ingreso: "2026-11-13" }, imp);
await pedir(w, env, "rep_vacio", "POST", "/api/repuestos", { nombre: " ", categoria: "Y", costo_unitario_usd: 10, margen_pct: 35, stock: 1, proveedor_id: "PROV-CN-03", fecha_ingreso: "2026-11-13" }, imp);
await pedir(w, env, "rep_ok", "POST", "/api/repuestos", { nombre: "Filtro de aire para motor 1.6", categoria: "Filtro de aire", descripcion: "Filtra el aire.", costo_unitario_usd: 8.5, margen_pct: 40, stock: 0, proveedor_id: "PROV-CN-03", fecha_ingreso: "2026-11-13" }, imp);
await pedir(w, env, "repuestos_pub", "GET", "/api/repuestos");
await pedir(w, env, "cot_nuevo", "POST", "/api/cotizaciones", { repuesto_id: "REP-N001", cantidad: 12 });
await pedir(w, env, "miprov", "GET", "/api/proveedor", undefined, prov);
await pedir(w, env, "miprov_imp", "GET", "/api/proveedor", undefined, imp);

await pedir(w, env, "venta_prov", "POST", "/api/cotizaciones/2/venta", {}, prov);
await pedir(w, env, "venta", "POST", "/api/cotizaciones/2/venta", {}, imp);
await pedir(w, env, "venta_otra_vez", "POST", "/api/cotizaciones/2/venta", {}, imp);
await pedir(w, env, "ventas_cli", "GET", "/api/ventas-clientes", undefined, imp);
await pedir(w, env, "csv", "GET", "/api/cotizaciones?formato=csv", undefined, imp, true);

// Otra clave de sesión: el token del servidor anterior no sirve.
const w2 = await cargar();
await pedir(w2, { DB: d1(), SECRETO: "y".repeat(40) }, "otra_clave", "GET", "/api/yo", undefined, imp);
await pedir(w2, { DB: d1() }, "sin_secreto", "POST", "/api/entrar", { usuario: "importador", clave: "demo-importador" });
modo = "falla";
const w3 = await cargar();
await pedir(w3, { DB: d1(), SECRETO: SEC }, "tc_sin_red", "GET", "/api/tc");

// Versión liviana: lee datos y app de GitHub (simulado). Primero con GitHub caído, después funcionando.
if (LIVIANO) {
  modo = "github_404";
  const l1 = (await import(pathToFileURL(LIVIANO).href + "?v=l1")).default;
  await pedir(l1, { DB: d1(), SECRETO: SEC, FUENTE_REF: "rama-x" }, "liv_caido", "GET", "/");
  modo = "csv";
  const l2 = (await import(pathToFileURL(LIVIANO).href + "?v=l2")).default;
  const env2 = { DB: d1(), SECRETO: SEC, FUENTE_REF: "rama-x" };
  await pedir(l2, env2, "liv_html", "GET", "/");
  salida.liv_html.cuerpo = { portal: String(salida.liv_html.cuerpo).includes("window.PORTAL=1") };
  await pedir(l2, env2, "liv_cot", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 10 });
}
process.stdout.write(JSON.stringify(salida));
