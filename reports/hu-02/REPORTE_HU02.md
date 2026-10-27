# HU-02 — Fuente y fecha de actualización de los datos

## Resultado

**Los 13 conjuntos de datos del repositorio quedaron registrados con su fuente, su tipo de dato y su última actualización.** Diez son FICTICIOS (armados por el equipo mientras no lleguen los datos de MULTIPARTES), dos son públicos (INE y páginas de agentes de carga) y uno es MIXTO (costos de importación, con filas documentadas, estimadas y pendientes). La primera carga real se hizo el 26 de octubre de 2026 y las 13 salieron bien.

Además de la fecha en que se cargó, la tabla muestra hasta qué fecha llegan los datos. Por ejemplo, los movimientos llegan al 14 de septiembre y el stock inicial al 31 de agosto, así que un jefe de compras ve que la información tiene más de un mes.

## Cómo se probó cada criterio

| Criterio | Cómo se comprueba | Resultado |
|---|---|---|
| 1. Cada conjunto muestra fuente y última actualización | `consultar` da un renglón por conjunto con fuente, tipo y fecha. Uno que nunca se cargó dice SIN CARGA VÁLIDA | Cumple (pruebas y corrida real) |
| 2. Una actualización exitosa cambia la fecha | Se cargó todo el 20-oct; llegó un stock_inicial nuevo y se actualizó el 26-oct | La fecha pasó al 26-oct y los datos al 30-sep |
| 3. Si una carga falla, conserva la última fecha válida y muestra el fallo | FALLO PROVOCADO: conteos_fisicos llegó con una columna renombrada | Conserva el 20-oct, muestra el motivo y queda en el historial |

Las pruebas automáticas (`python -m unittest test_registro_fuentes`, 8 pruebas) repiten lo mismo con otros fallos: archivo borrado, archivo vacío, fecha mal escrita, archivo que no es texto y columna de fecha sin ningún valor. En todos se conserva la fecha válida anterior. También comprueban que, si un conjunto falla, los demás se actualizan igual, y que una carga buena posterior limpia el aviso.

Para asegurar que las pruebas detectan un error de verdad, se rompió el programa a propósito de dos maneras: que el fallo pisara la fecha, y que una carga buena no la cambiara. Con la primera versión rota fallaron 6 de las pruebas y con la segunda 3; con el programa correcto pasan las 8.

## Hallazgo de la primera carga

La primera versión rechazaba `hu31_costos_importacion.csv` porque cinco filas tienen un rango de fechas (`2025-09 a 2026-08`) y cuatro costos PENDIENTE no tienen fecha. Las dos cosas son correctas en ese archivo, así que ahora un rango cuenta por su fecha final y una celda vacía se toma como dato pendiente. Una fecha mal escrita, como `31/08/2026`, sigue siendo fallo.

## Corrida de demostración

Se hizo sobre una copia temporal del repositorio, para no tocar los archivos de las demás historias. Las fechas se fijan con `--fecha` para que el ejemplo se pueda repetir.

```
$ python registro_fuentes.py actualizar --todos --fecha '2026-10-20 10:00 UTC'
cargas correctas=13 fallidas=0
catalogo_repuestos       2026-10-20 10:00 UTC                                 Datos de prueba armados por el equipo (HU-17) [FICTICIO]
movimientos_inventario   2026-10-20 10:00 UTC (datos al 2026-09-14)           Datos de prueba armados por el equipo (HU-17) [FICTICIO]
reporte_depuracion       2026-10-20 10:00 UTC (datos al 2026-09-14)           Depuración de HU-17 sobre los movimientos de prueba [FICTICIO]
stock_inicial            2026-10-20 10:00 UTC (datos al 2026-08-31)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
conteos_fisicos          2026-10-20 10:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
historial_ajustes        2026-10-20 10:00 UTC (datos al 2026-10-02 10:05:00)  Conciliación de HU-18 [FICTICIO]
comparacion_pronosticos  2026-10-20 10:00 UTC (datos al 2026-09-14)           Resultado de HU-07 sobre el reporte de depuración [FICTICIO]
historial_movimientos    2026-10-20 10:00 UTC (datos al 2026-09-14)           Generador de datos pseudoaleatorios de HU-30 [FICTICIO]
cotizaciones_proveedor   2026-10-20 10:00 UTC (datos al 2026-09-26)           Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_complementarios   2026-10-20 10:00 UTC (datos al 2026-09)              Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_importacion       2026-10-20 10:00 UTC (datos al 2026-10-09)           Referencias públicas de flete y estimaciones de HU-31 [MIXTO]
ine_flete_mensual        2026-10-20 10:00 UTC (datos al 2026-08)              INE Bolivia: estadísticas de comercio exterior [PUBLICO]
flete_referencias        2026-10-20 10:00 UTC (datos al 2026-10-09)           Agentes de carga (páginas públicas) [PUBLICO]
(código de salida 0)

# se cambia la fecha de corte de un renglón de stock_inicial (llega un archivo nuevo)

$ python registro_fuentes.py actualizar stock_inicial --fecha '2026-10-26 15:00 UTC'
cargas correctas=1 fallidas=0
catalogo_repuestos       2026-10-20 10:00 UTC                                 Datos de prueba armados por el equipo (HU-17) [FICTICIO]
movimientos_inventario   2026-10-20 10:00 UTC (datos al 2026-09-14)           Datos de prueba armados por el equipo (HU-17) [FICTICIO]
reporte_depuracion       2026-10-20 10:00 UTC (datos al 2026-09-14)           Depuración de HU-17 sobre los movimientos de prueba [FICTICIO]
stock_inicial            2026-10-26 15:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
conteos_fisicos          2026-10-20 10:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
historial_ajustes        2026-10-20 10:00 UTC (datos al 2026-10-02 10:05:00)  Conciliación de HU-18 [FICTICIO]
comparacion_pronosticos  2026-10-20 10:00 UTC (datos al 2026-09-14)           Resultado de HU-07 sobre el reporte de depuración [FICTICIO]
historial_movimientos    2026-10-20 10:00 UTC (datos al 2026-09-14)           Generador de datos pseudoaleatorios de HU-30 [FICTICIO]
cotizaciones_proveedor   2026-10-20 10:00 UTC (datos al 2026-09-26)           Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_complementarios   2026-10-20 10:00 UTC (datos al 2026-09)              Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_importacion       2026-10-20 10:00 UTC (datos al 2026-10-09)           Referencias públicas de flete y estimaciones de HU-31 [MIXTO]
ine_flete_mensual        2026-10-20 10:00 UTC (datos al 2026-08)              INE Bolivia: estadísticas de comercio exterior [PUBLICO]
flete_referencias        2026-10-20 10:00 UTC (datos al 2026-10-09)           Agentes de carga (páginas públicas) [PUBLICO]
(código de salida 0)

# FALLO PROVOCADO: conteos_fisicos llega con la columna conteo_fisico renombrada

$ python registro_fuentes.py actualizar conteos_fisicos --fecha '2026-10-26 15:30 UTC'
cargas correctas=0 fallidas=1
  FALLO conteos_fisicos: faltan columnas: conteo_fisico (se conserva la última fecha válida)
catalogo_repuestos       2026-10-20 10:00 UTC                                 Datos de prueba armados por el equipo (HU-17) [FICTICIO]
movimientos_inventario   2026-10-20 10:00 UTC (datos al 2026-09-14)           Datos de prueba armados por el equipo (HU-17) [FICTICIO]
reporte_depuracion       2026-10-20 10:00 UTC (datos al 2026-09-14)           Depuración de HU-17 sobre los movimientos de prueba [FICTICIO]
stock_inicial            2026-10-26 15:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
conteos_fisicos          2026-10-20 10:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
                         >> FALLÓ la carga del 2026-10-26 15:30 UTC: faltan columnas: conteo_fisico
historial_ajustes        2026-10-20 10:00 UTC (datos al 2026-10-02 10:05:00)  Conciliación de HU-18 [FICTICIO]
comparacion_pronosticos  2026-10-20 10:00 UTC (datos al 2026-09-14)           Resultado de HU-07 sobre el reporte de depuración [FICTICIO]
historial_movimientos    2026-10-20 10:00 UTC (datos al 2026-09-14)           Generador de datos pseudoaleatorios de HU-30 [FICTICIO]
cotizaciones_proveedor   2026-10-20 10:00 UTC (datos al 2026-09-26)           Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_complementarios   2026-10-20 10:00 UTC (datos al 2026-09)              Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_importacion       2026-10-20 10:00 UTC (datos al 2026-10-09)           Referencias públicas de flete y estimaciones de HU-31 [MIXTO]
ine_flete_mensual        2026-10-20 10:00 UTC (datos al 2026-08)              INE Bolivia: estadísticas de comercio exterior [PUBLICO]
flete_referencias        2026-10-20 10:00 UTC (datos al 2026-10-09)           Agentes de carga (páginas públicas) [PUBLICO]
(código de salida 1)

$ python registro_fuentes.py consultar
catalogo_repuestos       2026-10-20 10:00 UTC                                 Datos de prueba armados por el equipo (HU-17) [FICTICIO]
movimientos_inventario   2026-10-20 10:00 UTC (datos al 2026-09-14)           Datos de prueba armados por el equipo (HU-17) [FICTICIO]
reporte_depuracion       2026-10-20 10:00 UTC (datos al 2026-09-14)           Depuración de HU-17 sobre los movimientos de prueba [FICTICIO]
stock_inicial            2026-10-26 15:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
conteos_fisicos          2026-10-20 10:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
                         >> FALLÓ la carga del 2026-10-26 15:30 UTC: faltan columnas: conteo_fisico
historial_ajustes        2026-10-20 10:00 UTC (datos al 2026-10-02 10:05:00)  Conciliación de HU-18 [FICTICIO]
comparacion_pronosticos  2026-10-20 10:00 UTC (datos al 2026-09-14)           Resultado de HU-07 sobre el reporte de depuración [FICTICIO]
historial_movimientos    2026-10-20 10:00 UTC (datos al 2026-09-14)           Generador de datos pseudoaleatorios de HU-30 [FICTICIO]
cotizaciones_proveedor   2026-10-20 10:00 UTC (datos al 2026-09-26)           Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_complementarios   2026-10-20 10:00 UTC (datos al 2026-09)              Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_importacion       2026-10-20 10:00 UTC (datos al 2026-10-09)           Referencias públicas de flete y estimaciones de HU-31 [MIXTO]
ine_flete_mensual        2026-10-20 10:00 UTC (datos al 2026-08)              INE Bolivia: estadísticas de comercio exterior [PUBLICO]
flete_referencias        2026-10-20 10:00 UTC (datos al 2026-10-09)           Agentes de carga (páginas públicas) [PUBLICO]
(código de salida 0)

# historial_cargas.csv (últimas 3 líneas)
2026-10-20 10:00 UTC,flete_referencias,OK,6,2026-10-09,
2026-10-26 15:00 UTC,stock_inicial,OK,10,2026-09-30,
2026-10-26 15:30 UTC,conteos_fisicos,FALLO,,,faltan columnas: conteo_fisico
```
