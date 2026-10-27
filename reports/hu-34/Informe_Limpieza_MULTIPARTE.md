# Limpieza completa de datos de MULTIPARTE

Datos ficticios para fines académicos. Los valores completados son estimaciones y no información real recuperada de la empresa.

## Tamaño y faltantes antes y después

| Fuente | Filas antes | Filas después | Columnas antes | Columnas después | Celdas vacías antes | Celdas vacías después | Duplicados eliminados |
|---|---:|---:|---:|---:|---:|---:|---:|
| ventas | 19860 | 19860 | 6 | 8 | 398 | 0 | 0 |
| compras | 3600 | 3600 | 10 | 12 | 180 | 0 | 0 |
| inventario | 19860 | 19860 | 7 | 8 | 99 | 0 | 0 |

No se eliminaron filas: no se encontraron duplicados ni conflictos de claves. Se conservaron 43.320 registros. Los ceros de unidades vendidas son válidos y se mantienen.

## Reglas aplicadas y trazabilidad

- Precios: 199 valores completados con el último precio anterior disponible del mismo SKU. Si hay varios días vacíos consecutivos, se arrastra el último precio conocido. Campo precio_estimado.
- Ingresos: 199 valores calculados como unidades vendidas por precio completado, redondeados a dos decimales. Campo ingreso_recalculado.
- Fletes: 108 valores estimados con la mediana global del flete por unidad de las compras originalmente completas: 2.50558704 Bs/unidad. Se multiplica por las unidades de cada compra y se redondea a dos decimales. Campo flete_estimado.
- Proveedores: 72 etiquetas NO_INFORMADO. La identidad sigue desconocida; no se inventaron proveedores. Campo proveedor_no_informado.
- Almacén: 99 valores completados como Central por el supuesto documentado de un único almacén ficticio. Campo almacen_completado.
- Se normalizaron textos y se validaron fechas, enteros, claves, cantidades y relaciones. No se detectaron formatos incorrectos que requirieran corrección en estos CSV.

## Faltantes por columna original

| Fuente | Columna | Faltantes antes | Porcentaje antes | Faltantes después | Porcentaje después |
|---|---|---:|---:|---:|---:|
| ventas | fecha | 0 | 0.00% | 0 | 0.00% |
| ventas | sku | 0 | 0.00% | 0 | 0.00% |
| ventas | categoria | 0 | 0.00% | 0 | 0.00% |
| ventas | unidades_vendidas | 0 | 0.00% | 0 | 0.00% |
| ventas | precio_unitario_bs | 199 | 1.00% | 0 | 0.00% |
| ventas | ingreso_bs | 199 | 1.00% | 0 | 0.00% |
| compras | id_compra | 0 | 0.00% | 0 | 0.00% |
| compras | fecha_pedido | 0 | 0.00% | 0 | 0.00% |
| compras | fecha_recepcion | 0 | 0.00% | 0 | 0.00% |
| compras | sku | 0 | 0.00% | 0 | 0.00% |
| compras | proveedor | 72 | 2.00% | 0 | 0.00% |
| compras | cantidad | 0 | 0.00% | 0 | 0.00% |
| compras | costo_unitario_usd | 0 | 0.00% | 0 | 0.00% |
| compras | tipo_cambio_bs_usd | 0 | 0.00% | 0 | 0.00% |
| compras | flete_bs | 108 | 3.00% | 0 | 0.00% |
| compras | subtotal_bs | 0 | 0.00% | 0 | 0.00% |
| inventario | fecha | 0 | 0.00% | 0 | 0.00% |
| inventario | sku | 0 | 0.00% | 0 | 0.00% |
| inventario | almacen | 99 | 0.50% | 0 | 0.00% |
| inventario | stock_inicial | 0 | 0.00% | 0 | 0.00% |
| inventario | entradas | 0 | 0.00% | 0 | 0.00% |
| inventario | salidas | 0 | 0.00% | 0 | 0.00% |
| inventario | stock_final | 0 | 0.00% | 0 | 0.00% |

Los indicadores nuevos son booleanos True/False sin valores vacíos. True identifica una intervención o una identidad desconocida. El porcentaje se calcula como celdas vacías de la columna dividido entre filas del conjunto, por 100.

## Tipos de datos y períodos

Fechas en formato AAAA-MM-DD; códigos y categorías como texto; cantidades y stocks como enteros; precios, ingresos, flete, costo y tipo de cambio como decimales. CSV no almacena tipos nativos: deben asignarse al importar.

| Fuente | Columna de fecha | Desde | Hasta |
|---|---|---|---|
| ventas | fecha | 2025-01-01 | 2026-10-24 |
| compras | fecha_pedido | 2025-01-01 | 2026-09-24 |
| compras | fecha_recepcion | 2025-01-06 | 2026-10-23 |
| inventario | fecha | 2025-01-01 | 2026-10-24 |

## Controles ejecutados

| Control | Incidencias |
|---|---:|
| ventas: celdas vacías | 0 |
| ventas: números negativos | 0 |
| ventas: números no finitos | 0 |
| ventas: claves repetidas | 0 |
| ventas: período de fecha | 0 |
| compras: celdas vacías | 0 |
| compras: números negativos | 0 |
| compras: números no finitos | 0 |
| compras: claves repetidas | 0 |
| compras: período de fecha_pedido | 0 |
| compras: período de fecha_recepcion | 0 |
| inventario: celdas vacías | 0 |
| inventario: números negativos | 0 |
| inventario: números no finitos | 0 |
| inventario: claves repetidas | 0 |
| inventario: período de fecha | 0 |
| Recepción anterior al pedido | 0 |
| Balance de inventario | 0 |
| Continuidad diaria del stock | 0 |
| Stock inicial de apertura | 0 |
| ventas: 662 fechas por SKU | 0 |
| inventario: 662 fechas por SKU | 0 |
| Claves de ventas e inventario | 0 |
| Ventas iguales a salidas | 0 |
| Recepciones sin inventario | 0 |
| Entradas iguales a recepciones | 0 |
| Ingreso igual a unidades por precio | 0 |
| Subtotal de compras | 0 |
| SKU de compras existentes | 0 |
| ventas: nulos en CSV exportado | 0 |
| ventas: filas conservadas al exportar | 0 |
| compras: nulos en CSV exportado | 0 |
| compras: filas conservadas al exportar | 0 |
| inventario: nulos en CSV exportado | 0 |
| inventario: filas conservadas al exportar | 0 |

Se ejecutaron 35 controles sin incidencias. Se comprobaron balance, continuidad de stock, correspondencia entre ventas y salidas y entre compras recibidas y entradas. Los importes se compararon con tolerancia de 0,011 Bs por redondeo.

## Interpretación y límites

Los tres CSV finales no tienen celdas vacías. La ausencia de nulos no convierte los valores estimados en observaciones conocidas. NO_INFORMADO debe permanecer separado en cualquier análisis por proveedor. Los resultados monetarios incluyen estimaciones y deben presentarse como tales.

La mediana global de fletes utiliza todas las compras completas del período, por lo que esta regla se aplica a la limpieza descriptiva de esta simulación. Si se utiliza el flete en un modelo con evaluación temporal, la mediana debe estimarse únicamente con el conjunto de entrenamiento. El relleno de precios usa valores anteriores del mismo repuesto.

El stock de apertura de 100 unidades y los 662 días son reglas específicas de estos archivos. Las ventas pueden subestimar la demanda si no hay existencias. El subtotal de compras excluye flete y tributos: sumar flete proporciona un costo parcial, no el costo total de importación.

## Comentario para la subtarea

Se limpiaron y completaron los datos ficticios de ventas, compras e inventario de MULTIPARTE, conservando los 43.320 registros. No se encontraron duplicados ni se eliminaron filas. Se completaron los precios con valores anteriores del mismo repuesto, se recalcularon sus ingresos y se estimaron los fletes con el costo mediano por unidad. También se identificaron los proveedores desconocidos y se completó el almacén según la simulación. Los archivos finales no presentan celdas vacías y los valores estimados quedaron marcados para distinguirlos de los datos originales.