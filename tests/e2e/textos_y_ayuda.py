"""E2E de SCRUM-82 en el portal local: cada vista del importador y del proveedor, y la tienda, a 1920 y 390.
Mide en el texto VISIBLE (innerText): marcas de dato simulado, la nota única, íconos «i» que abren, errores de consola
y desborde horizontal. También busca etiquetas SCRUM o HU visibles fuera de las notas al pie. Uso: python tests/e2e/textos_y_ayuda.py <url base> <carpeta>."""
import re, sys
from playwright.sync_api import sync_playwright

B, out = sys.argv[1].rstrip("/"), sys.argv[2]
IMP = ["dashboard", "predicciones", "alertas", "simulador", "proveedores", "plan", "rotacion", "temporadas", "clientes",
       "catalogo", "cotizar", "cotizaciones", "cargar", "mineria"]
MARCAS = re.compile(r"SINTÉTIC|ILUSTRATIV|\bsimulad[oa]s?\b|TRAMOS DE EJEMPLO|ficticio|historia nueva|\$\{|(?-i:\bundefined\b|\bNaN\b)", re.I)
NOTA = "Ventas: base pública carparts. Clientes, proveedores, precios y stock: datos de demostración."
falla = []

def revisar(pg, nombre, w, errs, raiz_js):
    txt = pg.evaluate(f"({raiz_js}).innerText")
    m = sorted(set(x.group(0) for x in MARCAS.finditer(txt)))
    # Etiquetas de historia (SCRUM-xx, HU-xx) visibles fuera de las notas al pie (.pie): no debe haber ninguna.
    sc = pg.evaluate("(r) => [...r.querySelectorAll('*')].filter(e => e.getClientRects().length && !e.closest('.pie') && [...e.childNodes].some(n => n.nodeType === 3 && /SCRUM-\\d|HU-\\d/.test(n.textContent))).map(e => e.tagName + '.' + e.className + ': ' + e.textContent.trim().slice(0, 70))",
                     pg.evaluate_handle(raiz_js))
    if sc:
        print("   SCRUM fuera del pie:", sc[:6]); falla.append((w, nombre, "SCRUM visible", sc[:3]))
    n = pg.evaluate(f"[...({raiz_js}).querySelectorAll('.info')].filter(b => b.getClientRects().length).length")
    sw = pg.evaluate("document.documentElement.scrollWidth")
    abre = None
    if n:
        b = pg.locator(f".info >> visible=true").first
        b.scroll_into_view_if_needed()
        b.tap() if w < 500 else b.click()
        pg.wait_for_timeout(150)
        abre = pg.evaluate("!document.getElementById('info-pop').hidden && document.getElementById('info-pop').innerText.length > 20")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    linea = {"marcas": m, "iconos_visibles": n, "abre": abre, "scrollWidth": sw, "errores": list(errs)}
    print(w, nombre, linea)
    if m or sw > w or errs or (n and not abre):
        falla.append((w, nombre, linea))
    errs.clear()

with sync_playwright() as p:
    br = p.chromium.launch()
    for w in (1920, 390):
        movil = w < 500
        ctx = br.new_context(viewport={"width": w, "height": 1080 if not movil else 844}, has_touch=movil, is_mobile=movil)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
        # tienda
        pg.goto(B + "/", wait_until="networkidle"); pg.wait_for_timeout(800)
        nota_t = pg.evaluate(f"(() => {{ const e = [...document.querySelectorAll('.nota-datos')].find(x => x.innerText.includes({NOTA!r})); if(!e) return null; e.scrollIntoView(); const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }})()")
        print(w, "tienda: nota visible (ancho, alto):", nota_t)
        if not nota_t or nota_t[0] == 0: falla.append((w, "tienda", "nota no visible"))
        pg.screenshot(path=f"{out}/tienda_pie_{w}.png")
        pg.locator("#co-q").scroll_into_view_if_needed(); pg.wait_for_timeout(200)
        pg.screenshot(path=f"{out}/tienda_cotizar_{w}.png")
        revisar(pg, "tienda", w, errs, "document.body")
        # área de la empresa
        pg.goto(B + "/empresa"); pg.wait_for_timeout(800)
        revisar(pg, "entrar", w, errs, "document.body")
        pg.fill("#ent-u", "importador"); pg.fill("#ent-c", "demo-importador"); pg.click("#ent-b"); pg.wait_for_timeout(1500)
        for v in IMP:
            pg.evaluate(f"location.hash='#{v}'"); pg.wait_for_timeout(1500 if v == "simulador" else 800)
            revisar(pg, v, w, errs, f"document.getElementById('v-{v}')")
            pg.screenshot(path=f"{out}/{v}_{w}.png", full_page=True)
        nota_e = pg.evaluate(f"(() => {{ const e = [...document.querySelectorAll('.side .nota-datos-txt, .inner .nota-datos')].filter(x => x.getClientRects().length && x.innerText.includes({NOTA!r})); if(e[0] && e[0].closest('.inner')) e[0].scrollIntoView(); return e.map(x => {{ const r = x.getBoundingClientRect(); return [x.className, Math.round(r.top), Math.round(r.bottom), innerHeight, r.top >= 0 && r.bottom <= innerHeight]; }}); }})()")
        print(w, "empresa: nota visible en:", nota_e)
        if not nota_e or not all(x[4] for x in nota_e): falla.append((w, "empresa", "nota fuera de la pantalla"))
        pg.screenshot(path=f"{out}/nota_empresa_{w}.png")
        marco = pg.evaluate("document.querySelector('.side').innerText + ' ' + document.querySelector('.topbar').innerText")
        mm = sorted(set(x.group(0) for x in MARCAS.finditer(marco)))
        print(w, "marco:", mm)
        if mm: falla.append((w, "marco", mm))
        pg.evaluate("document.getElementById('b-salir').click()"); pg.wait_for_timeout(500)
        pg.fill("#ent-u", "proveedor"); pg.fill("#ent-c", "demo-proveedor"); pg.click("#ent-b"); pg.wait_for_timeout(1500)
        pg.evaluate("location.hash='#miprov'"); pg.wait_for_timeout(900)
        revisar(pg, "miprov", w, errs, "document.getElementById('v-miprov')")
        ctx.close()
    br.close()
# control negativo: el patrón ve una marca
assert MARCAS.search("Precio SINTÉTICO") and not MARCAS.search(NOTA)
print("FALLAS:", falla if falla else "ninguna")
