# HU-09: verificación de datos de inventario y plazo

Generado por `src/hu-09/verificar_datos.py` (Sabrina Adrian Zelaya). Fecha de evaluación 2026-11-10, corte de stock 2026-09-30.

## Resultado

Repuestos verificados: **0 de 10**. Un repuesto queda verificado solo si su stock disponible y su plazo vigente se pudieron reconstruir sin ningún motivo en contra.

| Motivo | Repuestos |
|---|---|
| COTIZACION_VENCIDA | 9 |
| DIFERENCIA_CONTEO_PENDIENTE | 2 |
| MOVIMIENTOS_PENDIENTES_REVISION | 5 |
| RESERVAS_Y_BLOQUEOS_DESCONOCIDOS | 10 |

## Detalle

| Repuesto | Registrado | Conteo físico | Ajustado | Disponible | Plazo | Motivos |
|---|---|---|---|---|---|---|
| REP-0001 | 95 | 95 | 95 |  |  | COTIZACION_VENCIDA, MOVIMIENTOS_PENDIENTES_REVISION, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0002 | 55 | 53 | 53 |  |  | COTIZACION_VENCIDA, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0003 | 31 | 31 | 31 |  |  | COTIZACION_VENCIDA, MOVIMIENTOS_PENDIENTES_REVISION, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0004 | 28 | 18 | 18 |  |  | COTIZACION_VENCIDA, MOVIMIENTOS_PENDIENTES_REVISION, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0005 | 17 | 18 | 17 |  |  | COTIZACION_VENCIDA, DIFERENCIA_CONTEO_PENDIENTE, MOVIMIENTOS_PENDIENTES_REVISION, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0006 | 130 | 130 | 130 |  |  | COTIZACION_VENCIDA, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0007 | 9 | 8 | 9 |  |  | COTIZACION_VENCIDA, DIFERENCIA_CONTEO_PENDIENTE, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0008 | 45 | 45 | 45 |  |  | COTIZACION_VENCIDA, MOVIMIENTOS_PENDIENTES_REVISION, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0009 | 45 | 45 | 45 |  | 30 | RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |
| REP-0010 | 7 | 7 | 7 |  |  | COTIZACION_VENCIDA, RESERVAS_Y_BLOQUEOS_DESCONOCIDOS |

## Supuestos

- Las fuentes de inventario y cotizaciones son ficticias/sintéticas del repositorio; esta integración no contiene datos operativos reales.
- El corte de stock es explícito y tiene 41 días de antigüedad respecto a la evaluación; el límite configurable de 30 días es una política de esta ejecución, no una prueba de actualidad.
- La selección de proveedor es explícita. No se sustituye una cotización vencida por otra ni se interpreta crédito o vigencia como plazo de entrega.
- El CSV de demanda contiene solo el contrato de columnas porque no existe previsión futura validada exportada en el repositorio.
- No se propaga el stock desde septiembre suponiendo ausencia de movimientos. Pendientes y discrepancias físicas impiden verificar disponibilidad según la política seleccionada.

## Huellas de las entradas

| Entrada | Archivo | SHA-256 |
|---|---|---|
| ajustes | `data/processed/hu-18/ajustes_inventario.csv` | `01df4a1190f0a38b52e406aeb66a6b3ca1f5e416572ca3f28cff240fd4f4f853` |
| conciliacion | `data/processed/hu-18/conciliacion_inventario.csv` | `71376a13ba3bf5a07f5dd5cabc04eb26c712646194173e52c06e134db5b1dd7c` |
| configuracion | `data/raw/hu-09/configuracion.json` | `163a2ea4e8bd5eaab725f11a6dccd31cebd54325c8d35dd04509dae35df7c7f6` |
| cotizaciones | `data/processed/hu-30-31/sintetico/hu31_cotizaciones_proveedor_sintetico.csv` | `5f986985645b7049c75025d1485cf97497754c916e358b3d9842095a0b73be71` |
| demanda | `data/raw/hu-09/demanda_prevista.csv` | `a5304a028fb8dff3b951a334576bb017deb7628dedeadb5334330d12e1d97918` |
| depuracion | `data/processed/hu-17/reporte_depuracion_final.csv` | `2c1e0df2ce0ff6a7d93958390412e46d9ffac799fe2b2a7d7c16defa25ad3ef1` |
| historial | `data/processed/hu-18/historial_ajustes.csv` | `352fda01aaa5bc64cc6b3909db590c2447a73eef8e4652e650d4f5f80f1321e2` |
| stock_inicial | `data/raw/hu-18/stock_inicial.csv` | `ea12d0f051b2c6213af52ad32bf566f08836fa15e76ee02254117b4d07c21717` |

Las fuentes de HU-17, HU-18 y HU-31 son FICTICIAS o SINTÉTICAS. Las alertas de reposición no usan esta verificación: salen de la lógica única del simulador (ver `docs/hu-09/LEEME.md`).
