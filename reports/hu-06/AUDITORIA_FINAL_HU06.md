# Auditoría final de HU-06

Fecha: 10/11/2026. Rama: `feature/hu-06-escenarios`.
Entorno ejecutado: Python 3.13.7, Windows.

## Dictamen

La implementación cumple los tres criterios originales de HU-06 dentro del
alcance de simulación documentado. Las 33 pruebas específicas y las 43 de la
suite completa pasan, sin fallos, errores ni pruebas omitidas. El recálculo
independiente coincide con los CSV. No se encontraron defectos bloqueantes en
los escenarios evaluados.

La auditoría no modificó código, configuración, pruebas ni resultados existentes.
Se agrega únicamente este informe. No se realizó commit, push ni staging.

## Criterios originales y evidencia

| Criterio | Estado | Evidencia |
|---|---|---|
| Un escenario base y al menos dos alternativas | CUMPLIDO | Se exige exactamente un BASE y alternativas CAMBIARIA y LOGISTICA. La configuración incluye además COMBINADO. Se rechazan bases ausentes/repetidas y alternativas obligatorias ausentes. |
| Costo total y diferencia respecto al base | CUMPLIDO | Se calculan mercancía USD, gastos en su moneda, total BOB, diferencia BOB y diferencia porcentual. Se recalcularon los cuatro escenarios con Decimal, sin utilizar las funciones de cálculo del módulo. El detalle reconcilia con cada total. |
| Cantidades y precios constantes salvo modificación expresa | CUMPLIDO | Las 20 filas de mercancía del detalle corresponden a cinco líneas idénticas en cuatro escenarios. Se prohíben modificaciones de canasta en CAMBIARIA/LOGISTICA. Las modificaciones expresas de COMBINADO conservan valores originales y motivo. |

## Ocho verificaciones solicitadas

| Verificación | Resultado y evidencia |
|---|---|
| 1. Tres criterios originales | Cumplidos, según la matriz anterior. |
| 2. Las 33 pruebas específicas | 33 ejecutadas, 33 OK; además, regresión completa de 43 pruebas OK. Evidencia individual más abajo. |
| 3. Constancia de cantidades y precios | Se comparó por movimiento, código, cantidad y precio cada escenario serializado contra la canasta y las compras originales. Los cuatro mantienen 205 unidades y 2740.85 USD. También se probaron cambios aislados de solo precio y solo cantidad, sin persistirlos. |
| 4. Costos y diferencias | Se recalcularon mercancía, flete/seguro, CIF, porcentajes y transporte local con Decimal a partir de las fuentes. Se comprobaron cada total, diferencia, porcentaje y suma del detalle. |
| 5. Duplicados y líneas legítimas | Se cotejaron las ocho filas seleccionadas contra HU-17: cinco ORIGINAL conservadas, tres DUPLICADO excluidas. Las pruebas con dos líneas válidas de una misma orden conservan ambas; tampoco se colapsan documentos distintos del mismo repuesto. |
| 6. Fuentes históricas y sintéticas | Se verificaron fuente, fecha, unidad, naturaleza y huella en las 40 filas de detalle. Tipos de cambio DOCUMENTADO, tarifas INE ESTIMACION, mercancía y complementos SINTETICO. Peso de 100 kg declarado como supuesto. Se verificaron las seis huellas de entrada. |
| 7. Coherencia de artefactos | Se leyeron los tres CSV y se validaron filas y cifras. Se regeneraron en temporal, dos veces, los tres CSV, informe y SVG: los cinco coinciden byte a byte con la entrega. El XML del SVG, sus cuatro etiquetas y anchos de barras coinciden con los totales. README y guía describen la misma canasta, supuestos y ejecución; se comprobaron ocho enlaces locales preexistentes. |
| 8. Cambios fuera de HU-06 | `git diff --name-only` muestra únicamente README.md entre los archivos ya versionados. No hay cambios de archivos versionados en data, docs, src, reports, notebooks, tests ni .gitignore. Se compararon 93 archivos con las huellas guardadas al terminar la implementación: ninguno cambió. |

## Resultados comprobados independientemente

| Escenario | TC BOB/USD | Mercancía USD | Logística USD | Total BOB | Diferencia BOB | Diferencia % |
|---|---:|---:|---:|---:|---:|---:|
| BASE | 11.84 | 2740.85 | 474.43 | 38068.92 | 0.00 | 0.00 |
| CAMBIARIA | 11.99 | 2740.85 | 474.43 | 38551.21 | 482.29 | 1.27 |
| LOGISTICA | 11.84 | 2740.85 | 555.93 | 39033.88 | 964.96 | 2.53 |
| COMBINADO | 11.99 | 2740.85 | 555.93 | 39528.40 | 1459.48 | 3.83 |

Mercancía USD = 411.20 + 641.70 + 491.00 + 799.00 + 397.95 = 2740.85.

| Componente USD | Base/cambiario | Logístico/combinado |
|---|---:|---:|
| Flete y seguro: tarifa INE × 100 kg | 320.56 | 398.46 |
| CIF simulado | 3061.41 | 3139.31 |
| Nacionalización/agente: 3.476% del CIF | 106.41 | 109.12 |
| Comisión: 1.142% del CIF | 34.96 | 35.85 |
| Transporte local: 0.125 USD/kg × 100 kg | 12.50 | 12.50 |
| Total logística USD | 474.43 | 555.93 |

Cada importe se redondea a centavos con ROUND_HALF_UP en su moneda; cada línea
USD se convierte y redondea por separado a BOB antes de sumar. El agregado USD
convertido de una sola vez puede diferir en centavos: no es el procedimiento
documentado. Diferencia = total del escenario − total base; porcentaje =
diferencia / total base × 100, redondeado a dos decimales.

La alternativa cambiaria conserva conceptos, tarifas, bases de cálculo, monedas
e importes logísticos de origen. La logística conserva el tipo de cambio; el
cambio de CIF recalcula nacionalización y comisión sin modificar sus tasas.
El flete INE ya incluye seguro y no se cobra otro. Las filas TIPO_CAMBIO son
metadatos con importes vacíos y no se suman como un gasto.

## Canasta, exclusiones y cambios expresos

| Orden | Movimiento válido | Repuesto | Cantidad | Precio USD | Movimiento duplicado excluido |
|---|---|---|---:|---:|---|
| OC-5003 | 1005 | REP-0002 | 40 | 10.28 | 1006 |
| OC-5006 | 1011 | REP-0004 | 10 | 64.17 | — |
| OC-5008 | 1015 | REP-0006 | 100 | 4.91 | 1016 |
| OC-5010 | 1020 | REP-0008 | 20 | 39.95 | — |
| OC-5011 | 1021 | REP-0009 | 35 | 11.37 | 1022 |

Las exclusiones son por movimiento clasificado, no por eliminar la orden
entera. En la configuración entregada no hay modificaciones de precio o cantidad.

En memoria, sobre copias de la configuración, se verificó adicionalmente:

- Cambiar únicamente el precio del movimiento 1005 a 11.00 USD conserva todas
  las cantidades y los precios de las demás líneas.
- Cambiar únicamente su cantidad de 40 a 45, redeclarando un peso supuesto de
  105 kg con motivo, conserva todos los precios y las cantidades restantes.
- Ninguno de esos experimentos alteró configuración, canasta o CSV entregados.

## Ejecución de pruebas

```text
python -m unittest discover -s tests -p "test_comparar_escenarios.py" -v
Ran 33 tests — OK

python -m unittest discover -s tests -p "test_*.py" -v
Ran 43 tests — OK
```

Ambas ejecuciones terminaron con código 0. La segunda incluye las 33 pruebas
de HU-06, las dos de HU-07 y las ocho de HU-02. No hubo fallos, errores ni skips.

Todas las pruebas siguientes están en
[`tests/test_comparar_escenarios.py`](../../tests/test_comparar_escenarios.py).
Los nombres de la tabla son los nombres reales de los métodos ejecutados.

| # | Prueba | Resultado | Evidencia comprobada por la prueba |
|---:|---|---|---|
| 1 | `test_admite_historia_sintetica_ausente_en_hu17_con_etiqueta` | OK | Conserva la línea sintética sin clasificación HU-17 con etiqueta explícita. |
| 2 | `test_alternativas_deben_cambiar_el_factor_declarado` | OK | Rechaza alternativa cambiaria con el mismo valor y alternativa logística sin cambios. |
| 3 | `test_base_y_dos_alternativas_con_calculo_independiente` | OK | Caso pequeño: mercancía 35 USD; totales 623.50, 746.70 y 735.50 BOB; diferencias 123.20 y 112.00; porcentajes 19.76% y 17.96%. Incluye 7.50 BOB de origen sin reconversión. |
| 4 | `test_calcula_m3_y_contenedores_con_parametros_expresos` | OK | 2.5 m³ × 2 = 5.00 USD; dos contenedores × 2 = 4.00 USD; rechaza 1.5 contenedores. |
| 5 | `test_cambio_faltante_no_se_imputa_y_fecha_futura_se_rechaza` | OK | Rechaza observación ausente del 22/10 y fecha posterior al análisis del 24/10. |
| 6 | `test_cambio_supuesto_exige_motivo_y_conserva_naturaleza` | OK | Cambio hipotético 9 con motivo se registra SINTETICO y produce ahorro. |
| 7 | `test_cambios_expresos_de_precio_y_cantidad_en_combinado` | OK | Modificación autorizada lleva mercancía de 35 a 45 USD; base intacto; valores originales y motivo en el informe. |
| 8 | `test_conserva_canasta_y_lineas_validas_del_mismo_documento` | OK | Mantiene dos líneas válidas de OC-1 en todos los escenarios y excluye solo su duplicado; logística cambiaria idéntica. |
| 9 | `test_equipo_requiere_clasificacion_y_coincidencia_con_hu17` | OK | Rechaza cantidades contradictorias entre historias y movimientos del equipo sin clasificación. |
| 10 | `test_logistica_exige_cambio_efectivo_y_no_solo_otra_fuente` | OK | Cambiar de referencia sin cambiar ningún importe no satisface una alternativa logística. |
| 11 | `test_modificaciones_exigen_linea_unica_y_motivo` | OK | Rechaza línea inexistente, motivo vacío y dos cambios de la misma línea. |
| 12 | `test_modificar_cantidad_exige_redeclarar_peso` | OK | Rechaza modificar cantidades manteniendo implícitamente el peso heredado. |
| 13 | `test_no_descarta_documentos_distintos_del_mismo_repuesto` | OK | Conserva tres líneas válidas aun cuando dos documentos contienen el mismo repuesto. |
| 14 | `test_no_permite_escribir_resultados_de_otras_historias` | OK | Impide salida en HU-32 y sobrescritura del README; su contenido permanece intacto. |
| 15 | `test_obligatorios_no_permiten_cambios_fuera_de_su_factor` | OK | Rechaza cambios de canasta en base/alternativas y cambios logísticos en CAMBIARIA o cambiarios en LOGISTICA. |
| 16 | `test_pendientes_excluidos_salvo_seleccion_expresa` | OK | Documento sin líneas válidas se rechaza por defecto; inclusión expresa conserva su estado PENDIENTE_REVISION. |
| 17 | `test_rechaza_bases_cif_de_moneda_o_alcance_incompatibles` | OK | Rechaza base CIF con flete BOB y con gastos posteriores incluidos sin desglose. |
| 18 | `test_rechaza_costos_pendientes_y_alcance_incompleto` | OK | No convierte PENDIENTE en cero ni omite el transporte local requerido. |
| 19 | `test_rechaza_doble_seguro_y_costo_incluido_en_precio` | OK | Rechaza seguro adicional a flete/seguro conjunto y gastos ya incluidos en el precio. |
| 20 | `test_rechaza_ids_y_campos_desconocidos` | OK | Rechaza IDs repetidos y propiedades fuera del esquema. |
| 21 | `test_rechaza_json_ambiguo_y_referencia_mal_formada` | OK | Rechaza claves JSON repetidas y referencias logísticas que no son objetos. |
| 22 | `test_rechaza_numeros_invalidos` | OK | Rechaza NaN, infinito, negativos, cero donde no procede, texto, booleanos, float, magnitudes fuera de límites y cantidades fraccionarias. |
| 23 | `test_rechaza_parametros_fisicos_ausentes` | OK | Una tarifa por kg sin peso declarado falla antes de generar resultados. |
| 24 | `test_rechaza_referencias_ambiguas_y_csv_sin_columnas` | OK | Rechaza múltiples coincidencias de una referencia y CSV sin columnas requeridas. |
| 25 | `test_rechaza_unidades_incompatibles_e_indices` | OK | Rechaza puntos de índice, EUR/kg, USD/tonelada y BOB/USD como gasto; SCFI no se trata como dinero. |
| 26 | `test_redondeo_half_up_por_linea_y_no_sobre_el_agregado` | OK | Dos líneas de 0.005 BOB se redondean individualmente a 0.01: mercancía total 0.02 BOB. |
| 27 | `test_reproducibilidad_fuentes_intactas_y_svg_valido` | OK | Dos ejecuciones producen cinco salidas idénticas; entradas intactas y SVG XML válido. |
| 28 | `test_requiere_exactamente_un_base_y_ambos_tipos_alternativos` | OK | Rechaza conjuntos incompletos, sin base o con dos bases. |
| 29 | `test_resuelve_seguro_porcentual_del_propio_cif` | OK | Seguro del 10% del propio CIF produce prima 5.56 y CIF 55.56; rechaza 100%. |
| 30 | `test_trazabilidad_y_reconciliacion_del_detalle` | OK | Todas las filas tienen procedencia, fecha, unidad y naturaleza; suma del detalle igual al total. |
| 31 | `test_un_error_no_sobrescribe_ultima_salida_valida` | OK | Configuración inválida conserva la comparación previamente generada. |
| 32 | `test_cli_desde_otra_carpeta_y_salida_de_error` | OK | CLI funciona fuera del repositorio; configuración inexistente devuelve código 1. |
| 33 | `test_resultados_del_pedido_existente_con_valores_esperados` | OK | Cinco líneas, 205 unidades, tres duplicados excluidos y los cuatro totales/diferencias esperados del repositorio. |

Las pruebas son evidencia de los casos ejecutados, no una garantía sobre todas
las configuraciones posibles. La compatibilidad declarada con Python 3.8 no se
ejecutó en un intérprete 3.8 durante esta auditoría.

## Archivos de la entrega y revisión Git

Único archivo previamente versionado modificado:

- [`README.md`](../../README.md): 24 inserciones y una eliminación; incorpora
  HU-06, su ubicación e instrucciones. No cambia instrucciones de otras HU.

Nueve archivos nuevos de implementación, todavía sin seguimiento en Git:

| Archivo | Función |
|---|---|
| [`src/hu-06/comparar_escenarios.py`](../../src/hu-06/comparar_escenarios.py) | Módulo de comparación y generación |
| [`data/raw/hu-06/escenarios.json`](../../data/raw/hu-06/escenarios.json) | Escenarios y supuestos explícitos |
| [`data/processed/hu-06/canasta_base.csv`](../../data/processed/hu-06/canasta_base.csv) | Cinco líneas originales válidas |
| [`data/processed/hu-06/comparacion_escenarios.csv`](../../data/processed/hu-06/comparacion_escenarios.csv) | Cuatro escenarios y diferencias |
| [`data/processed/hu-06/detalle_costos.csv`](../../data/processed/hu-06/detalle_costos.csv) | 40 filas: 20 de mercancía, 16 de logística y cuatro de cambio |
| [`docs/hu-06/LEEME.md`](../../docs/hu-06/LEEME.md) | Ejecución, configuración, fórmulas y límites |
| [`reports/hu-06/REPORTE_HU06.md`](REPORTE_HU06.md) | Resultados e interpretación |
| [`reports/hu-06/comparacion_escenarios.svg`](comparacion_escenarios.svg) | Gráfico comparativo sin dependencias externas |
| [`tests/test_comparar_escenarios.py`](../../tests/test_comparar_escenarios.py) | 33 pruebas específicas |

Este informe `reports/hu-06/AUDITORIA_FINAL_HU06.md` es el único archivo nuevo
añadido durante la auditoría: quedan diez archivos nuevos y README modificado.

Se revisaron `git diff`, `git diff --stat`, `git diff --name-only`,
`git status --short`, `git ls-files --others --exclude-standard` y
`git diff --cached`. `git diff --check` no reportó errores; también se comprobaron
espacios finales en los nueve archivos nuevos de implementación, que no aparecen
en el diff normal por estar aún sin seguimiento. No hay cambios preparados en
el índice. El diff normal muestra solo README por esa misma razón.

Las regeneraciones se realizaron en directorios temporales eliminados al terminar.
Las seis entradas de HU-17/HU-30/31/HU-32 conservaron sus SHA-256. La comparación
de 93 archivos contra la instantánea del cierre de implementación no encontró
cambios. Git tampoco muestra cambios de archivos versionados de otras historias.

## Pendientes y límites

No hay correcciones de código o datos pendientes derivadas de los casos auditados.
Permanecen los límites documentados del producto:

- El peso de 100 kg es supuesto. Faltan pesajes, ruta y alcance confirmados e
  Incoterm antes de sustituir la simulación por una operación real.
- Las referencias son históricas; el paralelo tiene un solo punto y el TCO no
  equivale al tipo de cambio efectivo pagado por la empresa.
- Los precios/cantidades y complementos son ficticios o sintéticos. No hay
  liquidación real de aranceles, IVA ni todos los gastos de importación.
- La escritura es atómica por archivo, no una transacción conjunta de los cinco
  artefactos: una interrupción durante la publicación puede requerir regenerarlos.

El alcance funcional auditado es una comparación reproducible de escenarios
simulados. La subida a GitHub queda sin ejecutar, conforme a la instrucción del usuario.
