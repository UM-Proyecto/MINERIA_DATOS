# Simulador de compras de MULTIPARTES (la app)

La app es un solo archivo HTML: `reports/simulador/MULTIPARTES_Simulador_Compras.html`. Lleva adentro los datos, el motor de cálculo y el logotipo, así que se abre con doble clic en cualquier navegador moderno, sin servidor y sin conexión. Con conexión usa la letra Poppins del sitio de MULTIPARTES; sin conexión usa la del sistema y todo lo demás funciona igual.

Historias de Jira: SCRUM-64 (datos y plantilla), SCRUM-66 a SCRUM-70 (vistas) y SCRUM-68 (clasificación). El motor de cálculo es de SCRUM-53 y SCRUM-56 a SCRUM-63.

## Qué tiene

Seis funciones en el menú de la izquierda. Se pasa de una a otra sin recargar la página, y el botón «atrás» del navegador vuelve a la anterior.

| Función | Para qué sirve |
|---|---|
| Alertas de reposición (inicio) | Los 30 repuestos ordenados por urgencia: «Pedir ya», «Vigilar» o «Cubierto». Una fila abre el simulador con ese repuesto. |
| Simulador de compra | Tipo de cambio de hoy, repuesto y proveedor, tres supuestos (dólar a 90 días, venta y atraso del proveedor), las cuatro alternativas con su puntaje, el dólar de quiebre y qué supuesto pesa más. |
| Comparar proveedores | Para un repuesto, el costo puesto en Santa Cruz con cada uno de los 10 proveedores. |
| Plan con presupuesto | Se escribe cuánto se puede gastar y la app marca hasta qué pedido alcanza. |
| ¿Qué hubiera pasado? | Tres formas de comprar aplicadas a los últimos 12 meses reales. |
| Clasificación de repuestos | Las 2.674 series de carparts según ADI y CV², con los cortes 1,32 y 0,49. |

### El dólar

El dólar oficial del BCB es la base. En el simulador se puede elegir el paralelo (11,99 Bs al 23-10-2026, promedio de plataformas P2P, marcado PRIVADO) u otro valor escrito a mano. Mientras el dólar elegido no sea el oficial, cada resultado que depende de él lleva una etiqueta amarilla que lo dice, también en Alertas, Comparar proveedores y Plan con presupuesto. «¿Qué hubiera pasado?» usa siempre el dólar oficial real de cada día.

### Qué es real y qué es simulado

Las ventas mensuales son reales (carparts, re-fechadas a 2022-2026) y el dólar oficial es real. Proveedores, plazos, costos, precios y stock son SINTÉTICOS (ver `docs/scrum-55/LEEME.md`). El costo de cada pedido (350 Bs) y el costo del dinero inmovilizado (1,5 % al mes) son supuestos del equipo y también son SINTÉTICOS.

## Cómo se regenera

Desde la raíz del repositorio, con Python 3.8 o más nuevo (solo biblioteca estándar):

```
python3 src/simulador/preparar_datos.py
python3 src/simulador/generar_app.py
```

1. `preparar_datos.py` junta los CSV de `data/processed/scrum-55/`, el tipo de cambio de `data/processed/scrum-54/tco_bcb_diario.csv` y el dólar paralelo de `data/raw/hu-32/insumos_publicos/puntos_documentados.csv` en `data/processed/simulador/datos_app.json`. No calcula nada del motor.
2. `generar_app.py` toma `src/simulador/plantilla_app.html` y le pone adentro ese JSON, el motor `src/simulador/motor.js` y el logotipo. Si el motor no existe, se detiene con un mensaje y no escribe nada.

Opciones de `generar_app.py`:

- `--motor RUTA` usa otro archivo de motor en lugar de `src/simulador/motor.js` (el motor se explica en `docs/simulador/MOTOR.md`).
- `--salida RUTA` escribe el HTML en otro lugar.

## Cómo está hecha

- `plantilla_app.html` usa el mismo CSS que la pantalla de decisión de compra (`src/hu-12/plantilla_panel.html`), copiado sin cambios en las secciones 1 a 9. Lo propio del simulador está en la sección 10.
- Toda cifra sale del motor (`Motor.simular`, `Motor.alertas`, etc.). La página solo pide, ordena y dibuja.
- Al mover un deslizador, la etiqueta cambia en el momento y el cálculo espera 150 ms sin movimiento antes de correr. Primero se calculan las cuatro alternativas; el dólar de quiebre y la sensibilidad, que corren el motor varias veces, van después en tareas separadas. Si se vuelve a mover algo antes de que terminen, el cálculo viejo se descarta.
- Se ve bien a 1920 × 1080, a 1080 × 1920 (pantalla vertical) y en un celular de 390 px de ancho, sin desplazamiento horizontal de la página. Las tablas anchas se desplazan dentro de su tarjeta.

## Pruebas

```
python3 -m unittest discover -s tests
```

`tests/test_simulador_app.py` comprueba que el JSON tenga las claves del contrato y los 30 repuestos, que el HTML armado traiga los datos, el motor y las seis vistas, que no aparezcan textos prohibidos y que `generar_app.py` se detenga si falta el motor.
