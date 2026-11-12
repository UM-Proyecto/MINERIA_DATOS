# Auditoría final de HU-09 — Alertas de riesgo de faltantes

> **Nota del 12-11-2026.** Este informe registra la entrega del 10-11-2026 tal como se hizo. Desde el 12-11-2026 las
> alertas de faltantes usan la lógica única del simulador (`src/hu-09/generar_alertas.py`), con los criterios de esta
> entrega; la conciliación de inventario y plazo sigue viva como verificación de datos (`src/hu-09/verificar_datos.py`),
> y el modo de demostración se retiró. Qué cambió y por qué: `docs/hu-09/LEEME.md`.

Fecha: 10/11/2026. Proyecto: MULTIPARTES / MINERIA_DATOS.
Rama revisada: `feature/hu-09-alertas-faltantes`.
Entorno: Windows, Python 3.13.7, biblioteca estándar.

## Dictamen

**Lista para entrega técnica y revisión en GitHub**, con los tres criterios
originales de aceptación demostrados. Se ejecutaron nuevamente las 41 pruebas
de HU-09 y la suite completa de 51 pruebas: todas aprobadas, sin errores,
fallos ni omisiones. No se encontraron defectos bloqueantes en el alcance
auditado. Esta conclusión no certifica disponibilidad ni pronósticos reales
de MULTIPARTES: faltan datos operativos y la integración devuelve correctamente
10 observaciones NO_CALCULABLE.

Las cuatro alertas de la demostración son sintéticas, están separadas de la
integración y coinciden con el recálculo independiente. Durante esta auditoría
solo se creó este informe; no se modificaron el motor, pruebas, configuración
ni resultados. No se hizo staging, commit ni push.

## Alcance y método

Se revisaron el motor, las configuraciones, las fuentes utilizadas, las pruebas,
los cuatro CSV, los dos SVG, los informes y la documentación. Se contrastaron
los resultados con lecturas independientes de CSV/JSON y aritmética Decimal,
sin invocar las funciones de HU-09 para el recálculo de existencias y demanda.

Se regeneraron ambos modos dos veces en directorios temporales externos al
repositorio, usando la CLI desde otra carpeta. Los ocho artefactos generados
(dos CSV, informe y SVG por modo) coinciden byte a byte con los entregados.
No fue necesario sobrescribirlos para auditarlos.

## Tres criterios originales de aceptación

| Criterio | Evidencia ejecutada | Resultado |
|---|---|---|
| La alerta identifica stock disponible, demanda prevista y plazo utilizado | `test_stock_suficiente_identifica_los_tres_datos`: stock 100, demanda 4 unidades/día, plazo 10 días; demanda durante entrega 40. Los CSV conservan esos campos, unidad, fecha, proveedor y procedencia. Las cuatro alertas sintéticas también identifican sus tres entradas. | CUMPLE |
| Genera alerta cuando demanda durante entrega supera estrictamente el stock | `test_demanda_superior_al_stock`: 4 × 10 = 40 frente a stock 20; ALERTA, faltante 20. `test_igualdad_no_genera_alerta`: 40 frente a 40; SIN_ALERTA. La prueba de igualdad semanal/mensual evita microfaltantes por divisiones periódicas. | CUMPLE |
| Si falta demanda o plazo, informa que no puede calcular | `test_demanda_faltante_no_es_cero`, `test_plazo_faltante` y `test_ambos_faltantes_informa_ambos`: NO_CALCULABLE, motivos explícitos y resultados calculados vacíos. Los diez registros de integración mantienen esa condición. | CUMPLE |

Las condiciones adicionales de calidad (stock verificable, horizonte suficiente,
vigencia y calendario) también pueden impedir el cálculo; nunca convierten una
observación incompleta en SIN_ALERTA.

## Pruebas ejecutadas nuevamente

Desde la raíz de MINERIA_DATOS:

```bash
python -m unittest discover -s tests -p "test_generar_alertas.py" -v
python -m unittest discover -s tests -p "test_*.py" -v
```

| Ejecución | Aprobadas | Fallos | Errores | Omitidas | Salida |
|---|---:|---:|---:|---:|---:|
| HU-09 | 41 | 0 | 0 | 0 | 0 |
| Suite completa | 51 | 0 | 0 | 0 | 0 |

La suite completa incluye las 41 anteriores y 10 pruebas preexistentes:
8 de HU-02 y 2 de HU-07. No deben sumarse las dos ejecuciones como 92 pruebas
distintas. Evidencia individual de las 41 pruebas, todas con resultado **OK**,
en [test_generar_alertas.py](../../tests/test_generar_alertas.py):

| Clase | Prueba | Resultado |
|---|---|---|
| MotorTest | test_stock_suficiente_identifica_los_tres_datos | OK |
| MotorTest | test_demanda_superior_al_stock | OK |
| MotorTest | test_igualdad_no_genera_alerta | OK |
| MotorTest | test_demanda_faltante_no_es_cero | OK |
| MotorTest | test_plazo_faltante | OK |
| MotorTest | test_ambos_faltantes_informa_ambos | OK |
| MotorTest | test_stock_desconocido_o_no_verificable | OK |
| MotorTest | test_demanda_cero_valida_y_stock_cero | OK |
| MotorTest | test_plazo_cero_explicito_conserva_regla_de_datos_faltantes | OK |
| MotorTest | test_rechaza_negativos_y_no_finitos | OK |
| MotorTest | test_decimal_no_redondea_antes_de_comparar | OK |
| MotorTest | test_horizonte_insuficiente | OK |
| MotorTest | test_serie_diaria_suma_solo_ventana | OK |
| MotorTest | test_serie_con_dia_faltante_o_vacio_no_se_completa | OK |
| MotorTest | test_codigos_y_proveedores_no_se_asocian_por_parecido | OK |
| MotorTest | test_pronostico_no_validado_o_posterior_a_evaluacion | OK |
| MotorTest | test_stock_antiguo_futuro_y_sin_fecha | OK |
| MotorTest | test_dias_habiles_incluyen_consumo_de_fin_de_semana_y_feriados | OK |
| MotorTest | test_calendario_faltante_no_se_inventa | OK |
| MotorTest | test_conversion_semanal_exige_distribucion_explicita | OK |
| MotorTest | test_conversion_mensual_usa_dias_reales_en_cambio_de_mes | OK |
| MotorTest | test_igualdad_semanal_y_mensual_sin_microfaltantes_por_division | OK |
| MotorTest | test_prioridades_descendentes_y_no_calculables_visibles | OK |
| IntegracionTest | test_demo_reproduce_resultados_de_las_fuentes | OK |
| IntegracionTest | test_deduplicacion_preserva_lineas_legitimas | OK |
| IntegracionTest | test_ajustes_aplicados_se_cuentan_una_vez | OK |
| IntegracionTest | test_rechazos_repetidos_y_discrepancias_no_cambian_stock | OK |
| IntegracionTest | test_ajustes_duplicados_o_sin_respaldo_se_rechazan | OK |
| IntegracionTest | test_ajustes_futuros_no_se_usan_retrospectivamente | OK |
| IntegracionTest | test_reservas_desconocidas_y_pendientes_no_se_ignoran | OK |
| IntegracionTest | test_reservas_confirmadas_se_restan_sin_inventarlas | OK |
| IntegracionTest | test_plazo_de_hu31_no_es_condicion_de_pago_y_vence | OK |
| IntegracionTest | test_alias_hu17_y_rechazo_de_rp_sin_equivalencia | OK |
| IntegracionTest | test_pronosticos_duplicados_y_negativos_se_rechazan | OK |
| IntegracionTest | test_csv_de_mae_no_cumple_contrato_de_demanda | OK |
| IntegracionTest | test_cabecera_sola_y_demanda_vacia_no_son_cero | OK |
| IntegracionTest | test_regeneracion_identica_conserva_entradas_y_svg | OK |
| IntegracionTest | test_error_no_sobrescribe_salida_y_modos_separados | OK |
| IntegracionTest | test_integracion_no_admite_reservas_cero_sin_confirmacion | OK |
| RepositorioTest | test_integracion_actual_no_inventa_datos_y_preserva_otras_hu | OK |
| RepositorioTest | test_cli_desde_otro_directorio_y_error_controlado | OK |

## Recálculo independiente de las cuatro alertas sintéticas

Evaluación: 20/10/2026. Corte histórico de stock: 30/09/2026.
Se reconstruyó el stock desde la apertura HU-18, los movimientos no duplicados
HU-17 y los dos ajustes aplicados respaldados por HU-18. Se seleccionó la
cotización exacta configurada y vigente. Se leyó la previsión sintética, sin
utilizar el resultado calculado como entrada.

Demanda durante entrega = suma del consumo en (evaluación, recepción].
Faltante = máximo(0, demanda durante entrega − stock disponible hipotético).

| Prioridad | Repuesto | Proveedor | Stock | Demanda independiente | Plazo natural | Recepción | Faltante | Estado |
|---:|---|---|---:|---|---:|---|---:|---|
| 1 | REP-0002 | Importadora Toyota | 53 | 2/día × 45 = 90 | 45 días | 2026-12-04 | 37 | ALERTA |
| 2 | REP-0001 | Bosch Bolivia | 95 | 40/día × 3 = 120 | 3 días | 2026-10-23 | 25 | ALERTA |
| 3 | REP-0008 | Importadora Toyota | 45 | 4/día × 15 = 60 | 15 días | 2026-11-04 | 15 | ALERTA |
| 4 | REP-0009 | Suspensiones SRL | 45 | 30 fechas con demanda 2 = 60 | 30 días | 2026-11-19 | 15 | ALERTA |

Coinciden código, stock, demanda, plazo, faltante y prioridad con ambos CSV y
con el gráfico. La serie REP-0009 comprende del 21/10 al 19/11, ambos inclusive.
La cotización REP-0008 vence el mismo día de evaluación y es válida inclusive.

También se verificaron los demás estados: REP-0004 tiene demanda 18 y stock 18
(igualdad, SIN_ALERTA); REP-0006 tiene demanda explícita 0 y stock 130;
REP-0010 tiene tasa 7/semana, reparto uniforme y tres días de consumo: 3 frente
a stock 7. Los tres son SIN_ALERTA. REP-0003 y REP-0005 carecen de demanda y
cotización vigente; REP-0005 además tiene discrepancia física. REP-0007 conserva
una discrepancia física aunque tenga demanda y plazo: NO_CALCULABLE.

## Verificación de las diez observaciones de integración

Evaluación: 10/11/2026. Stock al 30/09/2026: antigüedad 41 días, superior al
máximo configurado de 30. El archivo de demanda principal contiene solo la
cabecera: **cero previsiones**. Las reservas y bloqueos son desconocidos.

Se contrastó independientemente el conjunto exacto de motivos por cada código.
Las diez filas son NO_CALCULABLE, con stock disponible, demanda durante entrega
y faltante vacíos. Ninguna se presenta como ausencia de riesgo.

| Motivo | Cantidad | Códigos afectados |
|---|---:|---|
| DEMANDA_FALTANTE | 10 | Todos |
| RESERVAS_Y_BLOQUEOS_DESCONOCIDOS | 10 | Todos |
| STOCK_DISPONIBLE_NO_VERIFICABLE | 10 | Todos |
| STOCK_DESACTUALIZADO | 10 | Todos |
| COTIZACION_VENCIDA | 9 | Todos excepto REP-0009 |
| PLAZO_FALTANTE | 9 | Todos excepto REP-0009; no se usa una cotización vencida |
| MOVIMIENTOS_PENDIENTES_REVISION | 5 | REP-0001, REP-0003, REP-0004, REP-0005, REP-0008 |
| DIFERENCIA_CONTEO_PENDIENTE | 2 | REP-0005, REP-0007 |
| CALENDARIO_PLAZO_NO_DEFINIDO | 1 | REP-0009 |

Los motivos coexisten; sus cantidades no son repuestos adicionales. REP-0009
conserva plazo 30 de una cotización vigente hasta el 10/11 inclusive, pero no
se sabe si son días naturales o hábiles. No se inventa un calendario para
calcular recepción. Las nueve cotizaciones vencidas no se reemplazan
silenciosamente por otras referencias o proveedores.

## Integridad de stock, movimientos y catálogos

- HU-17 contiene 24 movimientos: 10 ORIGINALES, 7 PENDIENTE_REVISION y 7
  DUPLICADO. Se excluyeron los IDs 1004, 1006, 1009, 1016, 1018, 1022 y 1024;
  se conservaron los otros 17 para reproducir el registrado de HU-18. No se
  elimina una orden completa por contener un duplicado. La prueba de líneas
  legítimas agrega otra línea válida de OC-5008 y confirma stock 133.
- Solo se aplican dos ajustes únicos y respaldados por AJUSTE_APLICADO:
  REP-0002, 55 − 2 = 53, y REP-0004, 28 − 10 = 18, registrados el 02/10.
  No se vuelven a descontar sobre el conteo físico ni al ejecutar otra vez.
  Los ajustes ya incorporados en cortes posteriores tampoco se duplican.
- Los cuatro eventos repetidos de rechazo para REP-0007 no cambian su saldo 9.
  Los ajustes duplicados, sin respaldo o posteriores a la evaluación se
  rechazan. REP-0005 permanece con ajustado 17 frente a físico 18 y REP-0007
  con ajustado 9 frente a físico 8: no se inventa disponibilidad conciliada.
- En integración no se imputan reservas/bloqueos cero. Una confirmación exige
  cantidades, fecha del corte, fuente y naturaleza. La hipótesis de stock libre
  se admite únicamente en la demostración y está declarada en su JSON.
- Se usa el campo específico `plazo_entrega_dias` de HU-31. No se interpreta
  precio, vigencia ni condición de pago como plazo de entrega.
- Los códigos REP-xxxx se normalizan con los alias de HU-17. RPxxx de HU-34
  se rechaza sin equivalencia documentada. No hay cruces por posición, nombre
  parecido o sufijo numérico; las pruebas de incompatibilidad y alias pasaron.
- No se convierten MAE de HU-07 ni movimientos históricos de HU-30 en previsión
  futura. El CSV de MAE se rechaza como entrada de demanda. No se fabrica un
  pronóstico para obtener alertas en la integración.

## Separación, trazabilidad y coherencia de entregables

| Modo | Resultado | Identificación y ubicación |
|---|---|---|
| INTEGRACION | 0 ALERTA, 0 SIN_ALERTA, 10 NO_CALCULABLE | CSV en `data/processed/hu-09/`; informe y SVG en `reports/hu-09/` |
| DEMOSTRACION_SINTETICA | 4 ALERTA, 3 SIN_ALERTA, 3 NO_CALCULABLE | Configuración, previsiones, CSV, informe y SVG en sus subcarpetas `demostracion/` |

Las 37 filas de previsión de la demostración están marcadas SINTETICO. El stock
reutilizado está identificado FICTICIO y las cotizaciones SINTETICO. Se conservan
fuente, fecha, corte, unidad, proveedor y naturaleza en los campos correspondientes;
los informes incluyen SHA-256 de entradas y configuración. El modo aparece en
filas, informe y gráfico. La demostración declara stock libre hipotético,
calendario natural y admisión de un corte histórico de 20 días; `validado=true`
significa revisión del ejemplo, no validación estadística de un modelo.

Se comprobó que cada CSV tiene diez códigos sin repetir y que los estados de
ambos CSV coinciden. Los SVG son XML válido: cero barras en integración y cuatro
en demostración, con los faltantes y estados correctos. El gráfico sin alertas
advierte que ello no demuestra ausencia de riesgo. La documentación y el README
coinciden con las configuraciones, comandos y conteos. No se detectaron enlaces
locales rotos en README ni en los documentos HU-09 revisados.

Las ocho salidas coinciden byte a byte tras dos regeneraciones por modo. La
validación del modo impide que una ejecución sobrescriba el otro modo o escriba
resultados en otra historia dentro del repositorio. Las pruebas de separación
y conservación de salidas ante error también pasaron.

## Git y archivos afectados

Se ejecutaron `git status --short`, `git diff -- README.md`,
`git diff --check`, `git diff --cached --exit-code` y
`git diff --exit-code -- data docs src reports notebooks tests .gitignore`.
La revisión de diferencias no encontró cambios rastreados fuera del README,
ni cambios en el área de staging. `git diff --check` terminó con código 0.
Se revisaron además los archivos nuevos, que Git todavía no incluye en el diff:
sin espacios o tabulaciones sobrantes al final de línea.

Se compararon los SHA-256 actuales con la instantánea de los 84 archivos
preexistentes tomada antes de implementar HU-09: **83 siguen idénticos** y el
único cambiado es `README.md`, por la incorporación de HU-09, sus comandos y
enlaces (25 inserciones, 1 eliminación). No se alteró código, fuentes ni
resultados de otra historia. Contra la instantánea final de implementación,
los 99 archivos allí registrados también siguen idénticos; el informe de
validación y esta auditoría fueron incorporados después.

Estado de trabajo de la entrega, incluyendo este informe:

- Modificado: `README.md`.
- Nuevos, sin seguimiento: 17 archivos HU-09, enumerados a continuación.
- Staging vacío; no se realizaron staging, commit ni push.

| Grupo | Archivos nuevos |
|---|---|
| Motor | `src/hu-09/generar_alertas.py` |
| Integración: entradas | `data/raw/hu-09/configuracion.json`, `data/raw/hu-09/demanda_prevista.csv` |
| Demostración: entradas | `data/raw/hu-09/demostracion/configuracion.json`, `data/raw/hu-09/demostracion/demanda_prevista.csv` |
| Integración: resultados | `data/processed/hu-09/dataset_consolidado.csv`, `data/processed/hu-09/alertas_faltantes.csv` |
| Demostración: resultados | `data/processed/hu-09/demostracion/dataset_consolidado.csv`, `data/processed/hu-09/demostracion/alertas_faltantes.csv` |
| Documentación | `docs/hu-09/LEEME.md` |
| Integración: informe y gráfico | `reports/hu-09/REPORTE_HU09.md`, `reports/hu-09/prioridades.svg` |
| Demostración: informe y gráfico | `reports/hu-09/demostracion/REPORTE_HU09.md`, `reports/hu-09/demostracion/prioridades.svg` |
| Pruebas | `tests/test_generar_alertas.py` |
| Evidencia de entrega | `reports/hu-09/VALIDACION_HU09.md`, `reports/hu-09/AUDITORIA_FINAL_HU09.md` |

## Limitaciones y pendientes

1. Antes de usar alertas para compras reales se necesitan previsiones futuras
   validadas, stock reciente con reservas/bloqueos confirmados, revisión de
   movimientos/discrepancias, cotizaciones vigentes y calendario del plazo.
   Las fuentes disponibles son ficticias/sintéticas; no prueban riesgo real.
2. No hay equivalencia REP↔RP documentada ni un artefacto local de HU-36 con
   previsiones adicionales. La integración no fabrica esas relaciones.
3. La alerta se entrega en CSV, informe y SVG; no hay notificaciones por correo
   ni integración con un sistema de compras. El ejemplo sintético verifica la
   regla de riesgo, sin validar capacidad predictiva empresarial.
4. La publicación es atómica por archivo, sin transacción conjunta para las
   cuatro salidas. Una interrupción durante publicación exige regenerar el modo.
5. La compatibilidad declarada es Python 3.8+; esta auditoría ejecutó Python
   3.13.7 en Windows, sin probar otras versiones o plataformas.

Los pendientes anteriores limitan el uso operativo; no contradicen los tres
criterios de aceptación ni bloquean la entrega técnica revisada. La subida a
GitHub queda pendiente de revisión del usuario.

Referencias locales: [guía](../../docs/hu-09/LEEME.md),
[integración](REPORTE_HU09.md), [demostración](demostracion/REPORTE_HU09.md)
y [validación de implementación](VALIDACION_HU09.md).
