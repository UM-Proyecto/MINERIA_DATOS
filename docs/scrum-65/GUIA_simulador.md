# Guía del simulador de compras y preguntas del docente

MULTIPARTES · Minería de Datos (Univalle) · versión 2, jueves 12-nov-2026 · historia SCRUM-65

Esta guía sirve para explicar el simulador sin ayuda y para ensayar antes del martes 17. Las cifras salen del motor
integrado con los valores con que abre la pantalla: dólar oficial al 12 de noviembre de 2026 (11,70 Bs) también a 90
días, venta sin cambio, sin atraso, precio que sigue al dólar, 1.500 futuros y semilla 20261112.

## 1. En una frase

Es un simulador que le dice al jefe de compras de una importadora de repuestos **cuánto pedir y cuándo**, probando cada
forma de comprar en 1.500 futuros posibles del dólar, de la venta y del proveedor, y que descubre a partir de qué dólar
conviene cambiar de decisión.

## 2. El problema del importador

MULTIPARTES compra repuestos en dólares y los vende en bolivianos. Entre que pide y que le llega el repuesto pasan de 30 a
60 días. En ese tiempo cambian tres cosas que no controla:

1. **El dólar.** Desde que el BCB dejó flotar el tipo de cambio oficial, pasó de 9,73 Bs (27 de junio) a 12,64 Bs
   (9 de septiembre) y al 12 de noviembre está en 11,70 Bs. Un pedido de 1.000 dólares costó 2.910 Bs más un día que el otro.
2. **La venta.** Los repuestos se venden de vez en cuando y en cantidades que cambian mucho.
3. **El proveedor.** Algunos llegan tarde; uno de cada cuatro pedidos, en el peor caso.

Si pide de más, inmoviliza dinero y puede pagar un dólar caro. Si pide de menos, se queda sin stock y pierde ventas.

## 3. La pregunta del proyecto y cómo se responde

> ¿Qué técnicas de análisis de datos permiten apoyar las decisiones de compra de la empresa MULTIPARTES de Santa Cruz de la
> Sierra durante el segundo semestre de 2026?

La respuesta es el simulador: junta cinco técnicas, y cada una apoya una parte de la decisión.

| Técnica | Qué hace, en simple | Dónde se ve |
|---|---|---|
| Clasificación de la demanda (Syntetos y Boylan, ABC) | Agrupa los repuestos según cada cuánto se venden y cuánto varía la cantidad | Clasificación de repuestos |
| Pronóstico para demanda intermitente (Croston corregido, SBA) | Estima la venta de repuestos que se venden de vez en cuando, sin sobreestimarla | Simulador, cifra «venta pronosticada» |
| Simulación de Monte Carlo | Prueba cada forma de comprar en 1.500 futuros posibles y cuenta cuál gana más veces | Simulador, puntaje de cada alternativa |
| Análisis de sensibilidad y punto de quiebre | Mueve un supuesto por vez y encuentra el valor donde la mejor decisión cambia | Dólar de quiebre y «¿qué supuesto pesa más?» |
| Validación con el pasado | Repite los últimos 12 meses con las ventas y el dólar reales para ver qué habría funcionado | ¿Qué hubiera pasado? |

**Qué descubre que no se ve a simple vista:** el dólar de quiebre de cada repuesto, qué supuesto pesa más en cada caso,
que 87 de cada 100 repuestos son intermitentes (y un promedio simple los sobreestima) y que, con proveedores lentos,
comprar para cubrir 60 días dejó más ganancia que comprar lo justo: en los 12 meses reales, Bs 25.806 contra
Bs 18.642, con 25 pedidos en lugar de 38 y menos ventas perdidas (25,3 unidades contra 27,3).

## 4. Qué datos son reales y cuáles simulados

| Dato | Origen | Marca |
|---|---|---|
| Tipo de cambio oficial, diario desde el 27-jun-2026 | Banco Central de Bolivia, tabla pública; se actualiza con un comando (SCRUM-54) | REAL |
| Dólar paralelo (11,99 Bs al 23-oct) | Promedio de plataformas P2P | PRIVADO, solo para comparar |
| Ventas mensuales de 30 repuestos de auto | Conjunto público carparts (Hyndman y otros, 2008), 51 meses, re-fechados a 2022-2026 (SCRUM-55) | REAL, con fecha cambiada |
| Clasificación de 2.674 repuestos | Calculada por el equipo sobre carparts | REAL |
| Flete desde China | INE, tomado de HU-31 | REAL |
| Proveedores, plazos, puntualidad, costos, precios, stock | Generados por el equipo sobre las ventas reales | SINTÉTICO |
| Flete de Brasil y EE. UU., gastos de aduana | Supuestos del equipo y HU-31 | SINTÉTICO |
| Los 1.500 futuros de cada simulación | Generados por el simulador | SINTÉTICO |

Por qué carparts: la muestra de MULTIPARTES tiene unos 20 registros y no alcanza para simular. Carparts tiene ventas
reales de repuestos de auto con el mismo patrón de una importadora (71 de cada 100 meses sin venta), licencia abierta
(GPL) y se baja sin cuenta. Lo que no trae (proveedor, costo, stock) se simula y se dice.

## 5. Recorrido por la app

La app es un solo archivo que se abre con doble clic. El menú de la izquierda tiene seis funciones.

1. **Alertas de reposición** (SCRUM-66). Lo primero que ve el jefe de compras: qué repuestos ya llegaron al punto de
   pedido («Pedir ya»), cuáles llegarán antes de que el proveedor pueda entregar («Vigilar») y cuáles están cubiertos.
   Hoy: 3 para pedir ya y 4 en vigilancia.
2. **Simulador de compra** (SCRUM-53 a SCRUM-64). Arriba, el dólar oficial del día con su fuente; se puede elegir el
   paralelo u otro valor para comparar, y el resultado queda marcado. Después: el repuesto y el proveedor, la pregunta
   «¿Sube su precio de venta cuando sube el dólar?», y tres deslizadores (dólar a 90 días, venta, atraso del proveedor).
   Abajo, cuatro alternativas (lo justo, 30 días más, 60 días más, dos pedidos) con su puntaje, riesgo de quedarse sin
   stock, dinero inmovilizado y ganancia; el dólar de quiebre y qué supuesto pesa más.
3. **Comparar proveedores** (SCRUM-67). Para un repuesto, todos los proveedores con su costo puesto en Santa Cruz.
4. **Plan con presupuesto** (SCRUM-70). Se escribe cuánto se puede gastar y la lista dice qué entra y qué no.
5. **¿Qué hubiera pasado?** (SCRUM-69). Las tres formas de comprar aplicadas a los últimos 12 meses reales.
6. **Clasificación de repuestos** (SCRUM-68). El gráfico de los 2.674 repuestos de carparts según ADI y CV².

## 6. Las palabras que hay que poder explicar

- **Costo puesto en Santa Cruz:** lo que se paga hasta tener el repuesto en el almacén: precio de fábrica, flete, seguro y
  aduana.
- **Incoterm:** quién paga el envío. EXW: el comprador paga todo desde la fábrica. FOB: el proveedor lo pone en el barco;
  el flete lo paga el comprador. CIF: el precio ya incluye flete y seguro.
- **Punto de pedido:** la cantidad de stock con la que hay que pedir para no quedarse sin nada mientras llega el pedido.
- **Puntaje:** en cuántos de cada 100 futuros simulados una alternativa deja más ganancia que las otras tres. Sirve para
  comparar; no es la probabilidad de acertar.
- **Riesgo de quedarse sin stock:** en cuántos futuros de cada 100 el repuesto se agota antes de reponer.
- **Dinero inmovilizado:** lo que queda guardado en stock y no está disponible en caja.
- **Dólar de quiebre:** el dólar esperado a 90 días a partir del cual conviene cambiar de alternativa.
- **ADI:** cada cuántos meses, en promedio, se vende el repuesto. **CV²:** cuánto varía la cantidad cuando se vende.
- **Intermitente:** se vende de vez en cuando, en cantidades parecidas. **Irregular:** de vez en cuando y en cantidades
  muy distintas.
- **SBA (Croston corregido):** un pronóstico que estima por separado cada cuánto se vende y cuánto se vende, y corrige el
  exceso del método original.
- **Monte Carlo:** repetir el cálculo muchas veces con valores al azar dentro de rangos razonables, y contar resultados.
- **Semilla:** el número que fija los valores al azar para que la simulación salga igual cada vez que se corre.

## 7. Preguntas probables del docente, con su respuesta

1. **¿Qué problema resuelve?** Decidir cuánto pedir y cuándo, cuando el dólar, la venta y el proveedor cambian mientras
   llega el pedido.
2. **¿Por qué es minería de datos y no un sistema de carga?** Porque no registra datos: los cruza bajo miles de futuros y
   descubre cosas que no se ven en la tabla, como el dólar de quiebre o que casi todos los repuestos son intermitentes.
3. **¿Qué técnicas usan?** Clasificación de la demanda (Syntetos y Boylan y ABC), pronóstico para demanda intermitente
   (SBA), simulación de Monte Carlo, análisis de sensibilidad con punto de quiebre y validación con el pasado.
4. **¿De dónde sale el tipo de cambio?** De la tabla pública del Banco Central de Bolivia, con su fecha. Al 12 de noviembre, 11,70 Bs. Un
   comando la vuelve a leer y regenera la serie desde el 27 de junio.
5. **¿Y el paralelo?** Aparece aparte, rotulado privado. Se puede elegir para comparar, pero el oficial es la base y,
   si se usa otro, el resultado lo dice.
6. **¿Los datos son reales?** Las ventas sí: son de carparts, un conjunto público de repuestos de auto, con la fecha
   cambiada. El dólar oficial también. Proveedores, costos y stock son simulados y están marcados SINTÉTICO.
7. **¿Por qué no usaron datos de MULTIPARTES?** La empresa entregó unos 20 registros; no alcanzan para simular ni para
   validar. Cuando lleguen sus datos, se cambian los archivos de entrada y el simulador funciona igual.
8. **¿Qué significa el puntaje de 34?** Que en 34 de cada 100 futuros esa forma de comprar dejó más ganancia que las otras
   tres. Es una comparación, no una probabilidad de acertar.
9. **¿Por qué 1.500 futuros?** Con menos, el puntaje cambia de una corrida a otra; con 1.500 se estabiliza y la pantalla
   responde enseguida: una simulación de 1.500 futuros tarda unos 10 milisegundos (como máximo 60) en el equipo de pruebas.
10. **¿Cómo se generan los futuros?** La venta, remuestreando los últimos 24 meses reales; el plazo, con el normal del
    proveedor más su variación y la posibilidad de que se atrase; el dólar, alrededor del valor que el usuario espera,
    con la variación que tuvo el oficial desde junio.
11. **¿Qué es el dólar de quiebre?** El valor del dólar a 90 días a partir del cual conviene cambiar de forma de comprar.
    Si el usuario cree que el dólar pasará de ese número, le conviene adelantar la compra.
12. **¿Y si no hay quiebre?** Se dice que la mejor alternativa no cambia entre 9 y 15 Bs; no se inventa un valor.
13. **¿Cómo saben que funciona?** Por dos pruebas: el motor de la pantalla se compara con otro escrito en Python en 20
    casos fijos y deben dar lo mismo; y «¿Qué hubiera pasado?» aplica las reglas a los 12 meses reales.
14. **¿Qué es «cubrir 60 días»?** Pedir lo necesario para el plazo de entrega más dos meses de venta, para no volver a
    pedir pronto.
15. **¿Por qué dos pedidos puede ser peor?** Porque cada pedido paga trámites y flete; partir la compra baja el riesgo del
    dólar pero cuesta más.
16. **¿Qué es ADI y CV²?** ADI: cada cuántos meses se vende. CV²: cuánto cambia la cantidad. Con los cortes 1,32 y 0,49 se
    clasifica el repuesto en suave, errática, intermitente o irregular.
17. **¿Por qué no hay repuestos suaves ni erráticos en el simulador?** Porque en carparts ninguna serie completa vende en
    suficientes meses: todas son intermitentes o irregulares. Se corrigió el criterio en Jira para decirlo.
18. **¿Por qué SBA y no un promedio?** En repuestos que se venden de vez en cuando, el promedio mezcla los meses sin venta
    y da un pronóstico que no sirve para decidir; SBA separa cada cuánto se vende de cuánto se vende.
19. **¿Qué es el costo puesto y cómo entra el Incoterm?** Es fábrica más flete más aduana. Con FOB o EXW se suma el flete;
    con CIF ya viene incluido y no se cuenta dos veces.
20. **¿Qué pasa si el proveedor se atrasa?** Se mueve el deslizador del atraso y el simulador recalcula el riesgo de
    quedarse sin stock y los puntajes.
21. **¿Qué limitaciones tiene?** Las ventas son de otro mercado y de hace 25 años, con fechas cambiadas; proveedores y
    costos son simulados; la regla de reposición conoce la venta media de toda la serie. Por eso los resultados ilustran
    el método y no son recomendaciones para MULTIPARTES.
22. **¿Qué historias de usuario cubre?** SCRUM-53 a SCRUM-70, todas en el sprint; cada una tiene sus criterios en Jira.
23. **¿Quién hizo qué?** Samuel desarrolló el simulador, con el apoyo del equipo en la preparación de datos (HU-30, HU-31,
    HU-32, HU-34) y en los pronósticos (HU-07).
24. **¿Por qué con el dólar de hoy casi siempre gana «lo justo»?** Porque si el dólar a 90 días se queda donde está,
    comprar de más solo inmoviliza dinero. Con el oficial de 11,70 Bs, en los 30 repuestos el dólar de quiebre cae entre 12,30
    y 12,50 Bs (12,30 en REP-0022): si se espera un dólar por encima de ese valor, conviene comprar más ahora.
25. **¿Por qué un repuesto dice «Pedir ya» y el riesgo de quiebre es bajo?** La alerta aplica la regla fija de punto de
    pedido. El simulador mira la venta pronosticada: hay repuestos que venden menos de una unidad cada cinco meses y su
    stock alcanza para mucho más. Es justamente lo que el simulador aporta frente a la regla.
26. **¿Qué supuesto pesa más?** Depende del repuesto, y por eso la pantalla lo calcula para cada uno. Con el precio
    que sigue al dólar, el dólar pesa más en 22 de los 30 y la venta en 8. En REP-0022, llevar el dólar de 9 a 15 Bs mueve
    la ganancia en Bs 354, la venta de −30 % a +30 % en Bs 263 y el atraso de 0 a 30 días en Bs 21. Si el precio queda
    fijo en bolivianos, en REP-0022 la venta pasa a pesar más que el dólar. El atraso pesa poco cuando el stock cubre el
    plazo; en los repuestos que casi no se venden, mover el atraso no cambia nada, y eso es correcto.
27. **¿Qué supuestos propios tiene el motor?** «Lo justo» pide al menos una unidad, para que siempre pague el trámite del
    pedido; lo que sobra al día 90 vale lo que costaría reponerlo con el dólar de ese día; la variación del dólar sale de
    la serie oficial desde junio (15 % a 90 días, alta por el salto de junio). Están en docs/simulador/MOTOR.md.

## 8. Guion de cinco minutos para la demostración

1. **(30 s) El problema.** Mostrar el dólar oficial en la tarjeta 1 y su recorrido de 9,73 a 12,64.
2. **(45 s) Las alertas.** Abrir la app: «estos tres hay que pedirlos ya; estos cuatro llegan al punto de pedido antes de
   que el proveedor pueda entregar».
3. **(90 s) El simulador.** Hacer clic en REP-0022 (está en «Pedir ya»: 44 futuros de cada 100 se quedan sin stock). Explicar las cuatro alternativas y el puntaje. Mover
   el dólar esperado hasta pasar 12,30 Bs (su dólar de quiebre) y mostrar que la mejor pasa de A a B.
4. **(45 s) Qué pesa más.** Mostrar las tres barras (en REP-0022 el dólar pesa más) y llevar el atraso a 20 días: «lo
   justo» pasa de 1 a 2 unidades.
5. **(45 s) La evidencia.** Abrir «¿Qué hubiera pasado?» y leer el resultado de los 12 meses.
6. **(30 s) La minería.** Abrir la clasificación: «87 de cada 100 repuestos son intermitentes; por eso usamos SBA».
7. **(15 s) Cierre.** «Las ventas y el dólar son reales; lo simulado está marcado. Cuando lleguen los datos de MULTIPARTES,
   se cambian los archivos de entrada.»

## 9. Lo que no hay que decir

- Que el simulador «acierta» o «predice el dólar». Compara alternativas bajo supuestos.
- Que los datos son de MULTIPARTES. Las ventas son de carparts y lo demás es simulado.
- Que el paralelo es la referencia. La base es el oficial del BCB.
