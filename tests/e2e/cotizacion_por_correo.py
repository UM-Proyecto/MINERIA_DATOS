"""E2E de SCRUM-83: tienda -> correo validado -> «enviada» con vista del correo -> adjunto PDF; y en el área de la
empresa, la cotización registrada con su correo y su PDF. Uso: python tests/e2e/cotizacion_por_correo.py <url base> <carpeta de capturas>."""
import sys
from playwright.sync_api import sync_playwright

B, out = sys.argv[1].rstrip("/"), sys.argv[2]
falla = []
def chk(cond, que):
    print(("OK   " if cond else "FALLA"), que)
    if not cond: falla.append(que)

with sync_playwright() as p:
    br = p.chromium.launch()
    for w in (1920, 390):
        movil = w < 500
        ctx = br.new_context(viewport={"width": w, "height": 1080 if not movil else 844}, has_touch=movil, is_mobile=movil)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(B + "/", wait_until="networkidle"); pg.wait_for_timeout(700)
        # la cotización rápida lleva al formulario y al correo
        pg.select_option("#qr-rep", "REP-0019"); pg.fill("#qr-q", "12"); pg.wait_for_timeout(200)
        pg.click("#qr-emitir"); pg.wait_for_timeout(900)
        chk(pg.evaluate("document.activeElement.id") == "co-correo", f"{w}: «Continuar» lleva al campo de correo")
        chk(pg.input_value("#co-q") == "12" and pg.input_value("#co-rep") == "REP-0019", f"{w}: conserva repuesto y cantidad")
        # sin correo y con correo mal escrito: no envía y lo dice
        pg.click("#co-emitir"); pg.wait_for_timeout(300)
        chk("Escriba el correo" in pg.inner_text("#co-correo-err") and pg.is_hidden("#co-enviado"), f"{w}: sin correo no envía")
        pg.fill("#co-correo", "compras@taller"); pg.click("#co-emitir"); pg.wait_for_timeout(300)
        chk("Revise el correo" in pg.inner_text("#co-correo-err") and pg.is_hidden("#co-enviado"), f"{w}: correo inválido no envía")
        pg.screenshot(path=f"{out}/tienda_correo_invalido_{w}.png")
        # correo válido: envía, confirma y muestra el correo
        pg.fill("#co-nom", "Taller El Cruce"); pg.fill("#co-correo", "compras@tallerelcruce.com")
        pg.click("#co-emitir"); pg.wait_for_selector("#co-enviado:not([hidden])", timeout=8000); pg.wait_for_timeout(900)
        txt = pg.inner_text("#co-enviado")
        chk("enviada a compras@tallerelcruce.com" in txt and "Asunto" in txt and ".pdf" in txt, f"{w}: confirma el envío y muestra para, asunto y adjunto")
        pg.locator("#co-enviado").screenshot(path=f"{out}/tienda_correo_enviado_{w}.png")
        pg.screenshot(path=f"{out}/tienda_correo_enviado_pantalla_{w}.png")
        # el adjunto abre la cotización imprimible
        with ctx.expect_page() as nueva:
            pg.click("#co-adj")
        doc = nueva.value; doc.wait_for_load_state(); doc.wait_for_timeout(600)
        dt = doc.inner_text("body")
        chk("COTIZACIÓN N°" in dt and "Taller El Cruce" in dt and "compras@tallerelcruce.com" in dt and "PROTOTIPO ACADÉMICO" in dt and "válida hasta" in dt, f"{w}: el adjunto abre la cotización con cliente, validez y franja")
        chk(doc.evaluate("document.documentElement.scrollWidth") <= w, f"{w}: la cotización no desborda")
        doc.screenshot(path=f"{out}/cotizacion_pdf_{w}.png", full_page=True)
        if not movil:
            doc.pdf(path=f"{out}/Cotizacion_MULTIPARTES_ejemplo.pdf", format="A4", print_background=True) if hasattr(doc, "pdf") else None
        doc.close()
        chk(not errs, f"{w}: tienda sin errores de consola {errs}")
        # área de la empresa: queda registrada con su correo y su PDF
        errs.clear()
        pg.goto(B + "/empresa"); pg.wait_for_timeout(700)
        pg.fill("#ent-u", "importador"); pg.fill("#ent-c", "demo-importador"); pg.click("#ent-b"); pg.wait_for_timeout(1300)
        pg.evaluate("location.hash='#cotizaciones'"); pg.wait_for_timeout(1300)
        fila = pg.inner_text("#t-cz tbody tr:first-child")
        chk("compras@tallerelcruce.com" in fila, f"{w}: Cotizaciones guardadas muestra el correo al que se envió")
        pg.screenshot(path=f"{out}/empresa_cotizaciones_{w}.png", full_page=True)
        with ctx.expect_page() as nueva:
            pg.click("#t-cz tbody tr:first-child button[data-pdf]")
        doc = nueva.value; doc.wait_for_load_state(); doc.wait_for_timeout(500)
        chk("COTIZACIÓN N°" in doc.inner_text("body"), f"{w}: «Ver PDF» abre la misma cotización")
        doc.close()
        chk(not errs and pg.evaluate("document.documentElement.scrollWidth") <= w, f"{w}: empresa sin errores ni desborde {errs}")
        ctx.close()
    br.close()
print("FALLAS:", falla or "ninguna")
