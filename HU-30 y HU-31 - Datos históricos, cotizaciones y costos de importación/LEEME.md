# SCRUM-6 y SCRUM-7: historial, cotizaciones y costos de importación

Esta carpeta guarda los datos y el código de la HU-30 (historial de ventas, compras e inventario) y de la HU-31 (cotizaciones y costos de importación). Mientras no lleguen los datos reales de MULTIPARTES, todo se trabaja con datos FICTICIOS generados con números pseudoaleatorios, y cada registro lo indica.

## Cómo correrlo

Hace falta Python 3.8 o superior. No usa librerías externas, así que funciona igual en Windows, Linux o Mac y desde cualquier carpeta:

    python ejecutar_todo.py

Eso genera los datos ficticios, los carga con su registro de trazabilidad y arma los costos de importación. Con la misma semilla (`--semilla`, por defecto 20261019) y la misma fecha (`--fecha-actualizacion`) siempre salen los mismos archivos.

## Qué hay en cada carpeta

- `insumos_equipo/`: los archivos de Sabrina del repositorio del equipo (HU-17 y HU-18), con su huella en `SHA256SUMS.txt`. El código los lee tal cual y no los modifica.
- `insumos_publicos/`: datos públicos (INE y cotizaciones de referencia de flete) para el costo de importación.
- `parametros_sinteticos.csv`: costo base y proveedor principal de cada repuesto, usados solo para inventar los datos ficticios.
- `sintetico/`: lo que se genera. `movimientos_inventario_sintetico.csv` conserva los movimientos de septiembre de Sabrina con su precio agregado, y el historial anterior termina exactamente en su stock inicial del 31 de agosto. `hu30/` guarda el registro de la carga y la copia del original.
- `hu31_costos_importacion.csv`: costos con su respaldo, separados en DOCUMENTADO, ESTIMACION y PENDIENTE.

## Cuando lleguen los datos reales

1. Reemplazar el movimiento ficticio por el archivo real con la misma estructura y una columna `precio` o `precio_unitario_usd`.
2. Correr `python carga_historico.py --movimientos <archivo real>`: reporta campos faltantes, códigos que no están en el catálogo y guarda la copia del original.
3. Cargar las cotizaciones y facturas reales en lugar de las filas SINTETICO.

Los precios, cantidades y porcentajes de los datos ficticios no representan a MULTIPARTES.
