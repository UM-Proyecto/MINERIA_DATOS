"""E2E de los tres módulos y Tablas (pedido del docente, 27-11-2026): en cada módulo sólo gráficos, cada «Ver la tabla»
lleva a su tabla en Tablas, y nada desborda a lo ancho. Uso: python tests/e2e/tres_modulos.py <url de la app> <carpeta de capturas>.
La url puede ser la app sola (file://.../MULTIPARTES_Simulador_Compras.html) o /empresa del portal con sesión iniciada."""
import sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1].split("#")[0], sys.argv[2]
falla = []
def chk(cond, que):
    print(("OK   " if cond else "FALLA"), que)
    if not cond: falla.append(que)

with sync_playwright() as p:
    br = p.chromium.launch()
    for w in (1920, 390):
        m = w < 500
        pg = br.new_context(viewport={"width": w, "height": 844 if m else 1080}, is_mobile=m, has_touch=m).new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        if url.startswith("http"):   # portal publicado: entra con el usuario de demostración (docs/portal/LEEME.md)
            pg.goto(url + "#entrar"); pg.wait_for_timeout(1500)
            pg.fill("#ent-u", "importador"); pg.fill("#ent-c", "demo-importador"); pg.click("#ent-b"); pg.wait_for_timeout(2500)
        for v in ("m1", "m2", "m3", "tablas"):
            pg.goto(url + "#" + v); pg.wait_for_timeout(2500)
            chk(pg.evaluate("document.documentElement.scrollWidth") <= w, f"{w} {v}: sin desborde a lo ancho")
            pg.screenshot(path=f"{out}/{v}-{w}.png", full_page=True)
        for v in ("m1", "m2", "m3"):
            pg.goto(url + "#" + v); pg.wait_for_timeout(2500)
            ids = pg.eval_on_selector_all(f"#v-{v} a.ver-tabla", "as => as.filter(a => a.offsetParent).map(a => a.dataset.t)")
            chk(len(ids) > 0, f"{w} {v}: tiene enlaces «Ver la tabla» ({len(ids)})")
            chk(pg.locator(f"#v-{v} .solo-tabla:visible").count() == 0, f"{w} {v}: ninguna tabla de respaldo a la vista")
            for t in ids:
                pg.goto(url + "#" + v); pg.wait_for_timeout(1500)
                pg.locator(f'#v-{v} a.ver-tabla[data-t="{t}"]').click(); pg.wait_for_timeout(1500)
                r = pg.evaluate("""t => { const e = document.getElementById(t), b = e && e.getBoundingClientRect();
                  return {hash: location.hash, dentro: !!e && !!e.closest('#v-tablas'), foco: !!e && e.classList.contains('tb-foco'),
                          visible: !!b && b.height > 0 && b.bottom > 0 && b.top < innerHeight}; }""", t)
                chk(r["hash"] == "#tablas" and r["dentro"] and r["foco"] and r["visible"], f"{w} {v}: «Ver la tabla» lleva a {t} ({r})")
        chk(not errs, f"{w}: sin errores de la página {errs[:3]}")
    br.close()
print("\n" + ("TODO BIEN" if not falla else f"{len(falla)} FALLAS"))
sys.exit(1 if falla else 0)
