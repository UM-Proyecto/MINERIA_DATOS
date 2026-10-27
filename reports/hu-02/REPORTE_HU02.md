# HU-02: fuente y fecha de actualización de los datos

## Resultado

Los 17 conjuntos de datos del repositorio quedan registrados con su fuente, su tipo de dato, su responsable y su última actualización válida. Trece son FICTICIOS, tres son PÚBLICOS (INE, agentes de carga y Banco Central de Bolivia) y uno es MIXTO (costos de importación, con filas documentadas, estimadas y pendientes). La carga del 27 de octubre de 2026 salió bien en los 17.

La tabla también dice hasta qué fecha llegan los datos de cada conjunto. Por ejemplo, los movimientos de la HU-17 llegan al 14 de septiembre y las ventas simuladas de la HU-34 al 24 de octubre, así que el jefe de compras ve de un vistazo qué información está vieja.

## Cómo se probó cada criterio

| Criterio | Cómo se comprueba | Resultado |
|---|---|---|
| 1. Cada conjunto muestra fuente y última actualización | `consultar` da un renglón por conjunto con fuente, tipo y fecha. Uno que nunca se cargó dice SIN CARGA VÁLIDA | Cumple |
| 2. Una actualización exitosa cambia la fecha registrada | Llega un `stock_inicial` nuevo y se vuelve a cargar | La fecha pasa de las 09:00 a las 10:00 y los datos del 31-ago al 30-sep |
| 3. Si una carga falla, conserva la última fecha válida y muestra el fallo | FALLO PROVOCADO: `conteos_fisicos` llega con una columna renombrada | Conserva la fecha de las 09:00, muestra el motivo y sale con código 1 |

Las pruebas automáticas están en `tests/test_registro_fuentes.py` (8 pruebas) y repiten lo mismo con otros fallos: archivo borrado, archivo vacío, fecha mal escrita, archivo que no es texto y columna de fecha sin valores. En todos se conserva la fecha válida anterior. También comprueban que, si un conjunto falla, los demás se actualizan igual, y que una carga buena posterior limpia el aviso.

Para asegurar que las pruebas detectan errores de verdad, se rompió el programa a propósito de dos maneras: que un fallo pisara la fecha válida, y que una carga buena no la cambiara. En los dos casos la suite falló; con el programa correcto pasa entera.

## Demostración

Se corrió sobre una copia del repositorio, para no tocar los archivos de las demás historias. Las fechas se fijan con `--fecha` para que el ejemplo se pueda repetir.

1. Carga de los 17 conjuntos a las 09:00: `cargas correctas=17 fallidas=0`.
2. Llega un `stock_inicial` nuevo con datos al 30 de septiembre y se carga a las 10:00: su fecha pasa a las 10:00 y los demás no cambian.
3. Fallo provocado a las 11:00:

```
$ python src/hu-02/registro_fuentes.py actualizar conteos_fisicos --fecha "2026-10-27 11:00 UTC"
$ python src/hu-02/registro_fuentes.py actualizar conteos_fisicos --fecha 2026-10-27 11:00 UTC
cargas correctas=0 fallidas=1
  FALLO conteos_fisicos: faltan columnas: conteo_fisico (se conserva la última fecha válida)
catalogo_repuestos       2026-10-27 09:00 UTC                                 Datos de prueba armados por el equipo (HU-17) [FICTICIO]
movimientos_inventario   2026-10-27 09:00 UTC (datos al 2026-09-14)           Datos de prueba armados por el equipo (HU-17) [FICTICIO]
reporte_depuracion       2026-10-27 09:00 UTC (datos al 2026-09-14)           Depuración de HU-17 sobre los movimientos de prueba [FICTICIO]
stock_inicial            2026-10-27 10:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
conteos_fisicos          2026-10-27 09:00 UTC (datos al 2026-09-30)           Datos de prueba armados por el equipo (HU-18) [FICTICIO]
                         >> FALLÓ la carga del 2026-10-27 11:00 UTC: faltan columnas: conteo_fisico
historial_ajustes        2026-10-27 09:00 UTC (datos al 2026-10-02 10:05:00)  Conciliación de HU-18 [FICTICIO]
comparacion_pronosticos  2026-10-27 09:00 UTC (datos al 2026-09-14)           Resultado de HU-07 sobre el reporte de depuración [FICTICIO]
historial_movimientos    2026-10-27 09:00 UTC (datos al 2026-09-14)           Generador de datos pseudoaleatorios de HU-30 [FICTICIO]
cotizaciones_proveedor   2026-10-27 09:00 UTC (datos al 2026-09-26)           Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_complementarios   2026-10-27 09:00 UTC (datos al 2026-09)              Generador de datos pseudoaleatorios de HU-31 [FICTICIO]
costos_importacion       2026-10-27 09:00 UTC (datos al 2026-10-09)           Referencias públicas de flete y estimaciones de HU-31 [MIXTO]
ine_flete_mensual        2026-10-27 09:00 UTC (datos al 2026-08)              INE Bolivia: estadísticas de comercio exterior [PUBLICO]
flete_referencias        2026-10-27 09:00 UTC (datos al 2026-10-09)           Agentes de carga (páginas públicas) [PUBLICO]
tc_series_diaria         2026-10-27 09:00 UTC (datos al 2026-10-26)           Banco Central de Bolivia y fuentes citadas (HU-32) [PUBLICO]
ventas_simuladas         2026-10-27 09:00 UTC (datos al 2026-10-24)           Datos simulados del equipo (HU-34) [FICTICIO]
compras_simuladas        2026-10-27 09:00 UTC (datos al 2026-10-23)           Datos simulados del equipo (HU-34) [FICTICIO]
inventario_simulado      2026-10-27 09:00 UTC (datos al 2026-10-24)           Datos simulados del equipo (HU-34) [FICTICIO]
(código de salida 1)
```

## Lo que no hace

No decide si el contenido de cada conjunto es correcto (eso lo revisan las HU que los producen); sólo verifica que el archivo se pueda cargar. Mientras no lleguen los datos reales de MULTIPARTES, casi todos los conjuntos son FICTICIOS y así figuran en la tabla.
