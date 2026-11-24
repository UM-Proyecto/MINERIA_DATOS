// Sirve el portal en http://localhost:8788 con una base D1 simulada (node:sqlite), para probarlo sin Cloudflare.
// Uso, desde la raíz del repositorio, después de armar_portal.py:
//     node src/portal/servir_local.mjs [--archivo base.sqlite] [--puerto 8788]
// La clave de sesión se genera al azar en cada arranque. Necesita Node 22 o superior.
import { createServer } from "node:http";
import { DatabaseSync } from "node:sqlite";
import { randomBytes } from "node:crypto";
import { pathToFileURL } from "node:url";
import { resolve, basename } from "node:path";
import { readFileSync, existsSync } from "node:fs";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const db = new DatabaseSync(arg("--archivo", ":memory:"));
const n = v => (v === undefined ? null : v);
class Stmt {
  constructor(sql, args) { this.sql = sql; this.args = args || []; }
  bind(...a) { return new Stmt(this.sql, a); }
  async all() { return { results: db.prepare(this.sql).all(...this.args.map(n)).map(r => ({ ...r })) }; }
  async first() { const r = db.prepare(this.sql).get(...this.args.map(n)); return r === undefined ? null : { ...r }; }
  async run() { db.prepare(this.sql).run(...this.args.map(n)); return { success: true }; }
}
const env = { DB: { prepare: s => new Stmt(s), batch: async ss => {
    // Como D1: todas las sentencias en una transacción (si una falla, no queda ninguna) y un resultado por sentencia.
    db.exec("BEGIN");
    try { const r = ss.map(s => ({ results: db.prepare(s.sql).all(...s.args.map(n)).map(x => ({ ...x })), success: true })); db.exec("COMMIT"); return r; }
    catch (e) { db.exec("ROLLBACK"); throw e; } } },
              SECRETO: randomBytes(32).toString("hex"),
              // Igual que env.ASSETS de Cloudflare Pages: sirve los archivos estáticos de build/portal (los catálogos PDF).
              ASSETS: { fetch: async req => { const f = resolve("build/portal/catalogos", basename(new URL(req.url).pathname));
                return existsSync(f) ? new Response(readFileSync(f), { headers: { "content-type": "application/pdf" } }) : new Response("", { status: 404 }); } } };
const w = (await import(pathToFileURL(resolve("build/portal/_worker.js")).href)).default;
const puerto = Number(arg("--puerto", 8788));
createServer(async (req, res) => {
  const cuerpo = [];
  for await (const c of req) cuerpo.push(c);
  const r = await w.fetch(new Request("http://localhost:" + puerto + req.url, { method: req.method, headers: req.headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(cuerpo) }), env);
  res.writeHead(r.status, Object.fromEntries(r.headers));
  res.end(Buffer.from(await r.arrayBuffer()));
}).listen(puerto, "127.0.0.1", () => console.log("Portal local en http://localhost:" + puerto));
