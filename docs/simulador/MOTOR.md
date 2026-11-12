# Motor del simulador de compras de MULTIPARTES

Historias de Jira: SCRUM-53, SCRUM-56 a SCRUM-63, SCRUM-66, SCRUM-67, SCRUM-69 y SCRUM-70 (la parte de cálculo).

El motor es el archivo `src/simulador/motor.js`. Hace todas las cuentas de la app: costo puesto, pronóstico, simulación de una compra, dólar de quiebre, sensibilidad, alertas, plan con presupuesto, comparación de proveedores y «¿Qué hubiera pasado?». No dibuja nada en pantalla: recibe datos y devuelve números. La misma copia corre en el navegador (la app la incrusta) y en Node (las pruebas).

`src/simulador/motor_ref.py` repite las mismas cuentas en Python. La app no lo usa. Sirve para comprobar, en las pruebas, que el cálculo da lo mismo escrito de dos formas distintas.

## Qué calcula cada función

Todas reciben el objeto de datos de la app (`datos_app.json`): repuestos, proveedores, ventas mensuales, la serie del dólar oficial y los parámetros.

### `costoPuesto(repuesto, proveedor, dolar)`

Cuánto cuesta una unidad del repuesto puesta en Santa Cruz, en bolivianos, separada en tres partes:

- **fábrica**: el precio del proveedor en dólares por el dólar elegido;
- **flete**: el porcentaje de flete del proveedor sobre el precio de fábrica. Si el proveedor vende CIF, el flete ya viene dentro del precio: aquí vale 0 y el resultado dice `flete_incluido`;
- **gastos de importación**: el porcentaje de gastos sobre fábrica más flete.

Primero se calcula el costo puesto en dólares y se redondea a centavos, y después se pasa a bolivianos, igual que en SCRUM-55. Con el proveedor asignado y 11,75 Bs/USD da exactamente el `costo_puesto_bs` de `repuestos.csv` en los 30 repuestos.

### `pronostico(ventas, tipo)`

Cuántas unidades se espera vender por mes.

- Para los repuestos de venta **intermitente** o **irregular** (los 30 del simulador) usa **SBA**, el método de Croston corregido: sigue por separado el tamaño de cada venta y cada cuántos meses ocurre, con un suavizado de 0,1, y divide uno entre otro con la corrección de Syntetos y Boylan.
- Para el resto usa la media de los últimos 12 meses.

El tipo es opcional. Si no se da, el motor lo deduce de la serie: si se vende en menos de uno de cada 1,32 meses, la trata como intermitente.

### `simular(datos, repuesto, proveedor, supuestos, opciones)`

Responde: «si pido hoy, ¿cuánto me conviene pedir?». Compara cuatro alternativas:

| Alternativa | Cantidad |
|---|---|
| A, «lo justo» | La venta esperada mientras llega el pedido (plazo del proveedor más el atraso supuesto), más una reserva, menos lo que hay en stock y en camino. Al menos 1 unidad. |
| B | A más 30 días de venta. |
| C | A más 60 días de venta. |
| D | La misma cantidad que C, pero en dos pedidos: la mitad hoy y la otra mitad a los 30 días. Paga el costo de pedido dos veces. |

La reserva es el stock de seguridad de SCRUM-55: z por el desvío de la venta mensual de los últimos 24 meses, ajustado al plazo (z = 1,65 para clase A, 1,28 para B y 0,84 para C). Todas las cantidades se redondean hacia arriba a unidades enteras.

Después prueba las cuatro alternativas en muchos futuros posibles de 90 días (1.500 por omisión). En cada futuro cambian tres cosas:

- **la venta**: cada mes se toma al azar uno de los últimos 24 meses reales del repuesto, multiplicado por el cambio de venta que eligió el usuario;
- **el plazo del proveedor**: el plazo normal, más el atraso supuesto, más un desvío al azar del tamaño del desvío del proveedor; y, con la probabilidad de que el proveedor no cumpla (100 menos su porcentaje de entregas a tiempo), un atraso extra de 5 a 20 días;
- **el dólar a 90 días**: alrededor del dólar que eligió el usuario para dentro de 90 días, con la variación que tuvo de verdad el dólar oficial del BCB desde el 27-06-2026.

Día a día, el repuesto se vende de lo que hay en stock; si no hay, la venta se pierde. Lo que estaba en camino llega a la mitad del plazo normal del proveedor asignado; el pedido nuevo llega cuando dice el plazo sorteado.

La **ganancia** de cada alternativa en cada futuro es:

> ventas atendidas × precio − lo que se pagó por el pedido − costo por pedido × número de pedidos − costo del capital + lo que vale lo que sobró del pedido.

- El pedido de hoy se paga con el dólar de hoy. La segunda mitad de D se paga con el dólar del día 30 (a mitad de camino entre el de hoy y el sorteado para el día 90).
- Si se marca que el precio sigue al dólar, el precio en bolivianos sube o baja en la misma proporción que el dólar de cada día respecto al de hoy.
- El costo del capital es el dinero puesto en el pedido y todavía no recuperada en ventas, día por día, por la tasa mensual.
- Lo que sobra del pedido al día 90 (en el almacén o todavía en camino) vale lo que costaría reponerlo con el dólar de ese día.

Para cada alternativa devuelve: la cantidad (y cuánto se pide hoy y cuánto a los 30 días), el costo desglosado, los **días de margen** (cuántos días de venta quedan cuando llega el pedido), el **riesgo de quiebre** (en cuántos futuros de cada 100 se pierde alguna venta), las unidades perdidas en promedio, el **capital inmovilizado** (promedio diario del dinero puesto en el pedido sin recuperar), los días de venta que representa ese capital, la ganancia media, la ganancia del 10 % de los peores futuros y el **puntaje**: en cuántos futuros de cada 100 esa alternativa dejó más ganancia que las otras tres. `mejor` es la alternativa que gana en más futuros.

### `quiebreDolar(datos, repuesto, proveedor, supuestos, opciones)`

Busca el dólar a 90 días a partir del cual conviene otra alternativa. Prueba valores entre 9 y 15 Bs, de 0,05 en 0,05, por bisección (unas 9 simulaciones en vez de 121). Devuelve `{valor, antes, despues}`: con un dólar de `valor − 0,05` gana `antes` y con `valor` gana `despues`. Si gana la misma alternativa con 9 y con 15 Bs, devuelve `null`. Todas las simulaciones usan la misma semilla, así lo único que cambia entre una y otra es el dólar.

### `sensibilidad(datos, repuesto, proveedor, supuestos, opciones)`

Toma la mejor alternativa con los supuestos del usuario y mide cuánto cambia su ganancia media al llevar un supuesto de un extremo al otro, dejando los demás quietos: el dólar de 9 a 15 Bs, la venta de −30 % a +30 % y el atraso de 0 a 30 días. Devuelve los tres ordenados del que más mueve la ganancia al que menos.

### `alertas(datos, dolar)`

Una fila por repuesto con su estado de reposición, usando el proveedor asignado y la venta pronosticada:

- **Pedir ya** (0): stock más lo que viene en camino ya está en el punto de pedido o por debajo.
- **Vigilar** (1): todavía no llegó, pero a la venta pronosticada llega antes de lo que tarda el proveedor.
- **Cubierto** (2): el resto.

La cantidad sugerida es la que lleva el stock al nivel máximo de SCRUM-55 (nivel máximo menos stock y en camino), con un mínimo de 1 si el estado es «Pedir ya» o «Vigilar». Las filas salen ordenadas por estado y, dentro de cada estado, por los días que faltan para el punto de pedido.

### `planPresupuesto(alertas, presupuesto)`

Ordena los pedidos sugeridos por urgencia (estado), después por clase (A, B, C) y después por los días que faltan, y va sumando el costo. Marca `alcanza` mientras el acumulado no pase el presupuesto. Desde el primer pedido que lo pasa, todos los siguientes quedan como «no alcanza», aunque alguno más barato entrara: el plan respeta el orden de urgencia.

### `compararProveedores(datos, repuesto, dolar)`

El costo puesto del repuesto con cada uno de los diez proveedores, con el mismo precio de fábrica para todos, ordenado del más barato al más caro. Incluye el plazo, el desvío y el porcentaje de entregas a tiempo de cada uno, para que se vea que el más barato puede ser el más lento.

### `pasado(datos, politica)`

Repite noviembre de 2025 a octubre de 2026 con las ventas reales y el dólar oficial real, aplicando una forma de comprar a los 30 repuestos:

- `lo_justo`: pedir la cantidad A;
- `cubrir_60`: pedir la cantidad C (60 días más);
- `dos_pedidos`: la cantidad C en dos mitades, la segunda 30 días después.

El primer día de cada mes se revisa cada repuesto con el pronóstico hecho solo con los meses anteriores. Si la cantidad A es mayor que cero, se pide según la política; si no, no se pide. El pedido llega exactamente en el plazo normal del proveedor (sin azar). Se paga con el dólar del día de la orden: 6,96 Bs antes del 27-06-2026 y el TCO diario del BCB desde esa fecha. Devuelve las ventas perdidas, las ventas atendidas, el capital promedio, el número de pedidos, la ganancia y la lista de órdenes, sumando los 30 repuestos.

## Supuestos SINTÉTICOS

Estos valores no salen de MULTIPARTES ni de una fuente pública. Son supuestos del equipo para que el simulador funcione, y la app los muestra como tales.

| Supuesto | Valor | Dónde está |
|---|---|---|
| Costo por pedido (trámites y despacho) | 350 Bs por pedido | `parametros.costo_pedido_bs` |
| Costo del capital | 1,5 % al mes | `parametros.costo_capital_mensual` |
| Atraso extra cuando el proveedor no cumple | uniforme de 5 a 20 días | constante en `motor.js` |
| Llegada de lo que ya está en camino | a la mitad del plazo normal del proveedor asignado | constante en `motor.js` |
| Proveedores, plazos, costos en USD, precios, stock, punto de pedido y nivel máximo | ver `docs/scrum-55/LEEME.md` | `repuestos.csv`, `proveedores.csv` |

La **volatilidad del dólar** sí sale de datos reales: es el desvío de los cambios diarios del TCO del BCB desde el 27-06-2026, llevado a 90 días (por la raíz de 90). Con la serie actual da 15,1 % a 90 días. Es alta porque la serie incluye el salto de 9,73 a casi 12 Bs; si el dólar se calma, el número baja solo al regenerar los datos.

## Decisiones tomadas donde el contrato no alcanzaba

El contrato de la app dejaba algunos puntos abiertos o con resultados absurdos. Se decidieron de la forma más simple, y quedan anotados aquí:

1. **«Lo justo» es al menos 1 unidad.** El contrato decía mínimo 0. Con el stock actual, los 30 repuestos tienen A = 0 (stock y en camino cubren el plazo), y entonces A ganaba siempre porque no pagaba el costo de pedido de 350 Bs y las otras sí: puntaje 100 para A en los 30 repuestos y ningún dólar de quiebre. El simulador responde a «si pido hoy, ¿cuánto pido?»; si conviene o no pedir lo dice la vista de alertas.
2. **Lo que sobra al día 90 tiene valor.** La fórmula del contrato no lo contaba, y así cualquier unidad que no se vendiera en 90 días se contaba como dinero perdido. Ahora vale lo que costaría reponerla con el dólar de ese día. Es lo que hace que el dólar importe: si se espera que suba, comprar más hoy deja unidades que valen más mañana.
3. **El puntaje suma siempre 100.** Se cuentan los futuros que gana cada alternativa (los empates van a la primera, en el orden A, B, C, D) y se reparten los 100 puntos por el método del resto mayor, para que el redondeo no deje 99 o 101.
4. **`mejor`** es la alternativa que gana en más futuros, la misma que tiene el puntaje más alto.
5. **La normal y la exponencial se calculan a mano.** La normal es la suma de 12 números al azar menos 6, y la exponencial sale de una serie. Así JavaScript y Python dan el mismo resultado hasta el último decimal, cosa que no se puede asegurar con `Math.exp` y `math.exp`.
6. **Dólar de quiebre y sensibilidad usan 400 futuros** por simulación en vez de 1.500, para que la app responda rápido. Como todas las simulaciones usan la misma semilla, el resultado es estable: el valor de quiebre se repite igual en cada corrida.
7. **«¿Qué hubiera pasado?» arranca con el stock en el nivel máximo** al 1-11-2025, el mismo supuesto que usa SCRUM-55 para el arranque de 2022. Las tres políticas parten igual. Si la segunda mitad de `dos_pedidos` cae después del 31-10-2026, no se pide. El precio de venta sigue al dólar oficial del día (precio de `repuestos.csv` × dólar del día ÷ 11,75), y el stock se valora al dólar del día, de modo que todo queda en bolivianos de cada fecha.
8. **Días de margen y días de venta del capital** se redondean a días enteros. En las alertas, los días que faltan para el punto de pedido se redondean hacia abajo (días completos).

## Lo que muestra con los datos actuales

Con los supuestos de base (dólar de hoy y a 90 días = 11,75 Bs, sin cambio de venta, sin atraso, precio fijo en bolivianos), 1.500 futuros y la semilla 20261112:

- La mejor alternativa es A en los 30 repuestos, con un puntaje de 55 a 62. El stock actual alcanza para casi todos, así que comprar de más solo conviene si el dólar sube lo suficiente para pagar el costo del capital.
- Los 30 repuestos tienen dólar de quiebre: entre 12,30 y 12,55 Bs. En 18 cambia de A a B y en 12 de A a C. D no gana en ningún repuesto: con pedidos de una a cinco unidades, pagar dos veces los 350 Bs del pedido cuesta más de lo que ahorra repartir la compra.
- «¿Qué hubiera pasado?» (los 30 repuestos, noviembre de 2025 a octubre de 2026):

| Política | Ventas perdidas (unidades) | Capital promedio | Pedidos | Ganancia |
|---|---|---|---|---|
| Lo justo | 27,3 | Bs 32.634 | 38 | Bs 18.642 |
| Cubrir 60 días | 25,3 | Bs 35.742 | 25 | Bs 25.806 |
| Dos pedidos | 25,7 | Bs 34.526 | 50 | Bs 15.948 |

Con proveedores lentos y venta intermitente, comprar para 60 días perdió menos ventas, hizo menos pedidos y dejó más ganancia, además de comprar antes de la subida del dólar de junio de 2026.

## Cómo se corre la prueba

Hace falta Python 3.8 o superior y, para comparar con `motor.js`, Node.js (probado con la versión 22). Desde la raíz del repositorio:

```bash
python3 -m unittest tests.test_simulador_motor -v
```

La prueba arma los datos con `tests/_datos_motor.py` directamente desde los CSV de `data/processed/scrum-55` y `data/processed/scrum-54`, con las mismas claves que `datos_app.json`. Comprueba:

- que `motor.js` y `motor_ref.py` dan lo mismo en 20 casos fijos (tolerancia 1e-9 en números; igualdad exacta en enteros y textos) y que el generador de azar da exactamente los mismos números;
- que la comparación falla si un lado usa otro costo por pedido u otro costo del capital (control negativo);
- que el costo puesto reproduce `repuestos.csv`;
- que los puntajes suman 100, el riesgo está entre 0 y 100, y `simular` con 1.500 futuros tarda menos de 300 ms por repuesto;
- que el dólar de quiebre separa bien las dos alternativas en al menos 10 repuestos;
- el orden y la regla de las alertas, el acumulado del plan con presupuesto y «¿Qué hubiera pasado?».

Si `node` no está instalado, las pruebas que lo necesitan se saltan con el mensaje «node no está instalado».
