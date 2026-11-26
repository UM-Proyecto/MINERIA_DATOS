# Guía de estudio del portal MULTIPARTES

Esta guía es para que el equipo (Samuel, Sabrina y Fiorella) pueda explicar cada parte del portal sin ayuda: qué
muestra cada pantalla, de dónde sale cada dato, cómo se calcula cada cifra y qué es real y qué es de demostración.

> **Cómo se armó esta guía.** Ninguna cifra está escrita a mano. El script `src/guia/hechos.js` calcula cada número
> con el mismo motor y los mismos datos que usa el portal, y `src/guia/generar_guia.py` los pone en este texto. La
> prueba `tests/test_guia.py` vuelve a generar la guía y la compara con esta versión: si alguien cambia un número a
> mano, la prueba falla. Los datos usados son los del 26-nov-2026, con el dólar oficial de **11,86 Bs** del
> 26-nov-2026; si el dólar cambia, las cifras en bolivianos de los ejemplos cambian con él.

Contenido:

1. El portal en una página
2. De dónde salen los datos
3. Cómo funciona por detrás
4. Pantalla por pantalla
5. Los cálculos, uno por uno, con un ejemplo
6. Qué es real y qué es de demostración
7. Preguntas probables del docente
8. Glosario

---

## 1. El portal en una página

El portal es un prototipo académico de Minería de Datos (Univalle) para MULTIPARTES, una importadora de repuestos de
Santa Cruz. Responde a una pregunta de negocio: **qué repuestos comprar, cuántos y cuándo**, teniendo en cuenta la
demanda, el precio del dólar y el plazo de los proveedores.

- Dirección: <https://multipartes-univalle.pages.dev>
- **Tienda** (la raíz del sitio, `/`): es una propuesta de mejora del sitio actual de MULTIPARTES. Muestra el catálogo
  con precios en bolivianos y permite cotizar sin cuenta.
- **Área de la empresa** (`/empresa`): se entra con usuario.
  - `importador` / `demo-importador`: el personal de compras, con trece pantallas.
  - `proveedor` / `demo-proveedor`: cada proveedor ve solo sus repuestos.

El área de la empresa tiene trece pantallas, agrupadas en el menú:

| Grupo | Pantalla | Pregunta que responde | Historia |
|---|---|---|---|
| Resumen | Tablero de ventas | ¿Cómo van las ventas? | SCRUM-79 |
| Resumen | Predicción de ventas | ¿Qué repuestos se venderán el mes que viene? | SCRUM-80 |
| Decidir | Alertas de reposición | ¿Qué hay que pedir esta semana? | SCRUM-66 (HU-09) |
| Decidir | Simulador de compra | ¿Cuánto pedir y cuándo? | SCRUM-53 a SCRUM-64 |
| Decidir | Comparar proveedores | ¿A qué proveedor conviene comprar? | SCRUM-67 a SCRUM-70 |
| Decidir | Plan de compra con presupuesto | ¿Qué conviene comprar primero con el dinero disponible? | SCRUM-67 a SCRUM-70 |
| Entender la demanda | Importancia y rotación (ABC) | ¿Qué repuestos son importantes y cuáles se acumulan? | SCRUM-81 |
| Entender la demanda | Temporadas de venta | ¿En qué meses se vende más? | SCRUM-75 |
| Entender la demanda | Clientes que más compran | ¿De qué clientes dependen las ventas? | SCRUM-76 |
| Gestionar | Catálogo | ¿Qué vende MULTIPARTES? | SCRUM-74 |
| Gestionar | Cotizar por cantidad | ¿Cuánto cuesta un pedido? | SCRUM-72 |
| Gestionar | Cotizaciones guardadas | ¿Qué pidieron los clientes, aunque no hayan comprado? | SCRUM-73 |
| Gestionar | Registrar repuestos y clientes | ¿Cómo se agregan datos nuevos? | SCRUM-77 |

La vista del proveedor es SCRUM-78. Los textos claros y los íconos «i» de todas las pantallas son SCRUM-82, y la
cotización por correo es SCRUM-83. Dónde está el código de cada historia se ve en el README, sección «Dónde está cada
historia».

---

## 2. De dónde salen los datos

### 2.1 Las ventas: el conjunto carparts (dato real)

- **Qué es.** `carparts` es un conjunto público de datos publicado con el libro *Forecasting with Exponential
  Smoothing* (Hyndman, Koehler, Ord y Snyder, 2008, editorial Springer). Tiene las ventas mensuales de
  2.674 repuestos de auto, de enero de 1998 a marzo de 2002: 51 meses por repuesto.
- **Dónde está.**
  - Página del libro y de los datos: <https://robjhyndman.com/expsmooth/>
  - Descarga: <https://robjhyndman.com/expsmooth/expsmooth_data.zip>
  - Paquete R `expsmooth`, licencia GPL: <https://cran.r-project.org/package=expsmooth>
  - La copia que usamos está en `data/raw/scrum-55/expsmooth_data.zip`, con su huella sha256 para comprobar que no
    cambió.
- **Por qué se eligió.** MULTIPARTES no nos entregó sus ventas. carparts es la referencia académica para pronosticar
  demanda de repuestos, porque la mayoría de los meses no hay venta, como pasa con los repuestos reales: de las
  2.674 series, 2.294 son de venta intermitente y 347
  irregular.
- **Qué se le hizo (SCRUM-55, `src/scrum-55/adaptar_carparts.py`).**
  - Se eligieron 30 repuestos con una regla escrita: 6 de cada combinación de tipo de demanda y clase
    ABC, entre las series completas con al menos 6 meses con venta.
  - Recibieron los códigos REP-0001 a REP-0030; el código original queda en la columna `codigo_carparts`.
  - **Las cantidades no se tocaron.** Solo se trasladaron las fechas: enero de 1998 pasa a ser ago-2022 y marzo de
    2002, oct-2026. Así se pueden cruzar con el dólar de 2026. Es un supuesto: esas ventas no ocurrieron en esas
    fechas ni en Santa Cruz.
- **Archivo:** `data/processed/scrum-55/ventas_mensuales.csv` (un repuesto por mes, con el mes nuevo, el mes original
  y las unidades).

### 2.2 El dólar oficial: Banco Central de Bolivia (dato real)

- **Qué es.** El tipo de cambio oficial (TC): cuántos bolivianos cuesta un dólar según el Banco Central de Bolivia
  (BCB). Hoy: **11,86 Bs** por dólar, vigente el 26-nov-2026.
- **Cómo se trae (SCRUM-54).** El script `src/scrum-54/obtener_tco_bcb.py`:
  1. lee la página pública <https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php>;
  2. quita el HTML, lee la tabla «Tipo de cambio oficial, diario» y comprueba que no falten días;
  3. guarda la página original con su huella sha256 en `data/raw/scrum-54/`;
  4. guarda la serie limpia en `data/processed/scrum-54/tco_bcb_diario.csv`.
- **Se actualiza solo (SCRUM-71).** GitHub Actions corre ese script dos veces al día (09:30 y 18:00 de Bolivia),
  con el archivo `.github/workflows/tco-diario.yml`. Si hay un valor nuevo, regenera los datos, la app, la tienda y
  esta guía, corre las pruebas y lo guarda en el repositorio.
- **Serie:** 153 días, desde el 27-jun-2026 (9,73 Bs). Antes de esa fecha el dólar
  oficial fue fijo, de 6,96 Bs.

### 2.3 Otros datos públicos

- **Flete desde China (INE, dato real, HU-31).** El Instituto Nacional de Estadística publica el valor CIF y FOB de
  las importaciones. La diferencia entre los dos es el flete y el seguro: desde China da **7,8 %** del
  valor FOB. Está en `data/processed/hu-30-31/hu31_costos_importacion.csv`.
- **Dólar paralelo (fuente privada, solo referencia).** 12,01 Bs al 25-nov-2026: promedio de
  venta en plataformas de compraventa entre personas (P2P). Se lee una vez al día de dolarbolivia.net y, si no
  responde, de Binance P2P (dólar digital USDT contra bolivianos), con `src/scrum-54/obtener_paralelo.py`. La serie
  está en `data/processed/scrum-54/dolar_paralelo_diario.csv`, con la fuente de cada día. Si ninguna fuente
  responde, se conserva el último valor y la pantalla dice de qué fecha es. Se muestra en el simulador, pero **no
  entra en ningún cálculo**.

### 2.4 Lo que es de demostración y con qué regla se generó

MULTIPARTES no nos dio sus proveedores, precios, stock ni clientes. Para que el portal funcione, el equipo los
generó con reglas escritas y una semilla fija: con la misma semilla, el resultado sale idéntico cada vez.

| Dato | Regla | Archivo |
|---|---|---|
| 10 proveedores | 3 de Brasil, 4 de China y 3 de EE. UU., cada uno con su Incoterm, plazo, variación del plazo y puntualidad; a cada repuesto se le sortea uno | `data/processed/scrum-55/proveedores.csv` |
| Costo de fábrica en USD | Sorteado en un rango según la clase ABC: A de 5 a 35 USD, B de 15 a 70, C de 30 a 150 | `repuestos.csv`, columna `costo_unitario_usd` |
| Flete de Brasil (6 %) y EE. UU. (10 %) | Supuesto del equipo: no hay dato público en el repositorio | `proveedores.csv`, columna `flete_fuente` |
| Gastos de importación (5,498 %) | Seguro 0,88 % + nacionalización y agente aduanero 3,476 % + comisión 1,142 % (HU-31) | `proveedores.csv`, columna `gastos_pct_cif` |
| Precio de venta | Costo puesto más un margen de 35 % (A), 45 % (B) o 60 % (C) | `repuestos.csv`, columnas `margen_pct` y `precio_venta_bs` |
| Stock y pedidos en camino | Se reprodujeron las ventas reales día por día desde agosto de 2022 con una regla de reposición (s, S), ver 5.6 | `repuestos.csv`, `compras_historicas.csv` |
| Nombres y categorías de los repuestos | carparts solo trae un código; el nombre se asignó por costo (SCRUM-74) | `data/processed/scrum-74/catalogo.csv` |
| 20 clientes | Cada unidad vendida (real) se asignó a un cliente según su tamaño y su preferencia por la categoría (SCRUM-76) | `data/processed/scrum-76/` |
| Tramos de descuento | 10 a 50−1 unidades: 5 %; 50 o más: 10 % | `src/simulador/motor.js`, `TRAMOS_EJEMPLO` |
| Costo por pedido y del dinero | Bs 350 por pedido y 1,5 % al mes | `datos_app.json`, `parametros` |

En pantalla esto se dice una sola vez, en la nota al pie del menú y de la tienda: «Ventas: base pública carparts.
Clientes, proveedores, precios y stock: datos de demostración.» (decisión de Sam del 17-11-2026).

---

## 3. Cómo funciona por detrás

```
  DATOS ORIGINALES                 PREPARACIÓN (Python)                      PÁGINAS
  carparts (zip)  ──► scrum-55 ──► ventas, proveedores, stock ─┐
  BCB (página)    ──► scrum-54 ──► tco_bcb_diario.csv ─────────┤
  catálogo        ──► scrum-74 ──► catalogo.csv ───────────────┼──► preparar_datos.py ──► datos_app.json
  clientes        ──► scrum-76 ──► ventas por cliente ─────────┤                              │
  predicción      ──► scrum-80 ──► prediccion.json ────────────┘                              ▼
                                                    generar_app.py + motor.js ──► app del área de la empresa
                                                    generar_tienda.py + motor.js ──► tienda

  EN INTERNET
  GitHub (rama main) ──► el servidor lee de ahí los datos y las dos páginas
  Cloudflare Pages   ──► servidor del portal (worker_api.js) + base de datos D1 (cotizaciones, repuestos y clientes)
  GitHub Actions     ──► dólar diario (tco-diario.yml) y publicación del servidor (portal-deploy.yml)
```

- **El motor (`src/simulador/motor.js`).** Hace todos los cálculos: costo puesto, pronóstico, alertas, simulación,
  cotización, tablero y rotación. Está en JavaScript para que corra dentro de la página, sin servidor. Tiene una
  copia en Python (`motor_ref.py`) que solo sirve para probarlo: las dos versiones deben dar el mismo resultado.
- **Los generadores.** `generar_app.py` y `generar_tienda.py` arman cada página en un solo archivo HTML, con los
  datos, el motor y las fotos adentro. Por eso también se pueden abrir sin internet desde `reports/`.
- **El servidor (`src/portal/worker_api.js`).** Corre en Cloudflare.
  - Entrega la tienda en `/` y el área de la empresa en `/empresa`.
  - Controla quién entra (sesión firmada, con un rol por usuario).
  - Guarda en la base D1 lo que la página sola no puede guardar: cotizaciones, repuestos y clientes nuevos.
  - **Recalcula cada precio con el motor.** No confía en el precio que manda el navegador.
  - Lee los datos y las páginas desde la rama `main` de GitHub (variable `FUENTE_REF`), así que un cambio en `main`
    se ve en el sitio en unos 10 minutos, sin volver a publicar.
- **Las pruebas (`tests/`).** Son más de 200; se corren con `python3 -m unittest discover -s tests`. Entre otras
  cosas comprueban:
  - que el motor en JavaScript y su copia en Python den lo mismo;
  - que la predicción no use datos del futuro;
  - que cada precio del servidor coincida con el motor;
  - que no vuelvan a aparecer marcas de datos en pantalla;
  - que esta guía no tenga números escritos a mano.

---

## 4. Pantalla por pantalla

En cada pantalla del área de la empresa, debajo del título, una línea dice qué técnica usa y para qué decisión
sirve. Los íconos «i» explican cada indicador, gráfico y columna.

### 4.1 Tienda (`/`) — SCRUM-72, 74 y 78

- **Qué muestra:** el sitio de MULTIPARTES con su información real (textos, sucursales, rubros y logotipo, tomados
  de su sitio público) más lo agregado:
  - catálogo con foto, precio en bolivianos y stock;
  - cotizador con descuento por cantidad;
  - acceso al área de la empresa.
- **Para qué:** que el cliente vea precios y cotice sin llamar. Cada cotización queda guardada y es un dato de
  demanda, aunque el cliente no compre.
- **Datos:**
  - catálogo: `data/processed/scrum-74/catalogo.csv`;
  - precio: `repuestos.csv` (`precio_venta_usd`) por el dólar del día;
  - stock: `stock_al_2026_11_10`.
- **Ejemplo:** Correa de distribución para motor diésel 2.5 (REP-0019), 12 unidades → Bs 6.984,72. El cálculo está en 5.8.

### 4.2 Entrada (`/empresa`)

Pantalla de usuario y clave. Los usuarios son de demostración y están escritos en el servidor; la sesión dura unas
horas y va firmada con una clave secreta guardada en Cloudflare.

### 4.3 Tablero de ventas — SCRUM-79

- **Qué muestra:**
  - ventas totales: Bs 474.672, 797 unidades de ago-2022 a oct-2026;
  - ventas de los últimos 12 meses: Bs 109.552, contra Bs 105.687 de los 12 anteriores (+4 %);
  - repuesto más vendido: REP-0019, con 89 unidades;
  - cliente que más compra: Taller El Cruce (16,1 %); los 5 primeros suman el 51 %;
  - gráfico de unidades por mes con su promedio móvil de 12 meses, ventas por año y evolución de cada cliente por
    trimestre.
- **Técnica:** estadística descriptiva (totales, ordenamientos, serie mensual, promedio móvil) y concentración
  (Pareto).
- **Datos y cálculo:**
  - unidades: `ventas_mensuales.csv`;
  - bolivianos: unidades × precio de lista de hoy (carparts no trae precios de 1998), con el dólar del día;
  - función `Motor.dashboard`.
- **Lectura del gráfico:** el mes con más ventas fue mar-2025 (36 unidades); se venden en promedio
  15,6 unidades por mes.
  - El promedio móvil del último año es 13,3 por mes, contra 16,5 del año anterior: en unidades
    la demanda baja.
  - En bolivianos sube (+4 %), porque se vendieron menos unidades pero más caras.

### 4.4 Predicción de ventas — SCRUM-80

- **Qué muestra:** para cada repuesto, la probabilidad de vender al menos una unidad en noviembre de 2026.
  - 2 repuestos son «probables» (50 % o más), 6 «posibles» (entre 26 % y 50 %) y
    22 «poco probables».
  - El más probable es Bujía de encendido de iridio (REP-0022), con 58,2 %.
- **Técnica:** clasificación supervisada con regresión logística (ver 5.9), validada con 12 meses que el modelo no vio.
- **Datos:**
  - ventas reales (`ventas_mensuales.csv`);
  - resultado en `data/processed/scrum-80/prediccion.json`, calculado por `src/scrum-80/predecir_venta.py`.
- **Validación:**
  - AUC 0,68, contra 0,63 de la regla «se vende si se vendió el mes anterior»;
  - puntaje de Brier 0,174, contra 0,189 de decir siempre 26 %;
  - matriz de confusión con dos cortes (50 % y 26 %), calibración y peso de cada variable.

### 4.5 Alertas de reposición — SCRUM-66 (HU-09)

- **Qué muestra:** los 30 repuestos ordenados por urgencia: 3 «Pedir ya», 4 en vigilancia y
  23 cubiertos.
  - Muestra también el stock, lo que viene en camino, el punto de pedido, el plazo del proveedor, la venta esperada
    en ese plazo, la cantidad sugerida y su costo.
- **Técnica:** política de reposición (s, S) sobre el pronóstico (ver 5.6). Función `Motor.alertas`.
- **Ejemplo:** REP-0022 tiene 1 unidad en almacén y 5 en camino.
  - Su punto de pedido es 8 y su nivel máximo 9, así que está en «Pedir ya».
  - Cantidad sugerida: 3 unidades, que cuestan Bs 626,91 puestas en Santa Cruz.
- **Para qué:** saber qué pedir esta semana y cuánto. Al elegir una fila se abre el simulador con ese repuesto.

### 4.6 Simulador de compra — SCRUM-53 a SCRUM-64

- **Qué muestra:** para un repuesto y un proveedor, cuatro alternativas de compra evaluadas en 1.500
  escenarios de 90 días.
  - A: reponer lo justo.
  - B: cubrir 30 días más.
  - C: cubrir 60 días más.
  - D: la cantidad de C dividida en dos pedidos.
- **Supuestos que se pueden mover:**
  - el dólar en 90 días (de 9 a 15 Bs);
  - la venta (de −30 % a +30 % sobre el pronóstico);
  - el atraso del proveedor (de 0 a 30 días);
  - si el precio de venta sube con el dólar.
- **Técnica:** simulación de Monte Carlo (ver 5.7).
- **Ejemplo:** REP-0022 con Proveedor China Beta, sin mover los supuestos:

  | Alternativa | Cantidad | Puntaje (de 100) | Riesgo de quedarse sin stock | Ganancia media | Escenario desfavorable |
  |---|---|---|---|---|---|
  | A | 1 | 56 | 44 de 100 | Bs 522 | Bs −132 |
  | B | 2 | 44 | 42 de 100 | Bs 522 | Bs −178 |
  | C | 2 | 0 | 42 de 100 | Bs 522 | Bs −178 |
  | D | 2 | 0 | 44 de 100 | Bs 169 | Bs −512 |

  Gana la alternativa A.
- **Dólar de quiebre:** si se espera que el dólar pase de **12,20 Bs** en 90 días, la mejor deja de ser
  A y pasa a ser B.
- **Qué supuesto pesa más:** el dólar. Moverlo de un extremo al otro cambia la ganancia esperada en Bs 340;
  el que menos pesa la cambia en Bs 17.
- **Herramientas que respaldan cada alternativa:** el pronóstico de la venta (gráfico con la serie real) y la tabla
  de proveedores con su costo puesto.

### 4.7 Comparar proveedores — SCRUM-67 a 70

- **Qué muestra:** para un repuesto, el costo puesto en Santa Cruz con cada uno de los 10 proveedores, su plazo, su
  variación y su puntualidad.
- **Para qué:** el más barato en fábrica no siempre es el más barato puesto en Santa Cruz, por el Incoterm, el flete
  y la puntualidad.
- **Función:** `Motor.compararProveedores`. Ejemplo en 5.5.

### 4.8 Plan de compra con presupuesto — SCRUM-67 a 70

- **Qué muestra:** con un presupuesto dado, ordena los pedidos sugeridos por urgencia (y a igual urgencia, primero
  la clase A), y marca hasta dónde alcanza el dinero.
- **Función:** `Motor.planPresupuesto`.

### 4.9 Importancia y rotación (ABC) — SCRUM-81

- **Qué muestra:** cada repuesto según su peso en las ventas de los últimos 12 meses (clase ABC por dinero) y la
  rapidez con que se vende su stock.
  - Clase A: 13 repuestos concentran el 81 % de Bs 109.552.
  - Alertas: acumulación en 8 repuestos (Bs 16.045 inmovilizados) y baja rotación en 16.
  - La matriz cruza las dos cosas: 4 repuestos son A de rotación alta («no pueden faltar») y
    9 son C de rotación baja («no reponer»).
- **Técnica:** análisis ABC con el principio de Pareto (ver 5.1) y rotación del stock (ver 5.10).
- **Función:** `Motor.rotacion`.

### 4.10 Temporadas de venta — SCRUM-75

- **Qué muestra:** la venta promedio de cada mes del año.
  - El mes de mayor venta es diciembre, que vende 1,4 veces el promedio; el de menor venta es
    mayo (0,7).
  - Los meses de temporada alta, los que superan el promedio, son 6: febrero, marzo, agosto, octubre, noviembre, diciembre.
- **Técnica:** índice estacional (ver 5.11).
- **Advertencia para explicarla:** como las fechas se trasladaron, el calendario es el de carparts corrido siete
  meses, no el de Santa Cruz.

### 4.11 Clientes que más compran — SCRUM-76

- **Qué muestra:** los 20 clientes ordenados por compras, en todo el año, en temporada alta o fuera de ella.
  Muestra también la concentración (los 5 primeros) y el tipo de cliente que más compra: Taller mecánico,
  56 %.
- **Datos:** los clientes son de demostración. Las unidades vendidas son reales, pero quién las compró lo decidió
  una regla (ver 2.4).
- **Función:** `Motor.tableroClientes`.

### 4.12 Catálogo — SCRUM-74

- **Qué muestra:** la ficha de cada repuesto: foto, categoría, para qué sirve, precio con el dólar del día y stock.
- **Fotos:** tienen licencia libre (Openverse y Wikimedia Commons); los créditos están en la misma pantalla y en
  `data/raw/scrum-74/fuentes_imagenes.csv`. Muestran la categoría del repuesto, no la pieza exacta.

### 4.13 Cotizar por cantidad — SCRUM-72

Es la misma cotización de la tienda, dentro del área de la empresa. El personal puede además asociarla a un cliente
registrado. Cálculo en 5.8.

### 4.14 Cotizaciones guardadas — SCRUM-73

- **Qué muestra:** cada cotización emitida, con su número correlativo, fecha, cliente, repuesto, cantidad y total.
- **Datos:** se guardan en la tabla `cotizaciones` de la base D1 de Cloudflare.
- **Acciones:**
  - «Marcar venta» la suma a las ventas del Tablero y de Clientes.
  - «Descargar en Excel (CSV)» baja la lista filtrada.
- **Para qué:** una cotización sin venta también es información, porque muestra demanda que no se concretó.

### 4.15 Registrar repuestos y clientes — SCRUM-77

Formularios para agregar un repuesto (nombre, categoría, proveedor, costo, margen, stock) o un cliente. El servidor
valida cada campo y lo guarda en D1; el repuesto nuevo aparece en el catálogo, el cotizador y las alertas.

### 4.16 Vista del proveedor — SCRUM-78

El proveedor ve solo sus repuestos: su estado de alerta, cuánto se le pediría, el monto estimado y su puntualidad
de entrega. Lo que no es suyo no se lo entrega el servidor.

### 4.17 Cotización por correo — SCRUM-83

- **Flujo:** en la tienda, al cotizar se pide un correo y se valida su forma. Al «enviar», la pantalla confirma el
  envío y muestra cómo llegaría el correo: para, asunto, cuerpo y la cotización en PDF como adjunto.
- **El envío es de demostración:** no sale ningún correo. El servidor guarda la dirección y la hora junto a la
  cotización, y aparecen en Cotizaciones guardadas.
- **La cotización imprimible:** lleva el logotipo de MULTIPARTES sobre su verde, la franja de prototipo académico,
  el número, el cliente, el repuesto con su descuento, el total con el dólar del día, los tramos y una validez de 7
  días. La arma `src/portal/cotizacion_doc.js`, el mismo código en la tienda y en el área de la empresa.
- **En la empresa:** Cotizaciones guardadas muestra a qué correo se envió cada cotización y la abre con «Ver PDF».

---

## 5. Los cálculos, uno por uno, con un ejemplo

### 5.1 Clase ABC y principio de Pareto

- **Idea:** pocos repuestos explican la mayor parte de las ventas (principio de Pareto, también llamado «80/20»).
- **Regla:**
  1. Se ordenan los repuestos de mayor a menor valor vendido.
  2. Se suma el porcentaje acumulado.
  3. Los que llegan hasta el 80 % son clase A, hasta el 95 % clase B y el resto clase C.
- **Ejemplo (12 meses):** el primero es REP-0028, con Bs 13.778, que es el 12,6 % del total; con el
  segundo, REP-0013 (Bs 9.329), el acumulado llega a 21,1 %. Siguiendo así, 13 repuestos llegan al
  81 %: esos son los de clase A.
- **Ojo, hay dos clases ABC:**
  - la de la pantalla de rotación es por dinero de los últimos 12 meses;
  - la de SCRUM-55 (alertas, simulador) es por unidades sobre las 2.674 series de carparts.

### 5.2 Tipo de demanda: ADI y CV² (Syntetos y Boylan)

- **ADI**, intervalo medio entre ventas: meses con dato ÷ meses con venta.
- **CV²:** el cuadrado de (desvío ÷ media) de las cantidades, contando solo los meses con venta. Mide qué tan
  distinto es el tamaño de cada venta.
- **Clasificación:**

  | | CV² ≤ 0,49 | CV² > 0,49 |
  |---|---|---|
  | **ADI ≤ 1,32** | suave | errática |
  | **ADI > 1,32** | intermitente | irregular |

- **Ejemplo:** REP-0022 vendió en 17 de 51 meses, así que ADI = 3,00; CV² = 0,72. Por
  eso es «irregular».

### 5.3 Promedio móvil

- **Qué es:** el promedio de los últimos 12 meses, recalculado mes a mes. Suaviza los altibajos para ver la
  tendencia.
- **Ejemplo:** en los 12 meses hasta oct-2026 se vendieron 159 unidades; ÷ 12 = 13,3 por
  mes. Un año antes el promedio era 16,5.

### 5.4 Pronóstico: método SBA (Croston corregido)

- **El problema:** con venta ocasional, un promedio simple se equivoca, porque mezcla los meses sin venta con los
  meses con venta.
- **El método de Croston** separa dos cosas y las suaviza con α = 0,1:
  - **z**: el tamaño típico de una venta, cuando la hay;
  - **p**: cada cuántos meses hay una venta.
- **La corrección SBA** (Syntetos y Boylan) multiplica por (1 − α/2) para no sobreestimar.
- **Fórmula:** pronóstico mensual = (1 − α/2) × z ÷ p.
- **Ejemplo con REP-0022** (últimos 12 meses: 0, 2, 2, 8, 1, 5, 0, 0, 0, 1, 1, 7):
  - después de recorrer los 51 meses, z = 2,75 unidades y p = 5,76 meses;
  - pronóstico = 0,95 × 2,75 ÷ 5,76 = **0,45 unidades por mes** (0,015 por día);
  - el promedio simple de los 51 meses da 0,82.
- **Repuestos de venta regular:** se usa el promedio de los últimos 12 meses.
- **Función:** `Motor.pronostico`.

### 5.5 Costo puesto en Santa Cruz, Incoterm y aduana

- **Costo puesto:** lo que cuesta tener una unidad en el almacén de Santa Cruz.
- **Fórmula:** costo puesto = precio de fábrica × (1 + flete %) × (1 + gastos %), en dólares; después se multiplica
  por el dólar del día.
- **El Incoterm** (regla internacional de comercio) dice qué gastos de envío ya incluye el precio:
  - **EXW:** se retira en la fábrica, y se suman 3 puntos de traslado al flete;
  - **FOB:** puesto en el barco de origen, se suma el flete;
  - **CIF:** incluye flete y seguro hasta destino, no se suma flete.
- **Ejemplo:** REP-0022 cuesta 16,70 USD en fábrica.
  - Con Proveedor China Beta (CIF): fábrica Bs 198,06 + gastos Bs 10,91 = **Bs 208,97**.
  - Con Proveedor China Alfa (FOB): fábrica Bs 198,06 + flete Bs 15,45 (7,8 %) + gastos Bs 11,71
    = **Bs 225,22**.
- **Función:** `Motor.costoPuesto`.

### 5.6 Política de reposición (s, S) y stock de seguridad

- **Regla:** cuando el stock más lo que viene en camino baja hasta **s** (punto de pedido), se pide hasta llegar a
  **S** (nivel máximo).
- **s** = venta media × (plazo + 30 días) ÷ 30, más un **stock de seguridad**: z desvíos de la venta.
  - z = 1,65 para A, 1,28 para B y 0,84 para C, que cubren cerca del 95 %, 90 % y 80 % de los casos.
- **S** = s + 1, 2 o 3 meses de venta (A, B o C).
- **Ejemplo:** REP-0022, s = 8, S = 9; stock 1 + en camino 5 = 6, que está en el punto de pedido o por debajo: hay que pedir.
- **La misma regla generó el stock histórico de demostración (SCRUM-55):** desde agosto de 2022 se reprodujeron las
  ventas reales día por día y, una vez al mes, se aplicó esta regla.

### 5.7 Simulación de Monte Carlo

- **Idea:** el futuro es incierto, así que en vez de calcular un solo resultado se generan 1.500
  escenarios posibles al azar y se ve qué pasa en cada uno.
- **En cada escenario se sortea:**
  - la venta de cada mes (un mes real de los últimos 24, ajustado por el supuesto de venta);
  - el plazo de entrega del proveedor (su plazo normal ± su variación, con atrasos extra según su puntualidad);
  - el dólar a 90 días, con la volatilidad medida en la serie del BCB.
- **Para cada alternativa** se simulan los 90 días: llegan los pedidos, se vende lo que haya, se cuentan las ventas
  perdidas, el dinero inmovilizado y la ganancia.
- **Puntaje:** de cada 100 escenarios, en cuántos esa alternativa dejó más ganancia que las otras tres.
- **Semilla fija (20261112):** el resultado se puede repetir exactamente.
- **Dólar de quiebre:** se repite la simulación con dólares de 9 a 15 Bs (cada 5 centavos) y se busca dónde cambia
  la alternativa ganadora: 12,20 Bs en el ejemplo.
- **Sensibilidad:** se lleva cada supuesto de un extremo al otro, sin tocar los demás, y se mide cuánto cambia la
  ganancia.
- **Funciones:** `Motor.simular`, `Motor.quiebreDolar` y `Motor.sensibilidad`.

### 5.8 Cotización con tramos de descuento

- **Regla:** precio por unidad = precio de lista × (1 − descuento del tramo). El descuento nunca deja el precio por
  debajo del costo puesto.
- **Ejemplo:** Correa de distribución para motor diésel 2.5, 12 unidades:
  - precio de lista Bs 612,69; 12 unidades están en el tramo de 10 a 50−1, con 5 %;
  - precio por unidad Bs 582,06;
  - subtotal Bs 7.352,28 − descuento Bs 367,56 = **Bs 6.984,72**.
- **El servidor recalcula este precio con el motor** antes de guardarlo.
- **Función:** `Motor.cotizar`.

### 5.9 Predicción: regresión logística, AUC, Brier y Youden

- **Pregunta:** ¿se vende al menos una unidad el mes que viene? Es una clasificación con dos clases: «se vende» o
  «no se vende».
- **Variables**, calculadas solo con meses anteriores al que se predice:
  - vendió el mes anterior;
  - unidades de los últimos 3 meses;
  - meses con venta en los últimos 12;
  - vendió el mismo mes del año pasado;
  - meses seguidos sin vender.
- **Regresión logística:** suma las variables estandarizadas, cada una con su peso, más una constante (z), y la
  convierte en probabilidad con p = 1 ÷ (1 + e^(−z)). La variable que más pesa es «meses con venta en los últimos 12».
- **Ejemplo con REP-0022:**
  - variables: 1, 9, 0,67, 0 y 0;
  - estandarizadas: 1,70, 2,78, 1,84, −0,60 y −0,96;
  - pesos: 0,211, 0,035, 0,498, 0,005 y −0,167; constante −1,196;
  - z = 0,33 y p = 1 ÷ (1 + e^(−0,33)) = **58,2 %**, la misma probabilidad que muestra el portal.
- **Penalización L2 (λ = 1):** achica los pesos para que el modelo no se ajuste de más a los datos de
  aprendizaje.
- **Validación temporal:**
  - aprende con 810 casos (repuesto y mes) de ago-2023 a oct-2025;
  - se prueba con 360 casos de nov-2025 a oct-2026, que no vio; en ellos hubo
    91 ventas.
- **AUC (área bajo la curva ROC):** probabilidad de que el modelo dé más puntaje a un caso con venta que a uno sin
  venta.
  - 0,5 es azar y 1 es perfecto.
  - Modelo 0,68, regla simple 0,63: el modelo ordena mejor.
- **Puntaje de Brier:** el promedio de (probabilidad − resultado)², donde el resultado vale 1 si hubo venta y 0 si
  no. Mientras más bajo, mejor.
  - Modelo 0,174.
  - Decir siempre 26 % da 0,189.
  - La regla simple da 0,283.
- **Matriz de confusión (corte 50 %):**
  - 10 ventas previstas que ocurrieron;
  - 81 ventas no previstas;
  - 8 ventas previstas que no ocurrieron;
  - 261 meses sin venta bien previstos.
- **Medidas con el corte de 50 %:** exactitud 75 %, sensibilidad 11 %, especificidad
  97 %. Acierta mucho en total, pero anticipa pocas ventas, porque las ventas son minoría.
- **Índice de Youden** (sensibilidad + especificidad − 1): elige el corte que mejor equilibra las dos medidas, usando
  solo los datos de aprendizaje: 26 %.
  - Con ese corte la sensibilidad sube a 62 %, con especificidad 67 % y exactitud 66 %.
- **Calibración:** se agrupan los casos por la probabilidad dada y se compara con la parte que realmente se vendió.
  Si coinciden, la probabilidad es confiable.

### 5.10 Rotación, cobertura y alertas de acumulación

- **Rotación anual:** venta de 12 meses ÷ stock. Menos de 1 vez al año es baja rotación.
- **Cobertura:** stock ÷ venta mensual = meses que dura el stock.
  - Alta: 3 meses o menos.
  - Media: hasta 12 meses.
  - Baja: más de 12 meses, o sin ventas.
- **Acumulación:** stock + camino por encima del nivel máximo S, más de 24 meses de cobertura, o stock sin ventas en
  12 meses.
- **Ejemplo:** REP-0022 vendió 27 unidades en 12 meses con 1 en stock: cobertura
  0,4 meses, rotación 27,0 veces al año.

### 5.11 Índice estacional

- **Fórmula:** índice del mes = venta promedio de ese mes ÷ promedio de los 12 meses. 1,0 es un mes normal.
- **Ejemplo (30 repuestos juntos):** el promedio es 15,7 unidades por mes y diciembre promedia
  22,0, así que su índice es 1,4.

### 5.12 El dólar en los cálculos

- **Dólar oficial (11,86 Bs):** con él se convierte a bolivianos todo costo y precio del día.
- **Dólar a 90 días:** es un supuesto que mueve quien decide.
- **Dólar paralelo:** se muestra, pero no se usa en los cálculos.
- **Pedidos de demostración del pasado:** se convirtieron con el dólar oficial del día de la orden.

---

## 6. Qué es real y qué es de demostración, y por qué

| Real | De demostración |
|---|---|
| Unidades vendidas por repuesto y mes (carparts, con las fechas trasladadas) | Proveedores, plazos y puntualidad |
| Dólar oficial diario del BCB | Costos de fábrica, márgenes y precios |
| Flete desde China (INE) | Stock y pedidos en camino |
| Textos, sucursales y logotipo de MULTIPARTES (su sitio público) | Nombres y categorías de los repuestos |
| Fotos de categorías (licencia libre) | Clientes y a quién se vendió cada unidad |
| Cotizaciones que se emiten en el portal | Tramos de descuento, costo por pedido y costo del dinero |

**Por qué:** MULTIPARTES no entregó sus datos internos. Se eligió una base real y pública para la demanda, que es
lo que se pronostica y se mide, y una capa de demostración, con reglas escritas y semilla fija, para lo demás.

- Así cada cálculo es real en su método.
- Si MULTIPARTES entrega sus datos, basta con reemplazar los archivos de `data/processed/scrum-55/` y regenerar: el
  motor y las pantallas no cambian.

---

## 7. Preguntas probables del docente

1. **¿Los datos son reales?** Las ventas, sí: carparts (Hyndman y otros, 2008), 2.674 repuestos con
   51 meses. El dólar también, del BCB. Proveedores, precios, stock y clientes son de demostración, con reglas
   escritas.
2. **¿Por qué carparts y no datos de MULTIPARTES?** Porque no nos entregaron sus ventas, y carparts es la referencia
   académica para demanda intermitente de repuestos.
3. **¿Las ventas son de Santa Cruz?** No. Son de 1998 a 2002 y se trasladaron a ago-2022 a oct-2026 sin
   cambiar las cantidades.
4. **¿Cómo se actualiza el dólar?** Un script lee la página del BCB dos veces al día con GitHub Actions, valida la
   serie y regenera el portal.
5. **¿Por qué el dólar oficial y no el paralelo?** El oficial tiene fuente pública y fecha. El paralelo
   (12,01 Bs) es de fuente privada y solo se muestra como referencia.
6. **¿Qué técnica de minería de datos usan?**
   - Clasificación supervisada (regresión logística) en Predicción.
   - Segmentación ABC (Pareto) en Rotación.
   - Pronóstico de series (SBA) y simulación de Monte Carlo para decidir.
7. **¿Qué es la clase ABC?** Ordenar por valor vendido y cortar en 80 % y 95 %. Aquí 13 repuestos concentran
   el 81 %.
8. **¿Por qué SBA y no un promedio?** Porque la venta es ocasional. Para REP-0022, SBA da 0,45 unidades por
   mes y el promedio simple 0,82; el promedio simple sobreestima.
9. **¿Qué significa un AUC de 0,68?** Que el modelo ordena mejor que el azar (0,5) y que la regla simple
   (0,63), aunque no es perfecto.
10. **¿Y el Brier?** Es el error promedio de la probabilidad: 0,174, mejor que 0,189 de decir
    siempre la tasa base.
11. **¿Por qué la exactitud es 75 % pero la sensibilidad solo 11 %?** Porque la mayoría de los
    meses no hay venta: el modelo acierta diciendo «no se vende». Por eso se ofrece el corte de Youden
    (26 %).
12. **¿Cómo evitaron usar datos del futuro?** Las variables solo usan meses anteriores al predicho, y la prueba son
    12 meses posteriores a los de aprendizaje. Una prueba automática lo comprueba.
13. **¿Qué es el índice de Youden?** Sensibilidad + especificidad − 1. Se elige el corte que lo maximiza en los
    datos de aprendizaje.
14. **¿Qué es Monte Carlo aquí?** Evaluar cada alternativa en 1.500 escenarios sorteados de venta, plazo
    y dólar, y ver cuál gana más veces.
15. **¿Por qué el puntaje no es una probabilidad de acierto?** Porque compara alternativas entre sí: dice en cuántos
    escenarios de cada 100 una dejó más ganancia que las otras.
16. **¿Qué es el dólar de quiebre?** El valor del dólar a 90 días desde el que conviene comprar más hoy. Para
    REP-0022, 12,20 Bs.
17. **¿Qué es el costo puesto?** Fábrica + flete + aduana, en bolivianos. Para REP-0022 con CIF,
    Bs 208,97.
18. **¿Qué cambia entre FOB y CIF?** Con FOB se suma el flete (7,8 % desde China); con CIF ya viene en
    el precio.
19. **¿Qué es (s, S)?** Pedir cuando el stock y lo que viene en camino bajan a s, hasta llegar a S. Para REP-0022,
    s = 8 y S = 9.
20. **¿De dónde sale el stock si es de demostración?** De reproducir las ventas reales día por día desde 2022 con esa
    regla (s, S).
21. **¿Cómo se generaron los clientes?** Cada unidad real se asignó a uno de 20 clientes según su tamaño y su
    preferencia por la categoría, con semilla fija.
22. **¿Por qué el tablero está en bolivianos si carparts no tiene precios?** Se multiplican las unidades reales por
    el precio de lista de hoy, para comparar períodos con un mismo precio.
23. **¿Qué es el promedio móvil?** El promedio de los últimos 12 meses, recalculado cada mes: 13,3 unidades
    hoy, contra 16,5 hace un año.
24. **¿Qué es el índice estacional?** La venta de cada mes ÷ el promedio. El más alto es diciembre, con
    1,4.
25. **¿Dónde se guardan las cotizaciones?** En la base D1 de Cloudflare, con número correlativo. El servidor
    recalcula el precio antes de guardarlo.
26. **¿Es seguro?** Hay sesión firmada por rol; el proveedor solo recibe sus datos y los precios los calcula el
    servidor.
27. **¿Cómo saben que los cálculos están bien?** Con más de 200 pruebas automáticas. El motor tiene una copia en
    Python que debe dar lo mismo.
28. **¿El correo de la cotización se manda de verdad?** No: es de demostración. Se registra el correo y se muestra
    cómo llegaría.
29. **¿Qué tendría que darles MULTIPARTES para usarlo de verdad?** Sus ventas, proveedores, costos, stock y
    clientes. Se reemplazan los archivos de datos y se regenera.
30. **¿Qué limitaciones tiene?**
    - Las ventas no son de Santa Cruz ni de estos años.
    - La predicción ordena bien pero no asegura ventas (los repuestos se venden poco).
    - Precios y stock son de demostración.

---

## 8. Glosario

- **ABC:** clasificación de los repuestos por importancia económica. A, primer 80 % del valor; B, hasta el 95 %; C,
  el resto.
- **ADI:** intervalo medio entre ventas, en meses.
- **AUC:** área bajo la curva ROC; capacidad de un modelo para ordenar los casos. 0,5 es azar y 1 es perfecto.
- **BCB:** Banco Central de Bolivia.
- **Brier (puntaje de):** error promedio al cuadrado de una probabilidad; mientras más bajo, mejor.
- **carparts:** conjunto público de ventas mensuales de repuestos de auto (Hyndman y otros, 2008).
- **CIF, FOB, EXW:** Incoterms. CIF incluye flete y seguro hasta destino; FOB, puesto en el barco de origen; EXW, se
  retira en la fábrica.
- **Cobertura:** meses que dura el stock al ritmo de venta.
- **Costo puesto:** costo de tener una unidad en el almacén: fábrica + flete + aduana.
- **Croston / SBA:** métodos de pronóstico para venta ocasional; SBA corrige el sesgo de Croston.
- **CV²:** variabilidad del tamaño de la venta.
- **D1:** base de datos de Cloudflare donde el portal guarda cotizaciones, repuestos y clientes.
- **Estandarizar:** restar la media y dividir por el desvío, para comparar variables en una misma escala.
- **Incoterm:** regla internacional que define qué gastos de envío paga cada parte.
- **INE:** Instituto Nacional de Estadística de Bolivia.
- **Matriz de confusión:** tabla que cruza lo que predijo un modelo con lo que pasó.
- **Monte Carlo:** método que repite un cálculo en muchos escenarios sorteados al azar.
- **P2P:** plataformas de compraventa de dólares entre personas.
- **Pareto (principio de):** pocos elementos explican la mayor parte del total.
- **Promedio móvil:** promedio de los últimos n períodos, recalculado en cada período.
- **Regresión logística:** modelo que estima una probabilidad entre 0 y 1 a partir de variables.
- **Rotación:** veces al año que se vende el equivalente al stock.
- **(s, S):** política de reposición: pedir al llegar a s, hasta S.
- **Semilla:** número que fija los sorteos para que el resultado se pueda repetir.
- **Sensibilidad / especificidad:** proporción de ventas previstas / de meses sin venta bien previstos.
- **Stock de seguridad:** unidades extra para cubrir variaciones de la venta o del plazo.
- **TC:** tipo de cambio; precio del dólar en bolivianos.
- **Validación temporal:** probar un modelo con meses posteriores a los que usó para aprender.
- **Youden (índice de):** sensibilidad + especificidad − 1; sirve para elegir el corte de una probabilidad.
