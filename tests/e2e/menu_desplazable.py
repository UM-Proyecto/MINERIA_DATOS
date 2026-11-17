"""¿Se puede desplazar el menú lateral? Rueda del mouse sobre el menú (escritorio) o arrastre con el dedo (tablet y
celular), y si el último ítem queda visible y clicable sin que lo tape la nota. Uso: python tests/e2e/menu_desplazable.py <url base> [carpeta de capturas]."""
import sys
from playwright.sync_api import sync_playwright

B = sys.argv[1].rstrip("/"); out = sys.argv[2] if len(sys.argv) > 2 else None
TAM = [("1920x1080", 1920, 1080, False), ("1366x768", 1366, 768, False), ("1280x600", 1280, 600, False),
       ("tablet 820x1180", 820, 1180, True), ("tablet horizontal 1180x820", 1180, 820, True), ("celular 390x844", 390, 844, True)]
malos = []
with sync_playwright() as p:
    br = p.chromium.launch()
    for nom, w, h, tactil in TAM:
        ctx = br.new_context(viewport={"width": w, "height": h}, has_touch=tactil, is_mobile=tactil and w < 900)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(B + "/empresa"); pg.wait_for_timeout(700)
        pg.fill("#ent-u", "importador"); pg.fill("#ent-c", "demo-importador"); pg.click("#ent-b"); pg.wait_for_timeout(1300)
        info = pg.evaluate("""() => { const s = document.querySelector('.side'), n = document.querySelector('#menu'), cs = getComputedStyle(s);
          return {pos: cs.position, oy: cs.overflowY, ox: getComputedStyle(n).overflowX, sh: s.scrollHeight, ch: s.clientHeight, nsw: n.scrollWidth, ncw: n.clientWidth}; }""")
        ultimo = pg.locator("#menu a").last
        nombre_ult = ultimo.get_attribute("data-v")
        horizontal = info["pos"] == "static"     # en el celular el menú es una barra horizontal
        if not horizontal:
            box = pg.locator(".side").bounding_box()
            pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            if tactil:
                # arrastre con el dedo: se simula con eventos táctiles de CDP
                c = ctx.new_cdp_session(pg); x = box["x"] + box["width"] / 2
                for y0, y1 in ((h * .8, h * .2), (h * .8, h * .2)):
                    c.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
                    for k in range(1, 11): c.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 + (y1 - y0) * k / 10}]})
                    c.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                    pg.wait_for_timeout(300)
            else:
                for _ in range(10): pg.mouse.wheel(0, 300); pg.wait_for_timeout(60)
            pg.wait_for_timeout(300)
        else:
            c = ctx.new_cdp_session(pg); nb = pg.locator("#menu").bounding_box(); y = nb["y"] + nb["height"] / 2
            for _ in range(3):
                c.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": w * .9, "y": y}]})
                for k in range(1, 11): c.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": w * .9 - w * .8 * k / 10, "y": y}]})
                c.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); pg.wait_for_timeout(300)
        # ¿el último ítem está dentro de la pantalla y es lo primero que hay en su centro (no lo tapa la nota)?
        r = pg.evaluate("""() => { const a = [...document.querySelectorAll('#menu a')].pop(), b = a.getBoundingClientRect();
          const cx = Math.min(innerWidth - 1, Math.max(0, b.left + b.width / 2)), cy = Math.min(innerHeight - 1, Math.max(0, b.top + b.height / 2));
          const top = document.elementFromPoint(cx, cy);
          return {dentro: b.top >= 0 && b.bottom <= innerHeight && b.left >= 0 && b.right <= innerWidth, encima: top ? (a.contains(top) ? "el ítem" : top.className || top.tagName) : null,
                  scrollTop: document.querySelector('.side').scrollTop, scrollLeft: document.querySelector('#menu').scrollLeft}; }""")
        ok = r["dentro"] and r["encima"] == "el ítem" and not errs
        if ok:
            ultimo.click(); pg.wait_for_timeout(500)
            ok = pg.evaluate("location.hash") == "#" + nombre_ult
        print(nom, info, r, "último:", nombre_ult, "OK" if ok else "FALLA", errs)
        if out: pg.screenshot(path=f"{out}/menu_{w}x{h}.png")
        if not ok: malos.append(nom)
        ctx.close()
    br.close()
print("FALLAS:", malos or "ninguna")
