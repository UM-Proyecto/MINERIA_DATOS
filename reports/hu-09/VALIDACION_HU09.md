# Validación de entrega HU-09

> **Nota del 12-11-2026.** Este informe registra la entrega del 10-11-2026 tal como se hizo. Desde el 12-11-2026 las
> alertas de faltantes usan la lógica única del simulador (`src/hu-09/generar_alertas.py`), con los criterios de esta
> entrega; la conciliación de inventario y plazo sigue viva como verificación de datos (`src/hu-09/verificar_datos.py`),
> y el modo de demostración se retiró. Qué cambió y por qué: `docs/hu-09/LEEME.md`.

Fecha: 10/11/2026. Rama: `feature/hu-09-alertas-faltantes`.
Entorno ejecutado: Python 3.13.7 en Windows. Sin dependencias nuevas.

## Resultado

Se implementó y ejecutó HU-09 con dos modos separados. Los tres criterios
originales están demostrados mediante pruebas concretas. La suite completa
terminó con **51 pruebas aprobadas, 0 fallos, 0 errores y 0 omitidas**:
41 pruebas HU-09 y las 10 preexistentes de HU-02/HU-07.

No se realizó commit, push ni staging. Los resultados se entregan para revisión.

| Modo | Evaluación | Corte stock | ALERTA | SIN_ALERTA | NO_CALCULABLE |
|---|---|---|---:|---:|---:|
| INTEGRACION | 2026-11-10 | 2026-09-30 | 0 | 0 | 10 |
| DEMOSTRACION_SINTETICA | 2026-10-20 | 2026-09-30 | 4 | 3 | 3 |

La integración incompleta no es información operativa real: sus fuentes de
inventario y cotizaciones también son ficticias/sintéticas. La demostración
añade previsiones artificiales para comprobar la lógica; no demuestra un
pronóstico empresarial validado.

## Ejecuciones reproducibles

Desde la raíz del repositorio se ejecutaron, con código de salida 0:

```bash
python src/hu-09/generar_alertas.py
python src/hu-09/generar_alertas.py --config data/raw/hu-09/demostracion/configuracion.json
python -m unittest discover -s tests -p "test_*.py" -v
```

La ejecución específica inicial pasó 40 pruebas de HU-09. Durante la revisión
se añadió una prueba de igualdad después de conversiones semanales/mensuales;
la ejecución final completa incluye sus 41 pruebas. Se corrigió la acumulación
de divisiones periódicas para no emitir microfaltantes espurios: se reciben y
exportan Decimal y se compara el reparto temporal racional exacto mediante
Fraction de la biblioteca estándar.

## Evidencia de los tres criterios originales

| Criterio | Prueba y evidencia |
|---|---|
| La alerta identifica stock, demanda prevista y plazo utilizado | `test_stock_suficiente_identifica_los_tres_datos`: stock 100, demanda 4 unidades/día, plazo 10; demanda durante entrega 40. Los CSV incorporan esos campos, proveedor, corte, fuentes y fechas. |
| Alerta solo cuando demanda durante entrega supera stock | `test_demanda_superior_al_stock`: 4 × 10 = 40 frente a stock 20, ALERTA y faltante 20. `test_igualdad_no_genera_alerta`: 40 frente a 40, SIN_ALERTA. |
| Falta demanda o plazo: informar imposibilidad | `test_demanda_faltante_no_es_cero`, `test_plazo_faltante` y `test_ambos_faltantes_informa_ambos`: NO_CALCULABLE con todos los motivos aplicables y cálculos vacíos. |

## Cobertura de los 17 casos solicitados

Pruebas en [`tests/test_generar_alertas.py`](../../tests/test_generar_alertas.py).
Todos los casos de esta tabla pasaron en la suite final.

| Caso | Evidencia |
|---|---|
| 1. Stock suficiente | `test_stock_suficiente_identifica_los_tres_datos`: 100 frente a 40, SIN_ALERTA. |
| 2. Demanda superior | `test_demanda_superior_al_stock`: faltante 20 y ALERTA. |
| 3. Igualdad | `test_igualdad_no_genera_alerta`; también `test_igualdad_semanal_y_mensual_sin_microfaltantes_por_division`: nunca ALERTA por redondeo. |
| 4. Demanda faltante | `test_demanda_faltante_no_es_cero`: tanto previsión ausente como tasa vacía. |
| 5. Plazo faltante | `test_plazo_faltante`: motivo PLAZO_FALTANTE. |
| 6. Ambos faltantes | `test_ambos_faltantes_informa_ambos`: dos motivos, también con serie diaria vacía. |
| 7. Demanda cero | `test_demanda_cero_valida_y_stock_cero`: cero explícito es calculable. REP-0006 demuestra ese caso en el CSV. |
| 8. Stock cero | Misma prueba: demanda positiva con stock cero produce faltante; ambos cero producen SIN_ALERTA. |
| 9. Negativos | `test_rechaza_negativos_y_no_finitos`: stock, demanda y plazo negativos, NaN, infinito, booleanos y float se rechazan; plazo fraccionario también. |
| 10. Horizonte insuficiente | `test_horizonte_insuficiente` y `test_serie_con_dia_faltante_o_vacio_no_se_completa`: no se extrapola ni se completan días con cero. |
| 11. Códigos incompatibles | `test_codigos_y_proveedores_no_se_asocian_por_parecido` y `test_alias_hu17_y_rechazo_de_rp_sin_equivalencia`: alias reconocido sí; RP y código desconocido no. |
| 12. Duplicados | `test_deduplicacion_preserva_lineas_legitimas`: excluye 1016, conserva otra línea legítima de OC-5008 y obtiene 133 unidades. También se rechazan previsiones y ajustes duplicados. |
| 13. Ajustes ya aplicados | `test_ajustes_aplicados_se_cuentan_una_vez`: REP-0002 55→53 y REP-0004 28→18 en dos cargas consecutivas. Rechazos repetidos no restan stock; ajustes futuros se bloquean. |
| 14. Naturales y hábiles | `test_dias_habiles_incluyen_consumo_de_fin_de_semana_y_feriados`: viernes con plazo hábil 1 recibe lunes, consumiendo tres días; si lunes es feriado, cuatro; plazo natural 1 consume un día. |
| 15. Unidades temporales | `test_conversion_semanal_exige_distribucion_explicita` y `test_conversion_mensual_usa_dias_reales_en_cambio_de_mes`: 70/semana × 3/7 = 30; 930/mes en 31/10 y 01/11 suma 30+31=61. |
| 16. Reproducibilidad | `test_regeneracion_identica_conserva_entradas_y_svg`: cuatro artefactos idénticos byte a byte tras dos ejecuciones y XML SVG válido. Se comprobó además contra los archivos entregados de ambos modos. |
| 17. Originales conservados | `test_integracion_actual_no_inventa_datos_y_preserva_otras_hu` y comparación SHA-256 de los 84 archivos iniciales: solo README cambió; los otros 83 siguen idénticos. |

Las restantes pruebas cubren stock no verificable/antiguo/futuro, calendario
ausente, previsiones posteriores o no validadas, uso exclusivo del plazo de
entrega, vencimiento, política de reservas, prioridades, CSV de MAE incompatible,
separación de modos, conservación de salidas ante error y CLI desde otra carpeta.

## Comprobación de archivos generados

En cada modo se verificaron diez filas en `dataset_consolidado.csv` y diez en
`alertas_faltantes.csv`, con códigos y estados coincidentes. Para cada resultado
calculable se comprobó independientemente:

- Faltante = máximo entre cero y demanda durante entrega menos stock.
- ALERTA si y solo si demanda > stock.
- NO_CALCULABLE mantiene vacíos demanda durante entrega y faltante, con motivos.
- Prioridades descendentes por faltante, desempate estable por código/proveedor.

Los dos CSV, el informe y el SVG de cada modo se regeneraron dos veces en
directorios temporales: los ocho artefactos coinciden byte a byte con los
entregados. Se analizaron ambos SVG como XML y se verificaron sus cantidades de
barras: cero en integración y cuatro en demostración.

## Resultados de la demostración y cálculo independiente

| Prioridad | Repuesto | Stock disponible hipotético | Demanda durante entrega | Plazo natural | Faltante |
|---:|---|---:|---:|---:|---:|
| 1 | REP-0002 | 53 | 2 × 45 = 90 | 45 | 37 |
| 2 | REP-0001 | 95 | 40 × 3 = 120 | 3 | 25 |
| 3 | REP-0008 | 45 | 4 × 15 = 60 | 15 | 15 |
| 4 | REP-0009 | 45 | 30 valores diarios de 2 = 60 | 30 | 15 |

SIN_ALERTA:

- REP-0004: stock 18; 6 × 3 = 18; faltante 0 por igualdad exacta.
- REP-0006: stock 130; demanda explícita 0; faltante 0.
- REP-0010: stock 7; tasa 7/semana con reparto uniforme; 3 días → demanda 3.

NO_CALCULABLE:

- REP-0003: sin demanda y cotización seleccionada vencida.
- REP-0005: sin demanda, cotización vencida y diferencia física pendiente.
- REP-0007: tiene demanda y plazo, pero el registrado 9 no concuerda con conteo 8.

La demostración utiliza reservas y bloqueos cero como supuesto explícito, días
naturales declarados y un corte histórico admitido con 20 días de antigüedad.
No presenta ese stock como existencias confirmadas de MULTIPARTES al 20/10/2026.

## Motivos en la integración actual

Los motivos pueden coexistir: sus cantidades no se suman como repuestos distintos.

| Motivo | Repuestos |
|---|---:|
| DEMANDA_FALTANTE | 10 |
| RESERVAS_Y_BLOQUEOS_DESCONOCIDOS | 10 |
| STOCK_DISPONIBLE_NO_VERIFICABLE | 10 |
| STOCK_DESACTUALIZADO | 10 |
| COTIZACION_VENCIDA | 9 |
| PLAZO_FALTANTE | 9 |
| MOVIMIENTOS_PENDIENTES_REVISION | 5 |
| DIFERENCIA_CONTEO_PENDIENTE | 2 |
| CALENDARIO_PLAZO_NO_DEFINIDO | 1 |

La cotización seleccionada de REP-0009 conserva plazo 30 y vigencia hasta el
10/11/2026 inclusive. Aun así faltan previsión, disponibilidad y definición de
días. No se clasifica como SIN_ALERTA. Las otras nueve referencias no se
sustituyen por proveedores alternativos al vencer.

## Archivos creados y modificados

Se crearon 16 archivos:

1. `src/hu-09/generar_alertas.py`.
2. `data/raw/hu-09/configuracion.json`.
3. `data/raw/hu-09/demanda_prevista.csv` (contrato sin previsiones).
4. `data/raw/hu-09/demostracion/configuracion.json`.
5. `data/raw/hu-09/demostracion/demanda_prevista.csv` (37 filas sintéticas).
6. `data/processed/hu-09/dataset_consolidado.csv`.
7. `data/processed/hu-09/alertas_faltantes.csv`.
8. `data/processed/hu-09/demostracion/dataset_consolidado.csv`.
9. `data/processed/hu-09/demostracion/alertas_faltantes.csv`.
10. `docs/hu-09/LEEME.md`.
11. `reports/hu-09/REPORTE_HU09.md`.
12. `reports/hu-09/prioridades.svg`.
13. `reports/hu-09/demostracion/REPORTE_HU09.md`.
14. `reports/hu-09/demostracion/prioridades.svg`.
15. `tests/test_generar_alertas.py`.
16. `reports/hu-09/VALIDACION_HU09.md` (este informe).

Se modificó únicamente `README.md` entre los archivos preexistentes: incorpora
HU-09, comandos, enlaces y separación de modos. HU-07 y las demás historias
conservan código y resultados. No se añadieron paquetes ni se editaron registros
de HU-02 para evitar modificar resultados de otra historia.

## Limitaciones pendientes

- Integración: falta demanda futura validada, disponibilidad/reservas/bloqueos
  confirmados, stock más reciente y definición del calendario del plazo.
- Las cotizaciones y el inventario disponibles son sintéticos/ficticios; se debe
  actualizar proveedor y vigencia antes de una decisión operativa.
- No hay una equivalencia REP↔RP documentada ni un artefacto local de HU-36 con
  previsiones adicionales. No se fabricó esa relación.
- No se entrenó un modelo ni se relajaron los requisitos de HU-07. El ejemplo
  sintético prueba la lógica; no valida predicciones empresariales.
- Publicación atómica por archivo, sin transacción conjunta de cuatro salidas.
- Compatibilidad declarada Python 3.8+; la validación ejecutada fue en 3.13.7.

Ver [informe de integración](REPORTE_HU09.md),
[demostración](demostracion/REPORTE_HU09.md) y
[documentación](../../docs/hu-09/LEEME.md).
