# HU-34 — Describir los conjuntos de datos disponibles

## Empresa y propósito

MULTIPARTE, empresa de repuestos automotrices. Actor principal: jefe de compras. Esta entrega documenta fuentes para analizar cuándo y cuánto comprar, considerando ventas, inventario, costos y tipo de cambio.

## Naturaleza y alcance

No se proporcionaron bases empresariales reales para esta actividad. Se construyeron tres fuentes FICTICIAS para fines académicos; no son registros, cifras ni resultados reales de MULTIPARTE. Las tasas de cambio también son ficticias y no provienen de una cotización oficial. El período simulado termina el 24/10/2026. Los registros de 2025 aportan historia para analizar 2026.

Cada conjunto supera 3.000 filas. Una fila significa una observación con sus columnas, no una celda. El volumen y la cobertura permiten practicar integración y análisis, pero no garantizan precisión ni representan evidencia sobre la empresa.

## Inventario de fuentes

| Fuente | Archivo | Filas | Columnas | Unidad de observación | Período principal | Origen |
|---|---|---:|---:|---|---|---|
| ventas | ventas_simuladas.csv | 19,860 | 6 | Un repuesto por día (incluye ceros) | 2025-01-01 a 2026-10-24 | Ficticio |
| compras | compras_simuladas.csv | 3,600 | 10 | Una línea de pedido recibida | 2025-01-01 a 2026-09-24 | Ficticio |
| inventario | inventario_simuladas.csv | 19,860 | 7 | Un repuesto por día y almacén | 2025-01-01 a 2026-10-24 | Ficticio |

## Conjunto: ventas

**Tamaño:** 19,860 registros y 6 columnas. **Origen:** ficticio. **Cobertura:** 30 repuestos.

**Columnas, tipos y datos faltantes**

| Columna | Tipo lógico | Significado y unidad | Faltantes | Porcentaje |
|---|---|---|---:|---:|
| fecha | Fecha | Día observado | 0 | 0.00% |
| sku | Texto | Identificador de repuesto compartido entre fuentes | 0 | 0.00% |
| categoria | Texto | Familia de repuestos | 0 | 0.00% |
| unidades_vendidas | Entero | Unidades efectivamente vendidas en el día; puede ser cero | 0 | 0.00% |
| precio_unitario_bs | Decimal | Precio de venta por unidad en bolivianos | 199 | 1.00% |
| ingreso_bs | Decimal | Unidades por precio unitario, en bolivianos | 199 | 1.00% |

**Rango de fechas por columna**

- `fecha`: 2025-01-01 a 2026-10-24; 662 fechas distintas.

**Análisis que permite y límites:** Permite analizar ventas por repuesto, categoría y mes, frecuencia de días sin ventas y preparar series diarias para pronóstico. Las ventas observadas pueden subestimar la demanda cuando hay faltantes. No permite medir ventas perdidas ni preferencias de clientes.

## Conjunto: compras

**Tamaño:** 3,600 registros y 10 columnas. **Origen:** ficticio. **Cobertura:** 30 repuestos.

**Columnas, tipos y datos faltantes**

| Columna | Tipo lógico | Significado y unidad | Faltantes | Porcentaje |
|---|---|---|---:|---:|
| id_compra | Texto | Identificador único de línea de compra | 0 | 0.00% |
| fecha_pedido | Fecha | Fecha de emisión del pedido | 0 | 0.00% |
| fecha_recepcion | Fecha | Fecha de ingreso del repuesto | 0 | 0.00% |
| sku | Texto | Identificador de repuesto | 0 | 0.00% |
| proveedor | Texto | Código ficticio del proveedor | 72 | 2.00% |
| cantidad | Entero | Unidades recibidas | 0 | 0.00% |
| costo_unitario_usd | Decimal | Costo de adquisición por unidad en dólares | 0 | 0.00% |
| tipo_cambio_bs_usd | Decimal | Bolivianos por dólar; tasa simulada de la fecha del pedido | 0 | 0.00% |
| flete_bs | Decimal | Flete de la línea de compra en bolivianos | 108 | 3.00% |
| subtotal_bs | Decimal | Cantidad por costo USD por tipo de cambio; excluye flete, tributos y otros gastos | 0 | 0.00% |

**Rango de fechas por columna**

- `fecha_pedido`: 2025-01-01 a 2026-09-24; 631 fechas distintas.
- `fecha_recepcion`: 2025-01-06 a 2026-10-23; 651 fechas distintas.

**Análisis que permite y límites:** Permite analizar cantidades compradas, precios de adquisición, variación del tipo de cambio simulado y plazos de entrega por proveedor. El costo total parcial es subtotal_bs + flete_bs; si falta el flete, no se debe tratar como cero. No incluye tributos ni permite calcular un costo de importación completo.

## Conjunto: inventario

**Tamaño:** 19,860 registros y 7 columnas. **Origen:** ficticio. **Cobertura:** 30 repuestos.

**Columnas, tipos y datos faltantes**

| Columna | Tipo lógico | Significado y unidad | Faltantes | Porcentaje |
|---|---|---|---:|---:|
| fecha | Fecha | Día del cierre | 0 | 0.00% |
| sku | Texto | Identificador de repuesto | 0 | 0.00% |
| almacen | Texto | Nombre del almacén ficticio | 99 | 0.50% |
| stock_inicial | Entero | Unidades al inicio del día | 0 | 0.00% |
| entradas | Entero | Unidades recibidas de compras | 0 | 0.00% |
| salidas | Entero | Unidades vendidas | 0 | 0.00% |
| stock_final | Entero | Stock inicial más entradas menos salidas | 0 | 0.00% |

**Rango de fechas por columna**

- `fecha`: 2025-01-01 a 2026-10-24; 662 fechas distintas.

**Análisis que permite y límites:** Permite identificar faltantes, existencias acumuladas, cobertura y evolución del stock, y contrastar salidas con ventas y entradas con recepciones. No incluye reservas, devoluciones ni ajustes.

## Calidad y relaciones entre fuentes

Porcentaje de faltantes = número de valores vacíos de la columna / número de filas del conjunto × 100. Los campos vacíos del CSV representan nulos; cero es un valor válido y no se cuenta como faltante. Los tipos indicados son lógicos: CSV no conserva tipos nativos, por lo que deben asignarse al importar. Fechas en formato ISO AAAA-MM-DD, separador coma y punto decimal.

Ventas e inventario se relacionan por fecha + sku (clave única). Compras se relaciona por sku y fecha_recepcion con las entradas de inventario. Se debe agregar primero la cantidad de compras por fecha_recepcion + sku antes de unir con inventario, para no multiplicar filas. No se deben sumar los stocks diarios como si fueran ventas; para un mes se utiliza el cierre o el promedio según el indicador.

Los faltantes fueron introducidos intencionalmente y sus porcentajes se calcularon después de generar los archivos. No hay faltantes en fechas, claves ni cantidades. Precio e ingreso tienen faltantes en las mismas 199 filas: esas ventas pueden contarse en unidades, pero no completarse monetariamente sin una regla justificada. Proveedores faltantes deben conservarse como no informados, y fletes desconocidos requieren revisión antes de calcular costos. Almacén faltante debe validarse, aunque esta simulación tiene un único almacén.

## Construcción y verificación

Generación reproducible con Python estándar y semilla 34. Se usaron 30 códigos de repuesto y 12 códigos de proveedor. Las compras ingresan entre 5 y 30 días después del pedido. Inventario inicial: 100 unidades por repuesto. Las ventas diarias están limitadas por el stock disponible; los días con cero ventas permanecen en la serie. No se incluyen precios reales ni datos personales.

Se verificaron claves únicas, fechas, cantidades no negativas, stock final = stock inicial + entradas − salidas, continuidad diaria del stock, salidas = ventas y entradas = compras recibidas. Los porcentajes documentados provienen de los CSV, no de estimaciones.

## Cumplimiento de HU-34

| Criterio | Evidencia |
|---|---|
| Cantidad de registros, columnas, tipos y fechas por conjunto | Tabla general y diccionarios individuales |
| Identifica si los datos son reales o ficticios | Tres fuentes declaradas ficticias |
| Identifica columnas con faltantes y porcentaje | Diccionarios con conteo y porcentaje para todas las columnas |
| Mínimo de 3.000 datos | Cada CSV contiene más de 3.000 filas |

El número de filas no equivale al tamaño de una muestra independiente: varias observaciones corresponden a los mismos productos en fechas consecutivas. La utilidad de los pronósticos deberá evaluarse con partición temporal y comparación con un modelo base. Esta HU describe las fuentes; no demuestra todavía una mejora en las compras.