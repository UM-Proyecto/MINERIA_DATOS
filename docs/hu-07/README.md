# HU-07: comparación de pronósticos de demanda

El resultado explicado, con una fila por repuesto y una conclusión para compras, está en [REPORTE_HU07.md](../../reports/hu-07/REPORTE_HU07.md). Los valores detallados de MAE y las limitaciones por método están en `data/processed/hu-07/comparacion_pronosticos.csv`.

Para reproducir el CSV desde la raíz del repositorio:

```bash
python src/hu-07/comparar_pronosticos.py
```

La fuente predeterminada es `data/processed/hu-17/reporte_depuracion_final.csv`. Se agrupan las salidas `ORIGINAL` por `codigo_unico` y día; se excluyen duplicados y movimientos pendientes de revisión. Cada día sin salidas registradas se trata como cero **ventas observadas**, que pueden ser menores que la demanda real si hubo faltantes de stock.

Se reservan los últimos cinco días para evaluación. Cada método pronostica esos cinco días usando únicamente los días anteriores al corte y sus propias predicciones: último periodo, promedio móvil de tres días y mismo día de la semana anterior. Se calcula MAE en unidades por día sobre exactamente las mismas fechas para cada repuesto. `--dias-prueba N` cambia el horizonte; `--entrada RUTA` y `--salida RUTA` permiten usar otro reporte con las mismas columnas y guardar el CSV en otra ubicación.

El CSV de salida indica MAE global y por mes calendario, cantidad y rango de periodos evaluados, ventas en entrenamiento, registros excluidos, límites por repuesto y selección. La selección requiere al menos 12 meses de entrenamiento, 12 meses reservados para evaluación, tres días con ventas en entrenamiento, ventas en cada mes evaluado y ninguna salida pendiente de revisión; con un historial de dos años se puede usar, por ejemplo, `--dias-prueba 365`. Aun con ese mínimo, elegir un método de compras requiere revisar faltantes de stock. El método `mismo_dia_semana` mide un patrón semanal, **no** una temporada anual.

El archivo actual contiene movimientos del 1 al 14 de septiembre de 2026. Por eso sus MAE son una comprobación técnica del procedimiento y ninguna selección sirve todavía como base confiable para compras por época del año. Se necesita historial que abarque varios meses y, preferiblemente, varios ciclos anuales.

Verificar la separación temporal y el tratamiento de duplicados:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
