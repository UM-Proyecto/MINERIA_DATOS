# HU-09: alertas de riesgo de faltantes

**Modo: INTEGRACION. Datos operativos de origen ficticio/sintético; no son información operativa real de MULTIPARTES.**

Fecha de evaluación: 2026-11-10. Corte del stock: 2026-09-30. Antigüedad máxima admitida: 30 días.

## Resultados

ALERTA: **0**. SIN_ALERTA: **0**. NO_CALCULABLE: **10**.

NO_CALCULABLE conserva importes de demanda durante entrega y faltante vacíos, nunca cero. Los registros permanecen visibles.

| Prioridad | Código | Proveedor | Stock disponible | Demanda durante entrega | Plazo | Tipo días | Faltante | Estado | Motivos |
|---:|---|---|---:|---:|---:|---|---:|---|---|
|  | REP-0001 | Bosch Bolivia |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; MOVIMIENTOS_PENDIENTES_REVISION; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0002 | Importadora Toyota |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0003 | Frenos Bolivia |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; MOVIMIENTOS_PENDIENTES_REVISION; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0004 | NGK Bolivia |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; MOVIMIENTOS_PENDIENTES_REVISION; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0005 | Bosch Bolivia |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; DIFERENCIA_CONTEO_PENDIENTE; MOVIMIENTOS_PENDIENTES_REVISION; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0006 | Autopartes Andinas |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0007 | NGK Bolivia |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; DIFERENCIA_CONTEO_PENDIENTE; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0008 | Importadora Toyota |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; MOVIMIENTOS_PENDIENTES_REVISION; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0009 | Suspensiones SRL |  |  | 30 | no_definido |  | NO_CALCULABLE | CALENDARIO_PLAZO_NO_DEFINIDO; DEMANDA_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |
|  | REP-0010 | NGK Bolivia |  |  |  | no_definido |  | NO_CALCULABLE | COTIZACION_VENCIDA; DEMANDA_FALTANTE; PLAZO_FALTANTE; RESERVAS_Y_BLOQUEOS_DESCONOCIDOS; STOCK_DESACTUALIZADO; STOCK_DISPONIBLE_NO_VERIFICABLE |

![Prioridades de faltantes](prioridades.svg)

## Información faltante y bloqueos

- CALENDARIO_PLAZO_NO_DEFINIDO: 1 repuestos.
- COTIZACION_VENCIDA: 9 repuestos.
- DEMANDA_FALTANTE: 10 repuestos.
- DIFERENCIA_CONTEO_PENDIENTE: 2 repuestos.
- MOVIMIENTOS_PENDIENTES_REVISION: 5 repuestos.
- PLAZO_FALTANTE: 9 repuestos.
- RESERVAS_Y_BLOQUEOS_DESCONOCIDOS: 10 repuestos.
- STOCK_DESACTUALIZADO: 10 repuestos.
- STOCK_DISPONIBLE_NO_VERIFICABLE: 10 repuestos.

## Stock, duplicados y ajustes

| Código | Registrado | Conteo físico | Ajustado | IDs ajustes del corte | Duplicados excluidos | Pendientes HU-17 | Rechazos históricos |
|---|---:|---:|---:|---|---|---|---:|
| REP-0001 | 95 | 95 | 95 |  | 1004 | 1001, 1002 | 0 |
| REP-0002 | 55 | 53 | 53 | 2 | 1006 |  | 0 |
| REP-0003 | 31 | 31 | 31 |  | 1009 | 1007 | 0 |
| REP-0004 | 28 | 18 | 18 | 1 |  | 1010 | 0 |
| REP-0005 | 17 | 18 | 17 |  |  | 1012, 1013 | 0 |
| REP-0006 | 130 | 130 | 130 |  | 1016 |  | 0 |
| REP-0007 | 9 | 8 | 9 |  | 1018 |  | 4 |
| REP-0008 | 45 | 45 | 45 |  |  | 1019 | 0 |
| REP-0009 | 45 | 45 | 45 |  | 1022 |  | 0 |
| REP-0010 | 7 | 7 | 7 |  | 1024 |  | 0 |

Política de disponibilidad: no_confirmada. No hay datos de reservas ni bloqueos; el stock registrado o contado no se presenta como disponible.

Se reconstruye el registrado con stock inicial y movimientos HU-17 sin DUPLICADO, incluyendo pendientes como hace HU-18. Los ajustes anteriores ya están en ese saldo; los del mismo corte se añaden una vez solo con respaldo AJUSTE_APLICADO conocido a la evaluación. Los rechazados no modifican stock. Una diferencia física pendiente impide verificar disponibilidad.

## Método y unidades

Tasa diaria constante × días naturales de consumo; serie diaria = suma de las fechas exactas de entrega. Ventana: desde el día siguiente a la evaluación hasta recepción inclusive. El stock no se proyecta automáticamente desde su corte: aceptar su antigüedad requiere una política explícita.

Demanda semanal/7 o demanda mensual/días reales de cada mes solo con distribución uniforme explícita. El calendario hábil determina recepción; se sigue consumiendo durante fines de semana intermedios. No se completan días de pronóstico ausentes ni se extrapola un horizonte corto.

Faltante = max(0, demanda durante entrega − stock disponible). ALERTA solo si demanda > stock; igualdad produce SIN_ALERTA. Entradas y resultados Decimal; las divisiones temporales se comparan como fracciones exactas para evitar microfaltantes. Sin redondear predicciones antes de comparar. Prioridad: faltante descendente, con desempate estable por código/proveedor.

Interpretación de días HU-31: HU-31 indica días pero no confirma naturales o hábiles; no se asume un calendario operativo.

## Fuentes por repuesto

| Código | Fecha de previsión | Horizonte | Naturaleza demanda | Fecha cotización | Vigencia | Naturaleza plazo |
|---|---|---|---|---|---|---|
| REP-0001 |  |  a  |  | 2026-09-26 | 2026-10-26 | SINTETICO |
| REP-0002 |  |  a  |  | 2026-09-23 | 2026-11-07 | SINTETICO |
| REP-0003 |  |  a  |  | 2026-09-17 | 2026-10-02 | SINTETICO |
| REP-0004 |  |  a  |  | 2026-09-18 | 2026-11-02 | SINTETICO |
| REP-0005 |  |  a  |  | 2026-09-04 | 2026-10-04 | SINTETICO |
| REP-0006 |  |  a  |  | 2026-09-16 | 2026-10-31 | SINTETICO |
| REP-0007 |  |  a  |  | 2026-09-26 | 2026-10-26 | SINTETICO |
| REP-0008 |  |  a  |  | 2026-09-20 | 2026-10-20 | SINTETICO |
| REP-0009 |  |  a  |  | 2026-09-26 | 2026-11-10 | SINTETICO |
| REP-0010 |  |  a  |  | 2026-09-24 | 2026-10-24 | SINTETICO |

## Supuestos y limitaciones

- Las fuentes de inventario y cotizaciones son ficticias/sintéticas del repositorio; esta integración no contiene datos operativos reales.
- El corte de stock es explícito y tiene 41 días de antigüedad respecto a la evaluación; el límite configurable de 30 días es una política de esta ejecución, no una prueba de actualidad.
- La selección de proveedor es explícita. No se sustituye una cotización vencida por otra ni se interpreta crédito o vigencia como plazo de entrega.
- El CSV de demanda contiene solo el contrato de columnas porque no existe previsión futura validada exportada en el repositorio.
- No se propaga el stock desde septiembre suponiendo ausencia de movimientos. Pendientes y discrepancias físicas impiden verificar disponibilidad según la política seleccionada.
- HU-07 exporta MAE de evaluación, no demanda futura. No se usa MAE ni se modifica HU-07. El contrato admite previsiones futuras validadas; aquí no se generan automáticamente.
- RPxxx de HU-34 permanece separado de REP-xxxx: no hay equivalencia documentada. Ventas observadas no prueban demanda no satisfecha.
- HU-31 contiene plazos sintéticos; no se deduce plazo de vigencia, precio o condiciones de pago. No se elige otro proveedor si la cotización seleccionada vence.
- Estas alertas son deterministas y no estiman una probabilidad de agotamiento. Las pruebas sintéticas demuestran el motor, no validan previsiones empresariales.

## Archivos y trazabilidad

Salidas: dataset_consolidado.csv y alertas_faltantes.csv en la carpeta de datos de este modo; este informe y prioridades.svg en su carpeta de informes. La demostración usa subcarpetas demostracion independientes.

- ajustes: `data/processed/hu-18/ajustes_inventario.csv`; SHA-256 `dddea02e131f0ddcfd37ab3861996a2d92c27494ce5cce29d7fbc9ed81762e7f`.
- conciliacion: `data/processed/hu-18/conciliacion_inventario.csv`; SHA-256 `037e34b2188c2acfe38a48e58a24a4b58aaf12e8a47da6b01b7b6c7f60c9b7ac`.
- configuracion: `data/raw/hu-09/configuracion.json`; SHA-256 `163a2ea4e8bd5eaab725f11a6dccd31cebd54325c8d35dd04509dae35df7c7f6`.
- cotizaciones: `data/processed/hu-30-31/sintetico/hu31_cotizaciones_proveedor_sintetico.csv`; SHA-256 `5f986985645b7049c75025d1485cf97497754c916e358b3d9842095a0b73be71`.
- demanda: `data/raw/hu-09/demanda_prevista.csv`; SHA-256 `a5304a028fb8dff3b951a334576bb017deb7628dedeadb5334330d12e1d97918`.
- depuracion: `data/processed/hu-17/reporte_depuracion_final.csv`; SHA-256 `5aa3b2db7bfbcc6c88109c5bb7b3f41727ae0430554258774695c5780a048a96`.
- historial: `data/processed/hu-18/historial_ajustes.csv`; SHA-256 `cf15779fe7b9f651550e00eb1bad12bbe54ee3de1da4500f8b544d0011dc204a`.
- stock_inicial: `data/raw/hu-18/stock_inicial.csv`; SHA-256 `5fe1f6cb16f4970191ec338c3a105e8ca77643aa2b42bed52a3e110608aa5183`.

Procedencias de previsión: sin previsiones futuras suministradas.
