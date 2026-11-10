# HU-06: comparar escenarios cambiarios y logísticos

Compara un pedido fijo bajo un escenario base, una alternativa cambiaria y una
alternativa logística. Admite escenarios combinados y modificaciones expresas
por línea. Utiliza Python 3.8 o superior y únicamente su biblioteca estándar.

Los resultados son **MIXTO_SIMULADO**. Se reutilizan las referencias de HU-31 y
HU-32 y las compras ficticias de HU-30. No representan una cotización real ni una
liquidación de tributos de MULTIPARTES.

## Ejecución

Desde la raíz del repositorio:

```bash
python src/hu-06/comparar_escenarios.py
python -m unittest discover -s tests -p "test_*.py" -v
```

Para ejecutar solo las pruebas de esta historia:

```bash
python -m unittest discover -s tests -p "test_comparar_escenarios.py" -v
```

El script localiza la raíz a partir de su ubicación y también funciona desde
otra carpeta. Acepta `--config RUTA_JSON`, `--salida CARPETA_CSV` y
`--reporte RUTA_MD`. Las rutas de entrada del JSON son relativas a la raíz del
repositorio; las rutas de esos argumentos de consola son relativas al directorio
actual. También se aceptan rutas absolutas.

Valida y calcula todos los escenarios antes de escribir. Un error devuelve código
1 y conserva las salidas previas. Cada archivo se publica mediante un temporal y
su reemplazo; una interrupción durante la escritura no garantiza una transacción
conjunta de los cinco artefactos. Volver a ejecutar regenera el conjunto completo.
Dentro del repositorio solo permite escribir en `data/processed/hu-06/` y
`reports/hu-06/`; también admite salidas de revisión fuera del repositorio, sin
sobrescribir entradas. No ejecuta los generadores de otras historias.

## Entradas reutilizadas

Todas las rutas se configuran en `data/raw/hu-06/escenarios.json`, sección `archivos`.

| Clave | Ruta | Función |
|---|---|---|
| movimientos | `data/processed/hu-30-31/sintetico/hu30/movimientos_importados.csv` | Cantidades, precios USD, proveedores y documentos de compra |
| depuracion | `data/processed/hu-17/reporte_depuracion_final.csv` | Clasificación de cada movimiento del equipo |
| cotizaciones | `data/processed/hu-30-31/sintetico/hu31_cotizaciones_proveedor_sintetico.csv` | Descripciones de los repuestos; no reemplaza precios de compra |
| costos_importacion | `data/processed/hu-30-31/hu31_costos_importacion.csv` | Referencias documentadas y estimaciones logísticas |
| costos_complementarios | `data/processed/hu-30-31/sintetico/hu31_costos_complementarios_sintetico.csv` | Porcentajes y tarifa terrestre sintéticos |
| tipos_cambio | `data/processed/hu-32/tc_series_diaria.csv` | Observaciones cambiarias por serie y fecha exactas |

Se usa `codigo_unico` de HU-30/31. No se une con el catálogo `RPxxx` de HU-34.
HU-17 se cruza por `id_movimiento` y se comprueba coincidencia de documento,
repuesto, fecha, tipo y cantidad. Los `DUPLICADO` siempre se excluyen. Los
`PENDIENTE_REVISION` se excluyen salvo `incluir_pendientes: true` explícito.
Las compras generadas como `SINTETICO` que no pertenecen a la muestra de HU-17 se
conservan con `SINTETICO_SIN_CLASIFICACION_HU17`; esa etiqueta no certifica una
depuración inexistente. Un movimiento del equipo sin clasificación se rechaza.

Se mantienen todas las líneas válidas de cada orden, aunque compartan documento
o repuesto. No se toma solamente la primera línea de una orden. Si un documento
seleccionado no existe o queda sin líneas válidas, se rechaza la selección.

## Pedido y escenarios incluidos

La configuración selecciona las órdenes `OC-5003`, `OC-5006`, `OC-5008`,
`OC-5010` y `OC-5011`. Quedan cinco líneas, cinco repuestos y 205 unidades,
por **2.740,85 USD** de mercancía. Se excluyen los movimientos duplicados
`1006`, `1016` y `1022`.

Se declara un peso bruto hipotético de 100 kg, idéntico en los cuatro escenarios.
No hay pesaje, volumen ni número de contenedores por orden en los datos fuente.
Las órdenes se consolidan hipotéticamente y se valoran retrospectivamente al
23/10/2026; no es una reconstrucción de sus pagos históricos ni una evaluación
de la información que estaba disponible en esa fecha. La captura de HU-32 tiene
fecha de actualización 25/10/2026, que también queda conservada.

| Escenario | Cambio | Flete y seguro hasta frontera |
|---|---|---|
| BASE | TCO_BCB: 11,84 BOB/USD, 23/10/2026 | INE AEREA: 3,2056 USD/kg |
| CAMBIARIA | PARALELO_P2P_VENTA: 11,99 BOB/USD, mismo día | Igual al base |
| LOGISTICA | Igual al base | INE COURRIER: 3,9846 USD/kg |
| COMBINADO | Referencia P2P: 11,99 BOB/USD | INE COURRIER: 3,9846 USD/kg |

Nacionalización/agente: 3,476% del CIF; comisión: 1,142% del CIF; flete
local: 0,125 USD/kg. Son valores sintéticos existentes de HU-31. Los porcentajes
se mantienen; sus importes cambian cuando cambia el CIF.

## Configuración de alternativas

Debe existir exactamente un escenario de `tipo: BASE`, al menos uno de
`tipo: CAMBIARIA` y al menos uno de `tipo: LOGISTICA`. Los identificadores son
únicos, en mayúsculas, con letras, números o guion bajo, comenzando por letra.
Los campos desconocidos se rechazan para evitar que un error de escritura
desactive silenciosamente una modificación.

- BASE declara `tipo_cambio` y la lista `logistica`. Conserva las cantidades y
  precios originales y utiliza los parámetros físicos globales.
- CAMBIARIA declara únicamente su nuevo `tipo_cambio`, además de identificador,
  tipo y descripción. Hereda toda la logística y la canasta. Debe cambiar el
  valor numérico del cambio.
- LOGISTICA hereda el cambio y la canasta. Declara `cambios_logistica` con
  referencias completas que reemplazan por `id` un gasto del base; también puede
  redeclarar `parametros_logisticos`. Debe cambiar un costo efectivo.
- COMBINADO puede declarar cambio, reemplazos logísticos, parámetros y
  `modificaciones`. Todo lo omitido se hereda del base, nunca de otra alternativa.

Cada referencia de origen `importacion` selecciona un `concepto` exacto del CSV
y `campo: valor_min` o `valor_max` (por defecto el mínimo). Para origen
`complementario` se usa el campo `valor`. El ID del gasto no cambia al reemplazar
una referencia. No se seleccionan automáticamente los proveedores más baratos.

Un cambio de origen `serie` requiere `id_serie` y `fecha`. No se interpola ni se
arrastra un valor de otra fecha. Un cambio hipotético puede declararse así:

```json
{"origen": "supuesto", "fecha": "2026-10-23", "valor": "12.50", "motivo": "Hipótesis explícita para sensibilidad"}
```

Siempre se registra como `SINTETICO`. La fecha de las referencias utilizadas no
puede ser posterior a `fecha_analisis`; su fecha de captura/actualización se
conserva por separado. El TCO es una referencia, no el precio efectivo de compra
de dólares de la empresa. El paralelo tiene un único punto en este repositorio.

### Parámetros físicos y gastos supuestos

Cada parámetro en `parametros_logisticos` requiere `valor`, `motivo` y
`fecha_dato`. Se admiten `peso_kg`, `volumen_m3` y `contenedores`. Deben ser
positivos; los contenedores deben ser enteros. Los parámetros se consideran
supuestos sintéticos, no mediciones recuperadas de las fuentes.

Para una tarifa por kg se exige peso; para una tarifa por m³, volumen; para una
tarifa por contenedor, número de contenedores. No se inventan valores por defecto.

Una referencia logística hipotética puede sustituir un gasto con este formato:

```json
{
  "id": "terrestre",
  "origen": "supuesto",
  "concepto": "Transporte local hipotético en BOB",
  "valor": "150.00",
  "unidad": "BOB",
  "cubre": ["flete_local"],
  "motivo": "Supuesto explícito pendiente de cotización",
  "fecha_dato": "2026-10-23"
}
```

Su naturaleza siempre será `SINTETICO`. Las referencias existentes tienen
coberturas reconocidas por el módulo y no se pueden renombrar para eludir la
prevención de doble contabilización.

### Modificaciones expresas de cantidades y precios

En un escenario COMBINADO se puede agregar:

```json
"modificaciones": [
  {
    "id_movimiento": "1005",
    "cantidad": "45",
    "precio_unitario_usd": "10.50",
    "motivo": "Hipótesis explícita de ampliación y renegociación"
  }
]
```

Se puede cambiar solo cantidad o solo precio. Son obligatorios una línea válida
y un motivo; no se admite modificar dos veces la misma línea. Si cambia una
cantidad, el escenario debe redeclarar cada parámetro físico que utilicen sus
tarifas, con su justificación, aunque deliberadamente conserve el mismo peso o
volumen. No se alteran los archivos fuente ni la canasta original.

## Cálculos, unidades y cobertura

Todos los cálculos monetarios usan `Decimal`, con contexto local de 50 dígitos.
Es preferible escribir números decimales como cadenas JSON con punto decimal.
No se admiten NaN, infinitos, cantidades fraccionarias ni valores negativos.
Cantidades, precios y cambios son positivos; las tarifas pueden ser cero si
están declaradas. Se limita cada entrada a 16 dígitos enteros y 8 decimales.

Unidades admitidas: `USD`, `BOB`, `USD por kg`, `BOB por kg`, `USD por m3`,
`BOB por m3`, `USD por contenedor`, `BOB por contenedor` y `% del CIF` (en USD).
Se reconoce la anotación informativa `USD por kg (x% del FOB)` del INE; ese
porcentaje no se aplica otra vez. SCFI y cualquier otra unidad no monetaria se
rechazan. También se rechazan conceptos no reconocidos de las fuentes; para
ampliar el modelo debe definirse su cobertura, no asumirla automáticamente.

1. Mercancía por línea = cantidad × precio unitario USD.
2. Tarifa logística × parámetro físico, o importe fijo en su moneda.
3. CIF simulado = mercancía + flete internacional + seguro. Si el flete incluye
   seguro, no se agrega otro. Si el seguro es s% del propio CIF, se resuelve
   seguro = (mercancía + flete) × s / (100 − s); se exige s < 100.
4. Nacionalización/agente y comisión porcentuales se aplican sobre el CIF. El
   flete local queda fuera del CIF. Para porcentajes CIF, los componentes
   internacionales deben estar en USD; mezclar una base BOB se rechaza.
   También se rechaza calcular porcentajes CIF sobre un precio que ya incluya
   nacionalización, comisión o flete local sin desglose, pues no permite separar
   esos gastos posteriores al CIF.
5. Cada línea o gasto se redondea a centavos en su moneda, con `ROUND_HALF_UP`.
6. Cada importe USD se convierte a BOB y vuelve a redondearse a centavos. Los
   importes BOB quedan iguales. Total BOB = suma de todas las líneas convertidas.
7. Diferencia BOB = total del escenario − total base. Positiva significa mayor
   costo y negativa significa ahorro. Diferencia % = diferencia / total base ×
   100, redondeada a dos decimales. El base tiene ambas diferencias en cero.

El redondeo por línea garantiza que el detalle reconcilie exactamente con el
total. Puede diferir en centavos de convertir todo el agregado USD de una vez.

Se exige cubrir flete internacional, seguro, nacionalización/agente, comisión
y flete local exactamente una vez. `incluidos_en_precio` permite declarar los
componentes ya incluidos en la mercancía, respaldando esa decisión en `supuestos`.
Agregar nuevamente uno de esos gastos se rechaza. Los registros `PENDIENTE`
nunca se tratan como cero. Cubrir estos cinco componentes no demuestra que estén
incluidos todos los gastos y tributos de una importación real.

## Salidas

| Archivo | Contenido |
|---|---|
| `data/processed/hu-06/canasta_base.csv` | Líneas originales válidas, descripción, cantidades, precios y clasificación HU-17 |
| `data/processed/hu-06/comparacion_escenarios.csv` | Mercancía USD, logística USD, logística BOB de origen, CIF simulado, cambio, total y diferencias |
| `data/processed/hu-06/detalle_costos.csv` | Mercancía por línea, gastos por componente y fila de referencia cambiaria para cada escenario |
| `reports/hu-06/REPORTE_HU06.md` | Pedido, escenarios, análisis de impactos, fórmulas, supuestos y fuentes |
| `reports/hu-06/comparacion_escenarios.svg` | Barras de costo total simulado; se genera con Python estándar |

En el detalle, `TIPO_CAMBIO` es metadato y tiene importes vacíos: no es otro
gasto. Para sumar importes, usar `MERCANCIA` y `LOGISTICA`. `logistica_usd`
representa gastos originalmente denominados en USD; `logistica_bob_origen`,
gastos originalmente denominados en BOB; `logistica_convertida_bob`, todos los
gastos después de convertir los USD. No deben sumarse columnas de monedas
distintas entre sí.

Se conservan fuente, respaldo, unidad original, fecha del dato, fecha de
actualización y SHA-256 del archivo. `DOCUMENTADO`, `ESTIMACION` y `SINTETICO`
clasifican las referencias, no certifican como real el importe derivado de un
peso supuesto. Las modificaciones conservan cantidad y precio originales y su
motivo. El informe incluye las huellas de HU-17, cotizaciones y configuración;
la huella del JSON corresponde a su representación normalizada, no a sus bytes.

## Verificación y límites

Las pruebas usan datos pequeños con cálculos independientes, además del pedido
del repositorio. Verifican escenarios obligatorios, cantidades y precios fijos,
órdenes con varias líneas, duplicados, pendientes, modificaciones expresas,
monedas, unidades, seguro sobre CIF, redondeo, doble contabilización, fechas
faltantes, trazabilidad, salidas reproducibles, ejecución desde otra carpeta y
protección de fuentes y resultados de otras historias.

El total base esperado es 38.068,92 BOB; cambiario, 38.551,21 BOB; logístico,
39.033,88 BOB; combinado, 39.528,40 BOB, con la configuración incluida.

Para decisiones reales faltan pesajes y ruta/alcance confirmados, Incoterm,
comprobantes cambiarios, cotizaciones vigentes y liquidación de gastos y tributos.
Las tarifas públicas son referencias históricas y el supuesto de transporte
local debe contrastarse para evitar solapar tramos en una operación real.
