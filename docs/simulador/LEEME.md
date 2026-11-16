# Simulador de compras de MULTIPARTES (la app)

La app es un solo archivo HTML: `reports/simulador/MULTIPARTES_Simulador_Compras.html`. Lleva adentro los datos, el motor de cálculo y el logotipo, así que se abre con doble clic en cualquier navegador moderno, sin servidor y sin conexión. Con conexión usa la letra Poppins del sitio de MULTIPARTES; sin conexión usa la del sistema y todo lo demás funciona igual.

Historias de Jira: SCRUM-64 (datos y plantilla), SCRUM-66 a SCRUM-70 (vistas) y SCRUM-68 (clasificación). El motor de cálculo es de SCRUM-53 y SCRUM-56 a SCRUM-63. Las vistas del 13-11-2026 son de SCRUM-72 y SCRUM-74 a SCRUM-76, y las del 16-11-2026 (Dashboard, Predicciones y Rotación e importancia), de SCRUM-79 a SCRUM-81. Cuando la app se sirve desde el portal (SCRUM-73, 77 y 78, ver `docs/portal/LEEME.md`), suma cotizaciones guardadas, carga de datos y una vista para el proveedor.

## Qué tiene

Las funciones del importador van en el menú de la izquierda, agrupadas en Resumen, Decidir, Entender la demanda y Gestionar; la app abre en el Dashboard. Cada pantalla dice arriba, en una línea, qué técnica usa y para qué decisión de compra sirve. Se pasa de una a otra sin recargar la página, y el botón «atrás» del navegador vuelve a la anterior.

| Función | Para qué sirve |
|---|---|
| Dashboard (SCRUM-79) | Cuánto dinero entró (total, últimos 12 meses y por año), qué repuesto salió más, qué cliente compra más, la demanda de los 30 repuestos mes a mes con su promedio móvil de 12 meses y el movimiento de compra de cada cliente por trimestre, con su tendencia de los últimos 6 meses. El dinero es unidades por precio de lista de hoy, porque carparts no trae precios históricos. |
| Predicciones (SCRUM-80) | Probabilidad de que cada repuesto se venda el mes que viene, con un clasificador de regresión logística. Muestra la validación temporal (entrena hasta oct-2025 y prueba con los 12 meses siguientes), la matriz de confusión, la calibración y el peso de cada variable, y lo compara con la regla «se vende si se vendió el mes anterior». El modelo lo calcula `src/scrum-80/predecir_venta.py`. |
| Rotación e importancia (SCRUM-81) | Clase ABC por el dinero de los últimos 12 meses cruzada con la rotación del stock en una matriz de 3 × 3, con las alertas de acumulación y de baja rotación y los «Pedir ya» de Alertas como desabastecimiento. |
| Alertas de reposición (inicio) | Los 30 repuestos ordenados por urgencia: «Pedir ya», «Vigilar» o «Cubierto». Una fila abre el simulador con ese repuesto. |
| Simulador de compra | Tipo de cambio de hoy, repuesto y proveedor, tres supuestos (dólar a 90 días, venta y atraso del proveedor), las cuatro alternativas con su puntaje, el dólar de quiebre y qué supuesto pesa más. |
| Comparar proveedores | Para un repuesto, el costo puesto en Santa Cruz con cada uno de los 10 proveedores. |
| Plan con presupuesto | Se escribe cuánto se puede gastar y la app marca hasta qué pedido alcanza. |
| ¿Qué hubiera pasado? | Tres formas de comprar aplicadas a los últimos 12 meses reales. |
| Clasificación de repuestos | Las 2.674 series de carparts según ADI y CV², con los cortes 1,32 y 0,49. |
| Temporadas de venta (SCRUM-75) | Venta promedio por mes del año, de los 30 juntos o de uno, con los meses que superan el promedio y un mapa de los 30 repuestos mes a mes. Para un repuesto dice en qué mes tiene que salir el pedido para llegar al mes fuerte. Los meses están re-fechados desde carparts: el patrón es el de carparts corrido siete meses, no el de Santa Cruz. |
| Clientes que más compran (SCRUM-76) | Ranking de los 20 clientes SINTÉTICOS por compras en todo el año, en temporada o fuera de ella, con qué repuestos lleva cada uno y el resumen por tipo de cliente. |
| Catálogo (SCRUM-74) | Ficha de cada repuesto con foto, categoría, descripción, precio con el dólar del día y disponibilidad. Nombres ILUSTRATIVOS; fotos con licencia libre y sus créditos. |
| Cotizar por cantidad (SCRUM-72) | Precio en bolivianos para una cantidad, con descuento de 5 % desde 10 unidades y de 10 % desde 50 (tramos de EJEMPLO). El descuento nunca deja el precio por debajo del costo puesto. |

### El dólar

El dólar oficial del BCB es la base. En el simulador se puede elegir el paralelo (11,99 Bs al 23-10-2026, promedio de plataformas P2P, marcado PRIVADO) u otro valor escrito a mano. Mientras el dólar elegido no sea el oficial, cada resultado que depende de él lleva una etiqueta amarilla que lo dice, también en Alertas, Comparar proveedores y Plan con presupuesto. «¿Qué hubiera pasado?» usa siempre el dólar oficial real de cada día.

### Qué es real y qué es simulado

Las ventas mensuales son reales (carparts, re-fechadas a 2022-2026) y el dólar oficial es real. Proveedores, plazos, costos, precios y stock son SINTÉTICOS (ver `docs/scrum-55/LEEME.md`). El costo de cada pedido (350 Bs) y el costo del dinero inmovilizado (1,5 % al mes) son supuestos del equipo y también son SINTÉTICOS.

## Cómo se regenera

Desde la raíz del repositorio, con Python 3.8 o más nuevo (solo biblioteca estándar):

```
python3 src/scrum-80/predecir_venta.py      # solo si cambian las ventas de SCRUM-55
python3 src/simulador/preparar_datos.py
python3 src/simulador/generar_app.py
python3 src/tienda/generar_tienda.py         # la tienda incrusta el mismo motor
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

`tests/test_simulador_app.py` comprueba que el JSON tenga las claves del contrato y los 30 repuestos, que el HTML armado traiga los datos, el motor y las diez vistas, que no aparezcan textos prohibidos, que no se repitan identificadores y que `generar_app.py` se detenga si falta el motor. Las vistas nuevas tienen sus propias pruebas: `test_temporadas_cotizar.py`, `test_catalogo.py`, `test_clientes.py`, `test_tco_automatico.py` y `test_portal.py`.
