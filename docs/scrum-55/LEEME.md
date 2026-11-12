# SCRUM-55: ventas reales de repuestos adaptadas a MULTIPARTES

Esta carpeta explica cómo se tomó un conjunto público de ventas reales de repuestos de auto y se le agregó, encima, lo que le falta para parecerse a MULTIPARTES: proveedores, plazos de entrega, costos en dólares, precios en bolivianos y stock. Las ventas son reales; todo lo demás es simulado y está marcado así en cada archivo.

Historia en Jira: [SCRUM-55](https://fsandoval09.atlassian.net/browse/SCRUM-55).

## Qué es carparts

`carparts` es un conjunto de datos publicado con el libro *Forecasting with Exponential Smoothing* (Hyndman, Koehler, Ord y Snyder, 2008, Springer). Tiene las ventas mensuales de 2.674 repuestos de auto entre enero de 1998 y marzo de 2002: 51 meses por repuesto. La mayoría de los meses tienen venta cero (alrededor del 71 % de las celdas) y 165 repuestos tienen meses sin dato. Ese patrón, con muchos meses sin ventas y ventas sueltas de pocas unidades, es el típico de una importadora de repuestos.

- Licencia: GPL (>= 2), según el paquete R `expsmooth` 2.3 en CRAN (https://cran.r-project.org/package=expsmooth). Permite usar, modificar y redistribuir los datos citando la fuente.
- Descarga: https://robjhyndman.com/expsmooth/expsmooth_data.zip, bajado el 10/11/2026 y vuelto a bajar el 12/11/2026 con la misma huella.
- Copia guardada en `data/raw/scrum-55/expsmooth_data.zip` (206.764 bytes, sha256 `7ea2aabdfde73bb48eeec68c1eba3724d12d9b4691db3e353d3f310bb0fb3770`, también en `SHA256SUMS.txt`). Si el zip cambia, el script se detiene.

## Qué es real y qué es simulado

| Dato | Origen |
|---|---|
| Unidades vendidas por mes de cada repuesto | REAL (carparts). Solo cambia la fecha. |
| Tipo de demanda (ADI, CV²) y clase ABC | Calculados por el equipo sobre los datos reales. |
| Tipo de cambio | REAL: TCO diario del BCB desde el 27/06/2026 (`data/processed/scrum-54/tco_bcb_diario.csv`); antes, el oficial fijo de 6,96 Bs/USD. |
| Flete desde China | REAL (INE, tomado de HU-31): 7,8 % del valor FOB. |
| Proveedores, origen, incoterm, plazos, costo en USD, margen, precio en Bs, regla de reposición, órdenes de compra y stock | SINTÉTICO. |
| Flete desde Brasil y EE. UU., gastos de importación | Supuesto del equipo y valores SINTÉTICOS de HU-31. |

Cada fila de cada archivo lleva la columna `marca` con el texto «SINTÉTICO / ADAPTADO» y una columna `origen_dato` que dice qué parte es real.

### Cambio de fechas

Los 51 meses originales se trasladan, en el mismo orden, a agosto de 2022 hasta octubre de 2026. Enero de 1998 pasa a ser agosto de 2022 y marzo de 2002 pasa a ser octubre de 2026, el último mes completo antes del corte del 10/11/2026. Las cantidades no se tocan. Es un supuesto para poder cruzar las ventas con el tipo de cambio de 2026: las ventas no ocurrieron en esas fechas.

## Tres medidas, en una línea cada una

- **ADI** (intervalo medio entre ventas): meses con dato divididos entre meses con venta. Un ADI de 4 quiere decir que, en promedio, se vende algo una vez cada cuatro meses.
- **CV²** (variabilidad del tamaño de la venta): el cuadrado del desvío entre la media, calculado solo sobre los meses con venta. Cuanto más alto, más distintas son las cantidades de una venta a otra.
- **ABC**: se ordenan los repuestos de más a menos unidades vendidas; los que juntan el primer 80 % de las unidades son A, los que llegan hasta el 95 % son B y el resto son C.

Con ADI y CV² se clasifica el tipo de demanda según Syntetos y Boylan, con los cortes 1,32 y 0,49:

| | CV² ≤ 0,49 | CV² > 0,49 |
|---|---|---|
| **ADI ≤ 1,32** | suave | errática |
| **ADI > 1,32** | intermitente | irregular |

Los repuestos con menos de dos meses con venta quedan «sin clasificar», porque con una sola venta no se puede medir la variabilidad.

## Resultado de la clasificación de las 2.674 series

| Tipo de demanda | A | B | C | Total |
|---|---|---|---|---|
| suave | 2 | 1 | 0 | 3 |
| errática | 0 | 0 | 0 | 0 |
| intermitente | 927 | 706 | 661 | 2.294 |
| irregular | 284 | 57 | 6 | 347 |
| sin clasificar | 0 | 5 | 25 | 30 |
| **Total** | 1.213 | 769 | 692 | 2.674 |

Casi todo es intermitente o irregular, que es lo esperable en repuestos. Las tres series «suaves» tienen meses sin dato: su ADI se calcula solo con los meses que sí tienen dato y por eso no entran en la selección. Ninguna serie completa es suave ni errática, porque para tener un ADI de 1,32 o menos haría falta vender en al menos 39 de los 51 meses, y el repuesto que más meses vende lo hace en 38.

## Cómo se eligieron los 30 repuestos

La regla, en una frase: **entre las series completas (sin meses vacíos) con al menos 6 meses con venta, se toman 6 repuestos de cada combinación de tipo de demanda y clase ABC que tenga al menos 6 series así, repartidos a intervalos iguales desde el más vendido hasta el menos vendido.**

Con los datos de carparts quedan cinco combinaciones con suficientes series, y 5 × 6 = 30:

| Tipo de demanda | A | B | C |
|---|---|---|---|
| intermitente | 6 | 6 | 6 |
| irregular | 6 | 6 | — |

La combinación irregular C queda fuera porque tiene solo 4 series completas y ninguna con 6 meses con venta. Los 30 tienen 51 meses de historia cada uno, más que los 24 que pide la historia. Reciben los códigos `REP-0001` a `REP-0030`, en el orden de la tabla, y conservan su código original en la columna `codigo_carparts`.

## La capa simulada

Todos los valores están como constantes al principio de `src/scrum-55/adaptar_carparts.py`.

**Proveedores.** Diez proveedores ficticios: 3 de Brasil, 4 de China y 3 de EE. UU. Cada repuesto recibe uno, sorteado con la semilla.

| Proveedor | Origen | Incoterm | Plazo normal (días) | Desvío (días) | Entregas a tiempo |
|---|---|---|---|---|---|
| PROV-BR-01 | Brasil | FOB | 30 | 4 | 90 % |
| PROV-BR-02 | Brasil | EXW | 32 | 6 | 85 % |
| PROV-BR-03 | Brasil | CIF | 35 | 5 | 88 % |
| PROV-CN-01 | China | FOB | 55 | 10 | 75 % |
| PROV-CN-02 | China | CIF | 60 | 8 | 80 % |
| PROV-CN-03 | China | FOB | 50 | 12 | 70 % |
| PROV-CN-04 | China | EXW | 58 | 9 | 72 % |
| PROV-US-01 | EE. UU. | FOB | 40 | 6 | 88 % |
| PROV-US-02 | EE. UU. | CIF | 45 | 5 | 90 % |
| PROV-US-03 | EE. UU. | EXW | 42 | 7 | 82 % |

En cada orden, el plazo real sale de un sorteo: con la probabilidad de «entregas a tiempo» llega entre 0 y 3 días antes del plazo normal; si no, llega tarde por un número de días que depende del desvío.

**Costo en USD.** El precio del proveedor por unidad se sortea en un rango que depende de la clase ABC: A, de 5 a 35 USD; B, de 15 a 70 USD; C, de 30 a 150 USD. Se supone que los repuestos que más se venden son más baratos.

**Flete y gastos.** El flete y seguro hasta Bolivia, en porcentaje del valor FOB, es de 7,8 % para China (dato del INE que trae HU-31), 6 % para Brasil y 10 % para EE. UU. (estos dos son supuestos: el repositorio no tiene una referencia para esos orígenes). Si el incoterm es EXW se suman 3 puntos por el traslado hasta el puerto; si es CIF el flete ya viene dentro del precio del proveedor y no se suma. Encima se agregan 5,498 % de gastos de importación (seguro, nacionalización y comisión), tomados de los valores SINTÉTICOS de HU-31. El resultado es el `costo_puesto_usd`, lo que cuesta el repuesto ya en Santa Cruz.

**Precio de venta en Bs.** Costo puesto por el TCO del 10/11/2026 (11,75 Bs/USD) por un margen de 35 % (A), 45 % (B) o 60 % (C), redondeado a bolivianos enteros.

**Stock.** Se reproduce la demanda real día por día desde el 01/08/2022 hasta el 10/11/2026. Las unidades de cada mes se reparten a intervalos iguales dentro del mes. Una vez al mes, en un día fijo sorteado para cada repuesto, se revisa el stock: si lo que hay más lo que está en camino es igual o menor que el punto de pedido `s`, se pide lo necesario para llegar al nivel máximo `S`.

- `s` = venta media mensual × (plazo + 30 días) / 30, más un stock de seguridad de z desvíos (z = 1,65 para A, 1,28 para B y 0,84 para C).
- `S` = `s` más 1, 2 o 3 meses de venta media (A, B o C).
- El stock inicial del 01/08/2022 es `S`.
- Si una venta real no encuentra stock en la simulación, se cuenta como unidad no atendida. Las ventas no se modifican. Con la semilla por defecto pasa con 53 de las 797 unidades vendidas por los 30 repuestos.
- Noviembre de 2026 no tiene dato de ventas; del 1 al 10 de noviembre se supone que no hubo ventas.

## Conversión a bolivianos

Cada orden de compra se convierte con el tipo de cambio del día en que se hizo la orden:

- desde el 27/06/2026, el TCO diario del BCB de esa fecha;
- antes, el oficial fijo de 6,96 Bs/USD.

Las columnas `tc_bs_por_usd`, `tc_tipo` y `tc_fuente` dicen cuál se usó. En `repuestos.csv` los montos en Bs (costo, precio y valor del stock) usan el TCO del 10/11/2026.

## Archivos

En `data/processed/scrum-55/`:

- `repuestos.csv`: una fila por repuesto con su clasificación, su proveedor, sus costos en USD y Bs, su precio, su regla de reposición y su stock al 10/11/2026.
- `ventas_mensuales.csv`: 30 × 51 filas con el mes nuevo, el mes original y las unidades.
- `proveedores.csv`: los diez proveedores con su flete y de dónde sale cada porcentaje.
- `compras_historicas.csv`: las órdenes que generó la regla de reposición, con fecha de orden y de llegada, cantidad, costo en USD, tipo de cambio usado y costo en Bs.
- `resumen_clasificacion.csv`: cuántas series hay por tipo de demanda y clase ABC, para las 2.674 y para las 30 elegidas.
- `clasificacion_2674.csv`: la clasificación de cada una de las 2.674 series y cuál fue elegida.
- `fuente.json`: la cita, la licencia, la URL, la fecha de descarga y las huellas sha256.

## Cómo se corre

Hace falta Python 3.8 o superior. No usa librerías externas y se puede correr desde cualquier carpeta:

```bash
python src/scrum-55/adaptar_carparts.py
```

Opciones: `--semilla N` (por defecto 20261112) cambia la capa simulada, pero no las ventas ni la clasificación; `--salida CARPETA` escribe los archivos en otra carpeta. Con la misma semilla los archivos salen idénticos, byte por byte.

Las pruebas están en `tests/test_scrum55_carparts.py`:

```bash
python -m unittest tests.test_scrum55_carparts
```

## Límites

- Las ventas son de un distribuidor de repuestos de otro país y de otra época. Sirven por su forma (meses sin ventas, ventas sueltas), no como ventas de MULTIPARTES.
- No hay repuestos de demanda suave ni errática entre las series completas; la selección solo puede mostrar los tipos intermitente e irregular.
- El costo del proveedor no cambia en el tiempo y el precio de venta se fija con el tipo de cambio del 10/11/2026.
- La regla de reposición usa la venta media de toda la serie, algo que un comprador real no conoce de antemano.
