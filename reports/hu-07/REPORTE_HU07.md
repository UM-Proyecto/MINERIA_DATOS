# HU-07 — Comparación de pronósticos de salidas de repuestos

## Decisión para compras

**Con el historial disponible no se puede seleccionar una técnica confiable para planificar compras por época del año.** El repositorio registra movimientos entre el **1 y el 14 de septiembre de 2026**: una sola época y apenas cinco salidas válidas. Sí se pueden calcular errores sobre días reservados, pero un MAE bajo en estos datos escasos no demuestra capacidad para anticipar demanda futura. La acción justificada es reunir más historial de ventas, disponibilidad de stock y movimientos pendientes de revisión antes de elegir un método para compras.

## Datos y comparación

La fuente es `data/processed/hu-17/reporte_depuracion_final.csv`. Se usa `codigo_unico` para consolidar códigos equivalentes de un mismo repuesto. Solo las filas `SALIDA` con estado `ORIGINAL` cuentan como ventas observadas: hay **5**. Se excluyen **4 duplicados** y **1 salida pendiente de revisión**. `ENTRADA` no representa demanda. Los días sin salidas registradas se completan con cero; esto permite una serie diaria, pero no prueba que la demanda real haya sido cero si faltó stock o faltan registros.

| Fase | Periodos diarios | Uso |
|---|---:|---|
| Entrenamiento | 1–9 de septiembre de 2026 (9 días) | Únicos datos disponibles para construir cada pronóstico. |
| Evaluación reservada | 10–14 de septiembre de 2026 (5 días) | Se comparan los tres métodos en **exactamente los mismos cinco días** para cada repuesto. |

Los cinco pronósticos de cada método se calculan de una vez al terminar el 9 de septiembre. Para los días siguientes del horizonte se usan sus propios pronósticos, **nunca las ventas reales del tramo reservado**. Esto impide que un método gane por haber visto datos de evaluación.

| Método | Regla de pronóstico | Papel en la comparación |
|---|---|---|
| Último periodo | Repite la venta observada o pronosticada del día anterior. | Referencia simple. |
| Promedio móvil de 3 días | Promedia los tres valores diarios más recientes, observados antes del corte o pronosticados después. | Suaviza variaciones diarias. |
| Mismo día de la semana | Repite el valor de siete días antes. | Explora repetición semanal; **no mide estacionalidad anual**. |

**MAE** = suma de `|venta observada − pronóstico|` dividida entre **5 días evaluados**. Su unidad es *repuestos por día*. Un MAE menor indica mejor ajuste solo en esos cinco días; no expresa margen de seguridad de inventario ni costo de quedarse sin stock. El CSV también informa `mae_por_mes`; aquí solo existe **septiembre de 2026**, así que no hay dos épocas del año que comparar.

## Resultados por repuesto

En la columna «días con ventas» se muestra entrenamiento / evaluación. Los tres MAE se presentan en el orden último periodo / promedio móvil / mismo día de semana. Todos corresponden a los cinco días del **10 al 14 de septiembre**.

| Repuesto | Días con ventas | MAE: último / móvil / semanal | Limitación específica y decisión |
|---|---:|---:|---|
| REP-0001 | 1 / 0 | 0.000 / 0.000 / 1.000 | No hubo ventas en prueba; el MAE 0 de los dos primeros solo refleja pronósticos cero. Sin selección fiable. |
| REP-0002 | 0 / 0 | 0.000 / 0.000 / 0.000 | No hay ventas válidas en ninguna fase. Sin selección fiable. |
| REP-0003 | 1 / 0 | 0.000 / 0.000 / 0.800 | No hubo ventas en prueba; el MAE 0 no valida los métodos. Sin selección fiable. |
| REP-0004 | 0 / 0 | 0.000 / 0.000 / 0.000 | No hay ventas válidas en ninguna fase. Sin selección fiable. |
| REP-0005 | 0 / 1 | 0.400 / 0.400 / 0.400 | Una salida anterior al corte quedó pendiente de revisión y se excluyó; ningún método vio ventas válidas al entrenar. Sin selección fiable. |
| REP-0006 | 0 / 0 | 0.000 / 0.000 / 0.000 | No hay ventas válidas en ninguna fase. Sin selección fiable. |
| REP-0007 | 0 / 1 | 0.600 / 0.600 / 0.600 | La única venta válida aparece después del corte; los métodos empatan al pronosticar cero. Sin selección fiable. |
| REP-0008 | 0 / 0 | 0.000 / 0.000 / 0.000 | No hay ventas válidas en ninguna fase. Sin selección fiable. |
| REP-0009 | 0 / 0 | 0.000 / 0.000 / 0.000 | No hay ventas válidas en ninguna fase. Sin selección fiable. |
| REP-0010 | 0 / 1 | 0.400 / 0.400 / 0.400 | La única venta válida aparece después del corte; los métodos empatan al pronosticar cero. Sin selección fiable. |

Por ejemplo, REP-0007 vendió 3 unidades en uno de los cinco días reservados. Los tres métodos pronosticaron cero cada día, por lo que su MAE es `3 / 5 = 0.600`. El empate no significa que los métodos sean igual de útiles para comprar: ninguno anticipó la venta.

## Qué falta para elegir una técnica por época

Se necesitan al menos **12 meses anteriores para entrenar y 12 meses posteriores para evaluar**, con registros de salidas y disponibilidad de stock suficientemente completos para cada repuesto. Con un historial así, el mismo programa permite reservar un año (`--dias-prueba 365`) y el CSV separa el MAE por mes calendario. Para tomar una decisión de compras también habría que revisar si el error se mantiene bajo en meses con ventas, no solo en meses sin movimiento, y contrastar el pronóstico con plazos de reposición y faltantes de stock.

La columna `seleccion` del CSV queda en `SIN_SELECCION_FIABLE` para los diez repuestos actuales. Se evita recomendar una técnica a partir de empates y MAE cero producidos por la escasez de ventas.
