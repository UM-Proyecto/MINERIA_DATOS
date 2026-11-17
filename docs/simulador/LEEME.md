# Simulador de compras de MULTIPARTES (la app)

La app es un solo archivo HTML: `reports/simulador/MULTIPARTES_Simulador_Compras.html`. Lleva adentro los datos, el motor de cálculo y el logotipo, así que se abre con doble clic en cualquier navegador moderno, sin servidor y sin conexión. Con conexión usa la letra Poppins del sitio de MULTIPARTES; sin conexión usa la del sistema y todo lo demás funciona igual.

Historias de Jira: SCRUM-64 (datos y plantilla), SCRUM-66 a SCRUM-70 (vistas) y SCRUM-68 (clasificación). El motor de cálculo es de SCRUM-53 y SCRUM-56 a SCRUM-63. Las vistas del 13-11-2026 son de SCRUM-72 y SCRUM-74 a SCRUM-76, y las del 16-11-2026 (Dashboard, Predicciones y Rotación e importancia), de SCRUM-79 a SCRUM-81. Cuando la app se sirve desde el portal (SCRUM-73, 77 y 78, ver `docs/portal/LEEME.md`), suma cotizaciones guardadas, carga de datos y una vista para el proveedor.

## Qué tiene

Las funciones del importador van en el menú de la izquierda, agrupadas en Resumen, Decidir, Entender la demanda y Gestionar; la app abre en el Tablero de ventas. Cada pantalla dice arriba, en una línea, qué técnica usa y para qué decisión de compra sirve. Se pasa de una a otra sin recargar la página, y el botón «atrás» del navegador vuelve a la anterior.

| Función | Para qué sirve |
|---|---|
| Tablero de ventas (SCRUM-79) | Cuánto dinero entró (total, últimos 12 meses y por año), qué repuesto salió más, qué cliente compra más, la demanda de los 30 repuestos mes a mes con su promedio móvil de 12 meses y el movimiento de compra de cada cliente por trimestre, con su tendencia de los últimos 6 meses. El dinero es unidades por precio de lista de hoy, porque carparts no trae precios históricos. |
| Predicción de ventas (SCRUM-80) | Probabilidad de que cada repuesto se venda el mes que viene, con un clasificador de regresión logística. Muestra la validación temporal (entrena hasta oct-2025 y prueba con los 12 meses siguientes), la matriz de confusión, la calibración y el peso de cada variable, y lo compara con la regla «se vende si se vendió el mes anterior». El modelo lo calcula `src/scrum-80/predecir_venta.py`. |
| Importancia y rotación (ABC) (SCRUM-81) | Clase ABC por el dinero de los últimos 12 meses cruzada con la rotación del stock en una matriz de 3 × 3, con las alertas de acumulación y de baja rotación y los «Pedir ya» de Alertas como desabastecimiento. |
| Alertas de reposición (inicio) | Los 30 repuestos ordenados por urgencia: «Pedir ya», «Vigilar» o «Cubierto». Una fila abre el simulador con ese repuesto. |
| Simulador de compra | Tipo de cambio de hoy, repuesto y proveedor, tres supuestos (dólar a 90 días, venta y atraso del proveedor), las cuatro alternativas con su puntaje, el dólar de quiebre y qué supuesto pesa más. |
| Comparar proveedores | Para un repuesto, el costo puesto en Santa Cruz con cada uno de los 10 proveedores. |
| Plan de compra con presupuesto | Se escribe cuánto se puede gastar y la app marca hasta qué pedido alcanza. |
| Temporadas de venta (SCRUM-75) | Venta promedio por mes del año, de los 30 juntos o de uno, con los meses que superan el promedio y un mapa de los 30 repuestos mes a mes. Para un repuesto dice en qué mes tiene que salir el pedido para llegar al mes fuerte. Los meses están re-fechados desde carparts: el patrón es el de carparts corrido siete meses, no el de Santa Cruz. |
| Clientes que más compran (SCRUM-76) | Ranking de los 20 clientes simulados por compras en todo el año, en temporada o fuera de ella, con qué repuestos lleva cada uno y el resumen por tipo de cliente. |
| Catálogo (SCRUM-74) | Ficha de cada repuesto con foto, categoría, descripción, precio con el dólar del día y disponibilidad. Nombres ilustrativos; fotos con licencia libre y sus créditos. |
| Cotizar por cantidad (SCRUM-72) | Precio en bolivianos para una cantidad, con descuento de 5 % desde 10 unidades y de 10 % desde 50 (tramos de ejemplo). El descuento nunca deja el precio por debajo del costo puesto. |

### El dólar

Todo se calcula con el dólar oficial del BCB del día. El paralelo (11,99 Bs al 23-10-2026, promedio de plataformas P2P, de fuente privada) se muestra en el simulador solo como referencia y no entra en ningún cálculo. El único dólar que se mueve es el supuesto de «¿A cuánto estará el dólar en 90 días?», que alimenta la tarjeta del dólar de quiebre.

El 16-11-2026, a pedido de Fiorella y Sam, se quitaron el selector «Dólar para calcular» (oficial, paralelo u otro valor) y las vistas «¿Qué hubiera pasado?» y «Clasificación de repuestos». Las funciones del motor que las calculaban (`Motor.pasado` y la clasificación de SCRUM-55) siguen en el repositorio con sus pruebas: el tipo de demanda de cada repuesto todavía elige su pronóstico. También desde ese día cada gráfico es de barras, de líneas, un histograma o una torta, con título y ejes con nombre.

### Textos de pantalla e íconos de información (SCRUM-82)

El 17-11-2026, a pedido de Sam, se revisaron todos los textos de pantalla del área de la empresa y de la tienda: trato de usted, sin jerga y con cada sigla explicada (BCB, ABC, AUC, Incoterm, P2P, SBA). Además, junto a cada indicador, gráfico, campo del cotizador y columna que no es obvia hay un ícono «i». Es un botón: se abre con clic, con toque en el celular o con el teclado (Enter), y se cierra con Escape o tocando fuera. En el HTML fijo basta con poner `data-i="Tema|Explicación"` en el elemento; en el JavaScript, la función `info(tema, texto)` devuelve el botón.

Con la misma decisión se quitaron de cada pantalla las marcas SINTÉTICO, ILUSTRATIVO y similares. Queda una sola nota fija al pie del menú (en el celular, al pie de la página) y en el pie de la tienda: «Ventas: base pública carparts. Clientes, proveedores, precios y stock: datos de demostración.» Una prueba (`test_textos_y_ayuda_del_17_11`) falla si vuelve a aparecer una marca o si falta la nota.

### Qué es real y qué es simulado

Las ventas mensuales son reales (carparts, re-fechadas a 2022-2026) y el dólar oficial es real. Clientes, proveedores, plazos, costos, precios y stock son SINTÉTICOS (ver `docs/scrum-55/LEEME.md`), y los nombres de los repuestos son ilustrativos. El costo de cada pedido (350 Bs), el costo del dinero inmovilizado (1,5 % al mes) y los tramos de descuento son supuestos del equipo y también son SINTÉTICOS. En pantalla eso se dice una sola vez, en la nota del pie.

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
