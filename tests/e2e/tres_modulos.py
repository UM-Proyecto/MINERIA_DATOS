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
        # Las frases salen de los datos: cambian con el período (m1), el repuesto (m3) y el presupuesto (m2).
        LEER = """s => Object.fromEntries([...document.querySelectorAll(s + ' article.tab-c')].filter(a => a.offsetParent)
                   .map(a => [a.id, (a.querySelector('h2') || {}).textContent + ' | ' + ((a.querySelector('.nota-sit') || {}).textContent || '')]))"""
        def cambian(antes, despues, fijas, que):
            for k, t in antes.items():
                if k in fijas: continue
                chk(t != despues.get(k), f"{w} {que}: cambia {k}")
        pg.goto(url + "#m1"); pg.wait_for_timeout(2500)
        a1 = pg.evaluate(LEER, "#v-m1"); pg.click('#tab-per button[data-v="todo"]'); pg.wait_for_timeout(1500)
        cambian(a1, pg.evaluate(LEER, "#v-m1"), {"tab-pred"}, "m1 con «Todo el período»")
        chk(pg.evaluate("document.documentElement.scrollWidth") <= w, f"{w} m1 con «Todo el período»: sin desborde a lo ancho")
        for v in ("m1", "m2", "m3"):
            pg.goto(url + "#" + v); pg.wait_for_timeout(2500); pg.screenshot(path=f"{out}/{v}-todo-{w}.png", full_page=True)
        pg.goto(url + "#m1"); pg.wait_for_timeout(1500); pg.click('#tab-per button[data-v="12m"]'); pg.wait_for_timeout(1000)
        pg.goto(url + "#m3"); pg.wait_for_timeout(2500)
        a3 = pg.evaluate(LEER, "#v-m3"); otro = pg.evaluate("() => { const s = document.getElementById('cs-rep'); return [...s.options].map(o => o.value).find(v => v !== s.value && v === 'REP-0013') || [...s.options].map(o => o.value).find(v => v !== s.value); }")
        pg.select_option("#cs-rep", otro); pg.wait_for_timeout(5000)
        cambian(a3, pg.evaluate(LEER, "#v-m3"), {"tab-dol"}, f"m3 con {otro}")
        pg.screenshot(path=f"{out}/m3-otro-{w}.png", full_page=True)
        pg.goto(url + "#m2"); pg.wait_for_timeout(2500)
        h = pg.text_content("#tab-plan-h"); pg.fill("#rp-presu", "500"); pg.wait_for_timeout(1200)
        chk(pg.text_content("#tab-plan-h") != h, f"{w} m2: el plan cambia con el presupuesto")
        pg.goto(url + "#alertas"); pg.wait_for_timeout(2000)
        chk(pg.evaluate("location.hash") == "#m2", f"{w}: #alertas lleva al m2")
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
