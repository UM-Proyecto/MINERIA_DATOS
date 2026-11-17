# Pruebas en navegador (E2E)

Estas pruebas abren el portal en un navegador real (Chromium, con Playwright) y hacen lo que haría una persona. No
corren con `python3 -m unittest`, porque necesitan Playwright y un portal andando. Se corren a mano antes de unir un
cambio de pantalla, contra el portal local o contra el publicado.

## Preparación

```
pip install playwright && python -m playwright install chromium
python3 src/simulador/generar_app.py && python3 src/tienda/generar_tienda.py && python3 src/portal/armar_portal.py
node src/portal/servir_local.mjs --puerto 8790      # portal local con una base D1 de prueba en memoria
```

## Las pruebas

| Archivo | Qué comprueba | Historia |
|---|---|---|
| `textos_y_ayuda.py` | En la tienda y las 15 pantallas de la empresa, a 1920 y 390: ninguna marca de dato en pantalla, ninguna etiqueta SCRUM o HU fuera de las notas al pie, la nota única a la vista, que los íconos «i» abran, sin errores de consola ni desborde. | SCRUM-82 |
| `menu_desplazable.py` | El menú lateral se desplaza con la rueda o con el dedo, y el último ítem queda a la vista, sin que lo tape la nota, y se puede abrir. Prueba seis tamaños, desde 1920×1080 hasta el celular. | SCRUM-83 |
| `cotizacion_por_correo.py` | En la tienda, un correo vacío o mal escrito no se envía; uno válido muestra la confirmación y la vista del correo, y el adjunto abre la cotización imprimible. En la empresa, la cotización figura con su correo y «Ver PDF» la abre. | SCRUM-83 |

```
python tests/e2e/textos_y_ayuda.py http://localhost:8790 /tmp/capturas
python tests/e2e/menu_desplazable.py http://localhost:8790 /tmp/capturas
python tests/e2e/cotizacion_por_correo.py http://localhost:8790 /tmp/capturas
```

Cada una termina con `FALLAS: ninguna` o con la lista de lo que falló, y deja capturas en la carpeta indicada. Con la
dirección publicada (`https://multipartes-univalle.pages.dev`) prueban el sitio real. `cotizacion_por_correo.py`
guarda cotizaciones de prueba, así que contra el sitio real conviene no correrla.

**Controles.** Una prueba que no puede fallar no prueba nada. Por eso cada una se comprobó con un caso que tiene que
fallar:

- Con `.side{overflow:hidden}` inyectado, `menu_desplazable.py` falla en 4 de los 6 tamaños.
- Con una etiqueta «SCRUM-61» inyectada en un título, `textos_y_ayuda.py` la encuentra.
- Los correos `compras@taller` y vacío no se envían.
