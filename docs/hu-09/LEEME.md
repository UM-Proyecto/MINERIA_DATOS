# HU-09: alertas de riesgo de faltantes

Identifica repuestos cuya demanda prevista durante la entrega supera el stock
disponible. Distingue ALERTA, SIN_ALERTA y NO_CALCULABLE. Python 3.8 o superior;
solo biblioteca estándar, sin instalaciones adicionales.

## Ejecutar y revisar

Desde la raíz del repositorio, integración con las fuentes existentes:

```bash
python src/hu-09/generar_alertas.py
```

Demostración sintética independiente:

```bash
python src/hu-09/generar_alertas.py --config data/raw/hu-09/demostracion/configuracion.json
```

Pruebas específicas y suite completa:

```bash
python -m unittest discover -s tests -p "test_generar_alertas.py" -v
python -m unittest discover -s tests -p "test_*.py" -v
```

El script resuelve las entradas respecto a la raíz del repositorio, incluso
cuando se invoca desde otro directorio. `--config` selecciona el JSON;
`--salida CARPETA` y `--reporte ARCHIVO.md` permiten salidas de revisión.
Las rutas de estos argumentos son relativas al directorio actual. Las rutas de
entradas del JSON son relativas a la raíz; también se admiten absolutas.

No se ejecuta ningún generador de otra historia. No hay envío por correo ni
notificaciones externas: recibir alertas significa consultar los CSV e informes.

## Dos conjuntos de resultados separados

| Modo | Datos | Informes |
|---|---|---|
| INTEGRACION | `data/processed/hu-09/` | `reports/hu-09/` |
| DEMOSTRACION_SINTETICA | `data/processed/hu-09/demostracion/` | `reports/hu-09/demostracion/` |

Cada modo genera `dataset_consolidado.csv`, `alertas_faltantes.csv`,
`REPORTE_HU09.md` y `prioridades.svg`. El modo figura en las filas, el informe
y el gráfico. Dentro del repositorio se impide escribir en otras historias y
sobrescribir el otro modo. Fuera del repositorio los directorios de revisión
deben elegirse distintos si se quieren conservar ambas ejecuciones.

Los registros NO_CALCULABLE se mantienen en los dos CSV y en el informe. Sus
valores calculados de demanda durante entrega y faltante quedan vacíos, no cero.
El SVG muestra las alertas ordenadas y el conteo de los tres estados. Si no hay
alertas calculadas, indica que eso no demuestra ausencia de riesgo.

## Fuentes y calidad

La sección `fuentes` de cada configuración declara seis entradas:

- HU-17: `data/processed/hu-17/reporte_depuracion_final.csv`.
- HU-18: `data/processed/hu-18/conciliacion_inventario.csv`.
- HU-18: `data/raw/hu-18/stock_inicial.csv`.
- HU-18: `data/processed/hu-18/ajustes_inventario.csv`.
- HU-18: `data/processed/hu-18/historial_ajustes.csv`.
- HU-31: `data/processed/hu-30-31/sintetico/hu31_cotizaciones_proveedor_sintetico.csv`.

Se conservan los originales. Los informes guardan SHA-256 de sus bytes, del
archivo de previsiones y de la configuración. Los CSV incluyen fechas, fuentes,
naturaleza y datos de reservas/bloqueos cuando se aportan. El stock HU-18 es
FICTICIO; los plazos HU-31 son SINTETICO. No se reclasifican como información real.

HU-07 exporta errores MAE sobre evaluación histórica, no previsiones futuras.
Su función de pronóstico no se ejecuta automáticamente: no hay un método elegido
ni una previsión futura validada para esta integración. No se cambia su código,
su selección estadística ni sus resultados. Un CSV de MAE no satisface el
contrato de demanda. HU-30 contiene movimientos históricos, no previsiones; no
se convierte una media histórica en demanda futura de forma implícita.

HU-34 usa RPxxx y proveedores PRxx. HU-09 integra el catálogo REP-xxxx; rechaza
vincular RPxxx sin una equivalencia documentada. Sus ventas e inventario no se
mezclan por posición ni por similitud de nombres.

## Stock: registrado, físico, ajustado y disponible

1. Se selecciona exactamente el corte configurado. No se elige un conteo de otra
   fecha ni se propaga stock hasta hoy asumiendo ausencia de movimientos.
2. Se reconstruye el registrado con la apertura HU-18 y movimientos HU-17 entre
   apertura y corte, excluyendo DUPLICADO e incluyendo PENDIENTE_REVISION como
   HU-18. Se verifica concordancia con entradas, salidas, ajustes previos y saldo.
3. Los ajustes de cortes anteriores ya están incorporados en ese saldo. Los del
   mismo corte se añaden una sola vez, con respaldo único AJUSTE_APLICADO en el
   historial, fecha conocida a la evaluación y aritmética consistente.
4. Se ignoran los ajustes rechazados. Sus repeticiones en el historial quedan
   contadas como registros informativos, no como nuevos movimientos de stock.
5. Si saldo ajustado y conteo físico no coinciden, la disponibilidad no se
   verifica. Tampoco se aplica anticipadamente un ajuste registrado después de
   la fecha de evaluación.
6. La política `permitir_pendientes_con_conteo_coincidente` determina si un
   pendiente HU-17 bloquea aun con coincidencia física. Sus IDs siempre se muestran.

En las fuentes actuales REP-0002 conserva registrado 55, pero el ajuste −2 deja
53; REP-0004 conserva 28 y el ajuste −10 deja 18. Esos ajustes no se vuelven a
restar del conteo físico. REP-0005 (17 frente a 18) y REP-0007 (9 frente a 8)
siguen sin disponibilidad verificable por discrepancia pendiente.

La política de `disponibilidad` admite:

- `no_confirmada`: reservas y bloqueos desconocidos; no calcula stock disponible.
- `asumir_libre_solo_simulacion`: declara ambos cero y exige motivo; solo se
  admite en DEMOSTRACION_SINTETICA.
- `confirmadas`: utiliza `confirmaciones` por código, con `reservas`, `bloqueos`,
  `fecha`, `fuente` y `tipo_dato`. Todos son obligatorios; la fecha debe coincidir
  con el corte. La ausencia de un código no implica reservas cero.

Ejemplo de confirmación, usando cifras sintéticas únicamente para explicar el
contrato; no está incorporado a la configuración de integración:

```json
{
  "politica": "confirmadas",
  "motivo": "Registro de disponibilidad del mismo corte",
  "confirmaciones": {
    "REP-0002": {
      "reservas": "3",
      "bloqueos": "2",
      "fecha": "2026-09-30",
      "fuente": "Ejemplo sintético, sustituir por registro confirmado",
      "tipo_dato": "SINTETICO"
    }
  }
}
```

Stock disponible = ajustado − reservas − bloqueos. Si reservas/bloqueos superan
el ajustado, el registro se bloquea; no se sustituye un dato incoherente por cero.
Bloqueos deben corresponder a unidades aún incluidas en el saldo, para no volver
a descontar una baja ya registrada como ajuste.

Las fechas de corte/evaluación son cierres de día, no instantes intradía.
`max_antiguedad_stock_dias` es una política explícita: superarla impide calcular
riesgo aunque el resto de datos esté disponible. Admitir antigüedad no reconstruye
movimientos desconocidos ni convierte un stock histórico en existencia actual.

## Proveedor y plazo

`proveedores` selecciona un proveedor explícito por código canónico. La referencia
debe ser única y estar vigente: fecha de cotización ≤ evaluación ≤ vigencia.
No se elige otra si vence. `plazo_referencia_dias` conserva el valor histórico;
`plazo_dias` queda vacío cuando no es utilizable.

El plazo sale exclusivamente de `plazo_entrega_dias`. Vigencia, precio,
disponibilidad comercial y condiciones de pago no lo sustituyen. Por ejemplo,
la referencia NGK de REP-0004 tiene crédito a 30 días pero entrega en 3 días.

`tipo_dias_plazo` puede ser `naturales`, `habiles` o `no_definido`, con un motivo.
HU-31 no documenta esa distinción: la integración conserva no_definido; la
demostración declara naturales como supuesto. Los plazos deben ser enteros
entre 0 y 3660. Cero solo representa una entrega inmediata explícita, nunca un
dato ausente. Aun con plazo cero, demanda y stock deben estar informados.

Para hábiles, `calendario_laboral` requiere:

```json
{
  "dias_laborables": [0, 1, 2, 3, 4],
  "feriados": [],
  "fuente": "Ejemplo sintético: lunes a viernes sin feriados declarados"
}
```

Lunes es 0 y domingo 6. Esa lista es un ejemplo, no un calendario boliviano
oficial. Sin calendario se devuelve NO_CALCULABLE. La recepción se desplaza por
días no laborables; el consumo diario se acumula también durante los fines de
semana y feriados intermedios.

## Contrato CSV de demanda prevista

`data/raw/hu-09/demanda_prevista.csv` contiene solo la cabecera: es una entrada
válida que informa ausencia de previsiones, sin inventarlas.

| Columna | Significado |
|---|---|
| sistema_codigos | REP; no RP de HU-34 |
| codigo_repuesto | Código canónico o alias reconocido por HU-17 |
| proveedor | Vacío si la demanda es independiente del proveedor; si se informa, debe coincidir con el seleccionado |
| metodo | Identificación del método/modelo o caso de demostración |
| validado | true/false; false impide calcular |
| fecha_emision | Fecha de creación; no posterior a evaluación |
| inicio_horizonte, fin_horizonte | Cobertura futura, inclusiva; emisión anterior al inicio |
| tipo_pronostico | TASA_CONSTANTE o SERIE_DIARIA |
| fecha_objetivo | Obligatoria para cada valor de SERIE_DIARIA; vacía en una tasa |
| demanda | Decimal no negativo; vacío significa faltante, cero es válido |
| unidad_temporal | unidades/dia, unidades/semana o unidades/mes |
| distribucion | uniforme obligatorio para tasas semanales/mensuales |
| tipo_dato | DOCUMENTADO, ESTIMACION o SINTETICO |
| fuente | Procedencia identificable y no vacía |

Una tasa constante utiliza una fila por repuesto. Una serie diaria utiliza una
fila por código y fecha objetivo. Metadatos contradictorios, dos tasas para el
mismo código o fechas objetivo repetidas se rechazan: no se selecciona un modelo
arbitrariamente ni se suman pronósticos duplicados. Los alias se normalizan antes
de detectar duplicados.

## Cálculo y estados

Ventana: (fecha_evaluacion, fecha_recepcion], con consumo de días naturales
completos. Incluye el día de recepción por contrato explícito.

- Tasa diaria constante: demanda diaria × número de días de la ventana.
- Serie diaria variable: suma de las fechas exactas de la ventana. No usa valores
  fuera de ella ni completa días faltantes con cero.
- Tasa semanal: tasa/7, solo con distribución uniforme explícita.
- Tasa mensual: tasa/días reales del mes de cada fecha; distingue 28/29/30/31.
  Si cruza meses, acumula las partes correspondientes.
- Horizonte que no cubre la recepción: NO_CALCULABLE, sin extrapolar.
- Faltante = max(0, demanda durante entrega − stock disponible).
- ALERTA si demanda > stock; igualdad o demanda inferior produce SIN_ALERTA.

Entradas y resultados utilizan Decimal, con contexto local de 50 dígitos. Las
conversiones temporales periódicas se comparan mediante Fraction exacto de la
biblioteca estándar antes de expresar el resultado en Decimal. Esto evita que
sumar siete veces 2/7 produzca un microfaltante por precisión finita. No se redondea
a unidades enteras antes de comparar. Un valor decimal periódico puede mostrarse
con hasta 50 dígitos; no es una probabilidad ni una precisión estadística.

Se rechazan negativos, no finitos, booleanos numéricos, plazos fraccionarios,
columnas ausentes/repetidas y campos JSON desconocidos/repetidos. Las entradas
numéricas admiten hasta 16 dígitos enteros y 8 decimales. Preferir cadenas JSON
con punto decimal para cantidades.

NO_CALCULABLE conserva todos los motivos aplicables, por ejemplo DEMANDA_FALTANTE,
PLAZO_FALTANTE, STOCK_DISPONIBLE_NO_VERIFICABLE, COTIZACION_VENCIDA,
HORIZONTE_INSUFICIENTE o DIAS_PRONOSTICO_FALTANTES. No se clasifica como SIN_ALERTA.

## Ejemplos incluidos

La integración fija evaluación 10/11/2026 y stock 30/09/2026, con máximo 30 días.
No hay previsiones ni reservas/bloqueos confirmados. Además, nueve referencias
seleccionadas vencieron y el tipo de días no está confirmado. Resultado esperado:
**0 ALERTA, 0 SIN_ALERTA, 10 NO_CALCULABLE**.

La demostración fija evaluación 20/10/2026 y acepta explícitamente el corte de
septiembre con antigüedad de 20 días. Sus tasas y serie diaria se eligieron para
mostrar la lógica, no proceden de un modelo empresarial. validado=true significa
revisión del ejemplo, no validación estadística. Resultado esperado:
**4 ALERTA, 3 SIN_ALERTA, 3 NO_CALCULABLE**.

| Orden de alerta | Código | Stock | Demanda durante entrega | Plazo natural | Faltante |
|---:|---|---:|---:|---:|---:|
| 1 | REP-0002 | 53 | 90 | 45 | 37 |
| 2 | REP-0001 | 95 | 120 | 3 | 25 |
| 3 | REP-0008 | 45 | 60 | 15 | 15 |
| 4 | REP-0009 | 45 | 60 | 30 | 15 |

REP-0004 queda exactamente en igualdad: 18 de stock y 18 de demanda. REP-0006
demuestra demanda cero. REP-0010 usa 7 unidades/semana con reparto uniforme.
REP-0003 carece de demanda y de cotización vigente; REP-0005 además tiene una
discrepancia física; REP-0007 conserva discrepancia física aunque tenga demanda
y plazo. El desempate de prioridades es estable por código y proveedor.

## Integridad y validación

Los cuatro artefactos de cada ejecución se calculan antes de escribir y se
publican mediante temporales. Un error de validación devuelve código 1 y conserva
las salidas anteriores. La escritura es atómica por archivo, no una transacción
conjunta: ante una interrupción de disco durante publicación se deben regenerar
los cuatro archivos del modo.

El motor público `evaluar_riesgo(registro, demanda, calendario_laboral)` no escribe
archivos y permite integrar stock disponible verificable aportado por otro
sistema. `cargar_integracion` prepara las fuentes actuales; `ejecutar` genera
los CSV e informes. Ninguna función ejecuta pronósticos de HU-07 implícitamente.

Las pruebas cubren los tres criterios originales, calendarios, unidades,
precisión, plazos vencidos, conciliación, trazabilidad, separación de modos,
reproducibilidad y conservación de fuentes. El informe de validación de entrega
está en `reports/hu-09/VALIDACION_HU09.md`.
