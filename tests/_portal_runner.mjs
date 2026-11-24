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
  return { prepare: sql => new Stmt(sql), batch: async ss => {
    // Como D1: todas las sentencias en una transacción (si una falla, no queda ninguna) y un resultado por sentencia.
    db.exec("BEGIN");
    try { const r = ss.map(s => ({ results: db.prepare(s.sql).all(...s.args.map(n)).map(x => ({ ...x })), success: true })); db.exec("COMMIT"); return r; }
    catch (e) { db.exec("ROLLBACK"); throw e; } } };
}

import { readFileSync } from "node:fs";
const [LIVIANO, DATOS_LOCAL, HTML_LOCAL, TIENDA_LOCAL] = process.argv.slice(3);
let modo = "csv";
globalThis.fetch = async url => {
  if (modo === "falla") throw new Error("sin red");
  url = String(url);
  if (url.endsWith("/datos_app.json")) return modo === "github_404" ? new Response("no", { status: 404 }) : new Response(readFileSync(DATOS_LOCAL));
  if (url.endsWith("/MULTIPARTES_Tienda.html")) return modo === "github_404" ? new Response("no", { status: 404 }) : new Response(readFileSync(TIENDA_LOCAL));
  if (url.endsWith(".html")) return modo === "github_404" ? new Response("no", { status: 404 }) : new Response(readFileSync(HTML_LOCAL));
  salida.urls = (salida.urls || []).concat(url.replace(/^https:\/\/raw\.githubusercontent\.com\/UM-Proyecto\/MINERIA_DATOS\//, ""));
  // La última fila del CSV imitado lleva la fecha del dólar incrustado (el worker solo toma el del repositorio si no es
  // más viejo) y un valor distinto, 11,65, para saber de dónde salió. Antes era el 14-11 fijo y caducó con el dato del 17-11.
  const f = JSON.parse(readFileSync(DATOS_LOCAL, "utf-8")).tc.oficial.fecha;
  return new Response(`fecha,tco_bs_por_usd,fuente,fecha_lectura\n2026-11-13,11.67,x,2026-11-13\n${f},11.65,x,${f}\n`);
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
  salida[nombre] = { status: r.status, tipo: r.headers.get("content-type"), robots: r.headers.get("x-robots-tag"), cuerpo: crudo ? t.slice(0, 20000) : b };
  return salida[nombre];
}

const SEC = "x".repeat(40);
const w = await cargar(), env = { DB: d1(), SECRETO: SEC };
const marcas = x => ({ portal: String(x).includes("window.PORTAL=1"), tienda: String(x).includes('<div class="proto" role="note">'), empresa: String(x).includes('id="v-entrar"') });
await pedir(w, env, "html", "GET", "/");
salida.html.cuerpo = marcas(salida.html.cuerpo);
await pedir(w, env, "empresa", "GET", "/empresa");
salida.empresa.cuerpo = marcas(salida.empresa.cuerpo);
await pedir(w, env, "empresa_barra", "GET", "/empresa/");
salida.empresa_barra.cuerpo = marcas(salida.empresa_barra.cuerpo);
await pedir(w, env, "pagina_rara", "GET", "/otra-cosa");
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
// SCRUM-83: correo de la cotización (envío de demostración: solo se registra).
await pedir(w, env, "cot_correo", "POST", "/api/cotizaciones", { repuesto_id: "REP-0019", cantidad: 12, cliente_nombre: "Taller El Cruce", correo: "  compras@tallerelcruce.com " });
await pedir(w, env, "cot_correo_mal", "POST", "/api/cotizaciones", { repuesto_id: "REP-0019", cantidad: 12, correo: "compras@taller" });
await pedir(w, env, "cot_correo_largo", "POST", "/api/cotizaciones", { repuesto_id: "REP-0019", cantidad: 1, correo: "a".repeat(120) + "@x.com" });
// Migración: una base creada antes de SCRUM-83 (sin las columnas de correo) las recibe sin perder lo que tenía.
{
  const vieja = d1();
  await vieja.prepare(`CREATE TABLE cotizaciones (numero INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, cliente_id TEXT, cliente_nombre TEXT,
     repuesto_id TEXT NOT NULL, cantidad INTEGER NOT NULL CHECK (cantidad >= 1), tc REAL NOT NULL, tc_fecha TEXT NOT NULL,
     precio_lista_bs REAL NOT NULL, pct_aplicado REAL NOT NULL, total_bs REAL NOT NULL, convertida INTEGER NOT NULL DEFAULT 0, fecha_venta TEXT)`).run();
  await vieja.prepare("INSERT INTO cotizaciones (fecha, repuesto_id, cantidad, tc, tc_fecha, precio_lista_bs, pct_aplicado, total_bs) VALUES ('2026-11-15T10:00:00Z', 'REP-0001', 2, 11.67, '2026-11-13', 400, 0, 800)").run();
  const w3 = await cargar();
  await pedir(w3, { DB: vieja, SECRETO: SEC }, "cot_migrada", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 1, correo: "a@b.co" });
  salida.migracion = {
    columnas: (await vieja.prepare("PRAGMA table_info(cotizaciones)").all()).results.map(c => c.name),
    filas: (await vieja.prepare("SELECT numero, correo FROM cotizaciones ORDER BY numero").all()).results,
  };
}

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
await pedir(w, env, "rep_ok", "POST", "/api/repuestos", { nombre: "Filtro de aceite para motor 1.6", categoria: "Filtro de aceite", descripcion: "Filtra el aire.", costo_unitario_usd: 8.5, margen_pct: 40, stock: 0, proveedor_id: "PROV-CN-03", fecha_ingreso: "2026-11-13" }, imp);
await pedir(w, env, "repuestos_pub", "GET", "/api/repuestos");
await pedir(w, env, "cot_nuevo", "POST", "/api/cotizaciones", { repuesto_id: "REP-N001", cantidad: 12 });
await pedir(w, env, "miprov", "GET", "/api/proveedor", undefined, prov);
await pedir(w, env, "miprov_imp", "GET", "/api/proveedor", undefined, imp);

await pedir(w, env, "venta_prov", "POST", "/api/cotizaciones/2/venta", {}, prov);
await pedir(w, env, "venta", "POST", "/api/cotizaciones/2/venta", {}, imp);
await pedir(w, env, "venta_otra_vez", "POST", "/api/cotizaciones/2/venta", {}, imp);
await pedir(w, env, "ventas_cli", "GET", "/api/ventas-clientes", undefined, imp);
// Error E2 (auditoría del 24-11-2026): la cotización 1 salió de la tienda, sin cliente. Su venta tiene que llegar al
// tablero de clientes con el cliente aparte CLI-WEB, en vez de perderse.
await pedir(w, env, "venta_web", "POST", "/api/cotizaciones/1/venta", {}, imp);
await pedir(w, env, "ventas_cli_web", "GET", "/api/ventas-clientes", undefined, imp);
await pedir(w, env, "csv", "GET", "/api/cotizaciones?formato=csv", undefined, imp, true);
// Error E3: los catálogos PDF se sirven desde el portal (archivos estáticos de Pages, env.ASSETS).
{
  const pedidos = [];
  const envA = { DB: d1(), SECRETO: SEC, ASSETS: { fetch: async req => { pedidos.push(new URL(req.url).pathname); return new Response("%PDF-1.7", { headers: { "content-type": "application/pdf" } }); } } };
  await pedir(w, envA, "pdf_ok", "GET", "/catalogos/catalogo_baja.pdf", undefined, undefined, true);
  await pedir(w, envA, "pdf_raro", "GET", "/catalogos/../_worker.js", undefined, undefined, true);
  await pedir(w, { DB: d1(), SECRETO: SEC }, "pdf_sin_assets", "GET", "/catalogos/catalogo_baja.pdf");
  salida.pdf_pedidos = pedidos;
}

// Códigos correlativos seguros ante borrados: con COUNT(*) + 1, borrar CLI-N001 hacía que el alta siguiente repitiera
// CLI-N002 y la clave primaria fallara con un 500.
await pedir(w, env, "cli_2", "POST", "/api/clientes", { nombre: "Taller Dos", tipo: "Particular", zona: "Sur" }, imp);
await env.DB.prepare("DELETE FROM clientes WHERE cliente_id = 'CLI-N001'").run();
await pedir(w, env, "cli_tras_borrar", "POST", "/api/clientes", { nombre: "Taller Tres", tipo: "Particular", zona: "Sur" }, imp);
const repBase = { categoria: "Filtro de aceite", costo_unitario_usd: 5, margen_pct: 35, stock: 2, proveedor_id: "PROV-CN-03", fecha_ingreso: "2026-11-20" };
await pedir(w, env, "rep_2", "POST", "/api/repuestos", Object.assign({ nombre: "Repuesto dos" }, repBase), imp);
await env.DB.prepare("DELETE FROM repuestos WHERE repuesto_id = 'REP-N001'").run();
await pedir(w, env, "rep_tras_borrar", "POST", "/api/repuestos", Object.assign({ nombre: "Repuesto tres" }, repBase), imp);
// Una base anterior a la tabla secuencias, con altas hechas, sigue desde el máximo existente.
{
  const vieja = d1();
  await vieja.prepare("CREATE TABLE clientes (cliente_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, tipo TEXT NOT NULL, zona TEXT NOT NULL, alta TEXT NOT NULL)").run();
  await vieja.prepare("INSERT INTO clientes VALUES ('CLI-N001','a','Particular','x','2026-11-01'), ('CLI-N007','b','Particular','x','2026-11-01')").run();
  const w4 = await cargar();
  await pedir(w4, { DB: vieja, SECRETO: SEC }, "cli_base_vieja", "POST", "/api/clientes", { nombre: "C", tipo: "Particular", zona: "Sur" }, imp);
}

// D6: marcar la venta descuenta el stock; la cotización sola no. El stock vigente lo ven /api/stock, /api/repuestos,
// el cotizador del servidor y la vista del proveedor.
const stockDe = async (nombre, id) => (await pedir(w, env, nombre, "GET", "/api/stock")).cuerpo.repuestos.find(r => r.repuesto_id === id).stock;
salida.d6 = {};
salida.d6.rep1_tras_venta = await stockDe("stock_1", "REP-0001");          // la venta de la cotización 2 (3 u.) ya descontó
salida.d6.rep5_antes = await stockDe("stock_2", "REP-0005");
const c5 = (await pedir(w, env, "d6_cot5", "POST", "/api/cotizaciones", { repuesto_id: "REP-0005", cantidad: 4 })).cuerpo.numero;
salida.d6.rep5_tras_cotizar = await stockDe("stock_3", "REP-0005");
await pedir(w, env, "d6_venta_justa", "POST", `/api/cotizaciones/${c5}/venta`, {}, imp);
salida.d6.rep5_tras_venta = await stockDe("stock_4", "REP-0005");
const c6 = (await pedir(w, env, "d6_cot6", "POST", "/api/cotizaciones", { repuesto_id: "REP-0005", cantidad: 2 })).cuerpo;
salida.d6.cot_sin_stock = { en_stock: c6.en_stock, por_pedir: c6.por_pedir };
await pedir(w, env, "d6_venta_negativa", "POST", `/api/cotizaciones/${c6.numero}/venta`, {}, imp);
salida.d6.rep5_tras_409 = await stockDe("stock_5", "REP-0005");
salida.d6.cot6_tras_409 = (await pedir(w, env, "d6_lista", "GET", "/api/cotizaciones?repuesto=REP-0005", undefined, imp)).cuerpo.filas.find(f => f.numero === c6.numero).convertida;
await pedir(w, env, "d6_forzar_texto", "POST", `/api/cotizaciones/${c6.numero}/venta`, { forzar: "si" }, imp);
await pedir(w, env, "d6_venta_forzada", "POST", `/api/cotizaciones/${c6.numero}/venta`, { forzar: true }, imp);
salida.d6.rep5_forzado = await stockDe("stock_6", "REP-0005");
await pedir(w, env, "d6_forzada_otra_vez", "POST", `/api/cotizaciones/${c6.numero}/venta`, { forzar: true }, imp);
salida.d6.rep5_final = await stockDe("stock_7", "REP-0005");
const c8 = (await pedir(w, env, "d6_cot_negativo", "POST", "/api/cotizaciones", { repuesto_id: "REP-0005", cantidad: 3 })).cuerpo;
salida.d6.cot_con_negativo = { stock: c8.stock, en_stock: c8.en_stock, por_pedir: c8.por_pedir };
// Repuesto cargado (REP-N002, stock base 2): /api/repuestos muestra el vigente.
const c7 = (await pedir(w, env, "d6_cot7", "POST", "/api/cotizaciones", { repuesto_id: "REP-N002", cantidad: 2 })).cuerpo.numero;
await pedir(w, env, "d6_venta_cargado", "POST", `/api/cotizaciones/${c7}/venta`, {}, imp);
salida.d6.n002_pub = (await pedir(w, env, "d6_rep_pub", "GET", "/api/repuestos")).cuerpo.find(r => r.repuesto_id === "REP-N002").stock;
await pedir(w, env, "d6_miprov", "GET", "/api/proveedor", undefined, prov);
await pedir(w, env, "d6_mov_anon", "GET", "/api/movimientos");
await pedir(w, env, "d6_mov_prov", "GET", "/api/movimientos", undefined, prov);
await pedir(w, env, "d6_mov", "GET", "/api/movimientos?repuesto=REP-0005", undefined, imp);

// D8: edición de repuestos (dataset y cargados) y carga masiva por CSV. Solo el importador.
salida.d8 = {};
await pedir(w, env, "d8_patch_anon", "PATCH", "/api/repuestos/REP-0003", { nombre: "X" });
await pedir(w, env, "d8_patch_prov", "PATCH", "/api/repuestos/REP-0003", { nombre: "X" }, prov);
await pedir(w, env, "d8_patch_cat_mal", "PATCH", "/api/repuestos/REP-0003", { categoria: "Filtro de aire" }, imp);
await pedir(w, env, "d8_patch_campo_mal", "PATCH", "/api/repuestos/REP-0003", { precio_venta_usd: 1 }, imp);
await pedir(w, env, "d8_patch_formula", "PATCH", "/api/repuestos/REP-0003", { nombre: "=HIPERVINCULO(\"x\")" }, imp);
await pedir(w, env, "d8_patch_no_existe", "PATCH", "/api/repuestos/REP-9999", { nombre: "X" }, imp);
await pedir(w, env, "d8_patch_vacio", "PATCH", "/api/repuestos/REP-0003", {}, imp);
await pedir(w, env, "d8_alta_cat_mal", "POST", "/api/repuestos", Object.assign({}, repBase, { nombre: "Otro", categoria: "Filtro de aire" }), imp);
await pedir(w, env, "d8_patch_dataset", "PATCH", "/api/repuestos/REP-0003", { nombre: "Disco de freno ventilado", categoria: "Disco de freno", margen_pct: 50, stock: 2 }, imp);
await pedir(w, env, "d8_patch_igual", "PATCH", "/api/repuestos/REP-0003", { margen_pct: 50, stock: 2 }, imp);
await pedir(w, env, "d8_ajustes", "GET", "/api/ajustes");
salida.d8.rep3_stock = await stockDe("d8_stock_1", "REP-0003");
await pedir(w, env, "d8_mov3", "GET", "/api/movimientos?repuesto=REP-0003", undefined, imp);
await pedir(w, env, "d8_cot3", "POST", "/api/cotizaciones", { repuesto_id: "REP-0003", cantidad: 1 });
await pedir(w, env, "d8_patch_cargado", "PATCH", "/api/repuestos/REP-N002", { nombre: "Repuesto dos corregido", proveedor_id: "PROV-BR-01", stock: 5, descripcion: "" }, imp);
salida.d8.n002 = (await pedir(w, env, "d8_rep_pub", "GET", "/api/repuestos")).cuerpo.find(r => r.repuesto_id === "REP-N002");
await pedir(w, env, "d8_miprov", "GET", "/api/proveedor", undefined, prov);
salida.d8.n002_mod = await env.DB.prepare("SELECT modificado, usuario FROM repuestos WHERE repuesto_id = 'REP-N002'").first();

await pedir(w, env, "d8_plantilla_anon", "GET", "/api/repuestos/plantilla.csv");
await pedir(w, env, "d8_plantilla", "GET", "/api/repuestos/plantilla.csv", undefined, imp, true);
const CAB = "repuesto_id,nombre,categoria,descripcion,costo_unitario_usd,margen_pct,stock,proveedor_id,fecha_ingreso";
const csv = (cuerpo, nombre, aplicar, token) => pedirCsv(nombre, cuerpo, aplicar, token === undefined ? imp : token);
async function pedirCsv(nombre, cuerpo, aplicar, token) {
  const h = { "content-type": "text/csv" }; if (token) h.authorization = "Bearer " + token;
  const r = await w.fetch(new Request("https://portal.prueba/api/repuestos/csv" + (aplicar ? "?aplicar=1" : ""), { method: "POST", headers: h, body: cuerpo }), env);
  salida[nombre] = { status: r.status, cuerpo: await r.json() };
  return salida[nombre];
}
const nRep = async () => (await pedir(w, env, "d8_n", "GET", "/api/repuestos")).cuerpo.length;
salida.d8.n_antes = await nRep();
const malo = [CAB,
  "REP-0004,Nombre nuevo para el cuatro,,,,,,,",
  ",Bujía nueva de prueba,Bujía de encendido,Sirve para probar,3.5,40,12,PROV-CN-03,2026-11-24",
  ",Algo,Filtro de aire,,3,40,1,PROV-CN-03,2026-11-24",
  "REP-0006,,,,,,-1,,",
  "REP-9999,Nada,,,,,,,",
  "REP-0004,Repetido,,,,,,,",
  "REP-0007,,,,,,,,2026-11-01",
  ",=1+1,Disco de freno,,3,40,1,PROV-CN-03,2026-11-24",
  ",Corta,Disco de freno,,3,40,1,PROV-CN-03"].join("\n");
await csv(malo, "d8_csv_malo", true);
salida.d8.n_tras_malo = await nRep();
salida.d8.aj_tras_malo = (await pedir(w, env, "d8_aj2", "GET", "/api/ajustes")).cuerpo.map(a => a.repuesto_id);
salida.d8.rep6_tras_malo = await stockDe("d8_stock_2", "REP-0006");
const bueno = [CAB,
  "REP-0004,Nombre nuevo para el cuatro,,,,,,,",
  "REP-0006,,,,,,9,,",
  "REP-0001,,,,,,,,",
  "REP-N003,,Kit de embrague,\"Texto con coma, y \"\"comillas\"\"\",,,,,",
  ",Bujía nueva de prueba,Bujía de encendido,Sirve para probar,3.5,40,12,PROV-CN-03,2026-11-24",
  ",Otra bujía,Bujía de encendido,,4,35,0,PROV-BR-01,2026-11-24", ""].join("\r\n");
await csv(bueno, "d8_csv_revisar", false);
salida.d8.n_tras_revisar = await nRep();
await csv(bueno, "d8_csv_bueno", true);
salida.d8.n_tras_bueno = await nRep();
salida.d8.pub_tras_bueno = (await pedir(w, env, "d8_rep_pub2", "GET", "/api/repuestos")).cuerpo;
salida.d8.aj_tras_bueno = (await pedir(w, env, "d8_aj3", "GET", "/api/ajustes")).cuerpo;
salida.d8.rep6_tras_bueno = await stockDe("d8_stock_3", "REP-0006");
await csv(bueno, "d8_csv_otra_vez", true);   // las altas ya existen: se rechaza todo
await csv("﻿repuesto_id;nombre;categoria;descripcion;costo_unitario_usd;margen_pct;stock;proveedor_id;fecha_ingreso\nREP-0002;;;;12,5;;;;\n", "d8_csv_punto_coma", false);
await csv("a,b,c\n1,2,3\n", "d8_csv_cab_mal", false);
await csv(CAB + "\n", "d8_csv_sin_filas", false);
await csv(CAB + "\n" + "REP-0002,,,,,,,,\n".repeat(501), "d8_csv_muchas", false);
await csv(CAB + "\n" + ",x,Disco de freno," + "a".repeat(300 * 1024) + ",3,40,1,PROV-CN-03,2026-11-24\n", "d8_csv_grande", false);
await csv(bueno, "d8_csv_prov", true, prov);
await csv(bueno, "d8_csv_anon", true, null);

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
  salida.liv_html.cuerpo = marcas(salida.liv_html.cuerpo);
  await pedir(l2, env2, "liv_empresa", "GET", "/empresa");
  salida.liv_empresa.cuerpo = marcas(salida.liv_empresa.cuerpo);
  await pedir(l2, env2, "liv_cot", "POST", "/api/cotizaciones", { repuesto_id: "REP-0022", cantidad: 10 });
}
process.stdout.write(JSON.stringify(salida));
