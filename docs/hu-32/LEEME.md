# HU-32: series históricas del tipo de cambio

Como jefe de compras, necesito las series de tipo de cambio de fuentes identificadas para evaluar su relación con los costos de compra. Esta carpeta guarda las series, su documentación y la comparación entre el tipo de cambio de referencia y el que la empresa usa en la práctica.

Leído el 25/10/2026. Las series del BCB son datos reales; el tipo de cambio utilizado por MULTIPARTES es FICTICIO (SINTETICO) hasta que lleguen los comprobantes reales.

## Cómo correrlo

Hace falta Python 3.8 o superior. No usa librerías externas:

    python obtener_series_tc.py

Con la misma semilla (`--semilla`, por defecto 20261019) siempre salen los mismos archivos. Los valores ficticios del tipo de cambio utilizado se pueden ajustar con `--spread-min` y `--spread-max` (por defecto 0,5 % y 3,0 % sobre la referencia).

## Qué hay en cada archivo

- `fuentes_tipo_cambio.csv` (criterio 1): una fila por serie con fuente, URL, moneda cotizada y base, unidad, período, frecuencia, tipo de cotización, lado (compra o venta), cuántas observaciones se obtuvieron y si el dato es DOCUMENTADO o SINTETICO.
- `tc_series_diaria.csv` (criterio 2): fecha y valor de cada observación, tal como la publicó la fuente, con su fuente y fecha de actualización.
- `tc_fechas_faltantes.csv` (criterio 2): rangos de fechas sin dato en cada serie. No se rellenan ni se estiman.
- `tc_referencia_vs_utilizado.csv` (criterio 3): cada compra con su tipo de cambio de referencia (BCB) y el efectivamente utilizado, y cuánto cambia el costo en bolivianos.
- `insumos_publicos/`: la captura del TCO del BCB (`bcb_tco_diario_captura_2026-10-25.csv`, con el texto original de cada fecha y valor) y los puntos sueltos documentados (`puntos_documentados.csv`), con su huella en `SHA256SUMS.txt`.
- `insumos_equipo/`: el movimiento ficticio de la HU-30 (copiado tal cual) del que se toman las órdenes de compra.

## Las series

| Serie | Qué es | Período obtenido | Estado |
|---|---|---|---|
| TCO_BCB | Tipo de cambio oficial del BCB, flexible | 27/06/2026 a 26/10/2026, 122 días | Completa, sin fechas faltantes |
| OFICIAL_FIJO_BCB (compra 6,86 / venta 6,96) | Tipo fijo anterior | Solo 01/12/2025 | 207 días sin verificar hasta el 26/06/2026 |
| VRD_BCB (compra 7,85 / venta 9,32 el 01/12/2025) | Valor referencial del dólar | Solo 01/12/2025 | 207 días pendientes de descarga |
| PARALELO_P2P_VENTA | Dólar paralelo, promedio de plataformas P2P | Solo 23/10/2026 (11,99) | Sin historial |
| TC_UTILIZADO_EMPRESA | Lo que MULTIPARTES paga de verdad | Ninguno real | SINTETICO, pendiente del dato real |

Unidad de todas: bolivianos por 1 dólar estadounidense (Bs/USD).

## Cómo se lee el TCO

- El TCO es la mediana ponderada por monto de las compras de dólares que hacen los bancos a sus clientes. Es un valor de referencia, no el precio al que una empresa compra dólares.
- Cada fecha trae el TCO vigente ese día. El que se publica el viernes rige sábado, domingo y lunes, por eso esos días repiten el valor y no son observaciones independientes.
- Los valores del 26/10/2026 se publicaron por adelantado; esa fecha todavía no ocurría al leer.
- El TCO se mueve mucho: bajó hasta 9,73 el 27/06, subió a 12,64 el 09/09, cayó a 9,83 el 17/09 y volvió a 11,88 el 26/10. Un mismo pago de 1.000 USD cuesta unos Bs 2.810 más el 09/09 que el 17/09.
- El BCB muestra el TCO desde el 27/06/2026. Otro sitio secundario habla del 29/06; se tomó la fecha de la tabla del BCB.

## Referencia vs. utilizado (criterio 3)

- `tc_referencia_bcb` es el TCO de la fecha de la operación.
- `tc_utilizado_empresa` es el tipo de cambio de la operación real de la empresa. Hoy es ficticio (referencia más un sobreprecio entre 0,5 % y 3,0 %) y está marcado SINTETICO.
- Solo 23 de las 111 órdenes de compra tienen referencia, porque las otras 88 son anteriores al 27/06/2026, cuando empieza el TCO. Esas quedan en `SIN REFERENCIA` y no se estiman.
- La fecha de la operación es la del movimiento de inventario; con los comprobantes reales debe ser la fecha del pago.

## Qué falta

1. Descargar a mano la serie histórica del valor referencial del BCB (01/12/2025 a 26/06/2026), compra y venta. La página del BCB la carga con JavaScript y no se pudo leer automáticamente.
2. Conseguir un historial del dólar paralelo con fuente y fecha, si el análisis lo necesita.
3. Reemplazar el tipo de cambio utilizado ficticio por el de los comprobantes reales de MULTIPARTES (banco o casa de cambio, fecha de pago, monto en USD y en Bs). Hasta entonces, los resultados de costo en bolivianos son de prueba.

Los valores del tipo de cambio utilizado y los montos en USD de las órdenes de compra no representan a MULTIPARTES.
