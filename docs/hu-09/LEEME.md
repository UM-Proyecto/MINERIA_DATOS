# HU-09 y SCRUM-66: alertas de reposición

HU-09 tiene dos partes separadas: las **alertas de reposición**, con una sola lógica para todo el proyecto, y la
**verificación de datos** de inventario y plazo de Sabrina, que se conserva aparte (ver más abajo).

Una sola lógica de alertas para todo el proyecto. Vive en el motor del simulador (`src/simulador/motor.js`, que usa la
app, y su referencia en Python `src/simulador/motor_ref.py`, que usan las pruebas y el exportador). La app la muestra en
la vista «Alertas de reposición» y en «Plan con presupuesto»; `src/hu-09/generar_alertas.py` la exporta a CSV, a un
informe y a un gráfico para revisarla sin abrir la app. Python 3.8 o superior, solo biblioteca estándar.

## Cómo se ejecuta

Desde cualquier carpeta:

```bash
python src/hu-09/generar_alertas.py                 # dólar oficial más reciente de datos_app.json
python src/hu-09/generar_alertas.py --tc 12.50      # otro dólar, para comparar (el informe lo dice)
python -m unittest tests.test_generar_alertas -v    # 20 pruebas
```

Opciones: `--datos` (otro `datos_app.json`), `--salida CARPETA` (para el CSV) y `--reporte ARCHIVO.md` (el SVG queda al
lado). Si algo falla, el script sale con código 1 y no toca las salidas anteriores.

| Salida | Qué es |
|---|---|
| `data/processed/hu-09/alertas_faltantes.csv` | Una fila por repuesto, en orden de prioridad |
| `reports/hu-09/REPORTE_HU09.md` | Conteos, criterios y la tabla |
| `reports/hu-09/prioridades.svg` | Los repuestos para pedir o vigilar: venta durante la entrega frente a stock y en camino |

## La lógica

Para cada repuesto, con su proveedor asignado:

- **Venta durante la entrega** = venta diaria pronosticada × plazo del proveedor. El pronóstico es SBA (Croston
  corregido) para demanda intermitente o irregular y la media de 12 meses para el resto. No se redondea antes de
  comparar.
- **Faltante previsto** = máximo entre cero y la venta durante la entrega menos (stock + en camino). La igualdad no es
  alerta. En el CSV, la columna `alerta_faltante` lo resume en ALERTA, SIN_ALERTA o NO_CALCULABLE.
- **Estado de reposición:**
  - «Pedir ya»: stock + en camino es igual o menor que el punto de pedido.
  - «Vigilar»: a la venta pronosticada, llega al punto de pedido antes de que el proveedor pueda entregar.
  - «Cubierto»: el resto.
  - «Sin datos»: falta o no es válido el stock, el plazo, el historial de venta o el punto de pedido. Las cifras
    calculadas quedan vacías, nunca en cero, y se informa el motivo (`STOCK_FALTANTE`, `PLAZO_FALTANTE`,
    `DEMANDA_FALTANTE`, `REGLA_FALTANTE`). Un valor negativo, infinito o que no es número cuenta como faltante. Cero sí
    es válido: venta cero y plazo cero (entrega inmediata) se calculan.
- **Cantidad sugerida** = nivel máximo − (stock + en camino), al menos una si el estado es «Pedir ya» o «Vigilar».
- **Orden:** estado; dentro de cada estado, faltante de mayor a menor, después los días hasta el punto de pedido y el
  código.

Con los datos actuales (dólar oficial 11,70 Bs al 12-11-2026) salen 3 «Pedir ya», 4 «Vigilar», 23 «Cubierto» y
ninguno «Sin datos». Ningún repuesto tiene faltante con la venta promedio. No quiere decir que no haya riesgo: la venta
de estos repuestos es intermitente y el promedio esconde los meses fuertes. Por eso el simulador prueba 1.500 futuros:
REP-0022, por ejemplo, no tiene faltante promedio, pero se queda sin stock en 44 de cada 100 futuros.

Datos: ventas REALES de carparts con el mes adaptado; stock, punto de pedido, plazo y costo SINTÉTICOS (SCRUM-55). No
hay registro de reservas ni de bloqueos, así que el stock disponible es el registrado.

## De dónde viene cada parte

La historia tuvo dos versiones que se hicieron por separado y se unieron el 12-11-2026, para que el proyecto tenga una
sola forma de calcular alertas.

**Sabrina Adrian Zelaya (HU-09, rama `feature/hu-09-alertas-faltantes`, commit 307c1fb).** Su versión definió el
criterio de faltante: la venta prevista durante la entrega contra el stock disponible, con la igualdad sin alerta.
También fijó las reglas de calidad que ahora tiene la lógica única:
- un dato que falta no se convierte en cero y el repuesto queda visible como no calculable, con su motivo;
- plazo cero y venta cero son datos válidos;
- se rechazan negativos y valores no finitos;
- no se redondea antes de comparar;
- los repuestos se ordenan por faltante;
- el exportador se puede correr desde cualquier carpeta, regenera idéntico y no pisa la salida anterior si falla.

El exportador conserva los nombres de sus salidas (CSV, informe y `prioridades.svg`) y el vocabulario ALERTA,
SIN_ALERTA y NO_CALCULABLE. De sus 40 pruebas, las que aplican a la lógica única están en
`tests/test_generar_alertas.py`.

**Simulador (SCRUM-66).** Aportó el pronóstico para demanda intermitente (SBA), el punto de pedido con los estados «Pedir
ya», «Vigilar» y «Cubierto», la cantidad sugerida con su costo puesto en Santa Cruz, el plan con presupuesto, la vista
en la app y la comparación con los 1.500 futuros del simulador.

## Verificación de datos (Sabrina Adrian Zelaya)

La otra mitad de su versión se conserva tal cual, aparte de las alertas, en `src/hu-09/verificar_datos.py`. Trabaja
sobre los datos FICTICIOS de HU-17, HU-18 y HU-31 (10 repuestos) y reconstruye, para cada uno:
- el stock registrado al corte, con la apertura de HU-18 y los movimientos depurados de HU-17, excluyendo duplicados;
- los ajustes del mismo corte, contados una sola vez y con su respaldo en el historial;
- la diferencia con el conteo físico;
- las reservas y bloqueos confirmados;
- el plazo vigente de la cotización de HU-31.

Dice qué se pudo verificar y qué no, con su motivo, y no calcula alertas.

```bash
python src/hu-09/verificar_datos.py                 # data/processed/hu-09/dataset_consolidado.csv y reports/hu-09/VERIFICACION_DATOS_HU09.md
python -m unittest tests.test_verificar_datos -v    # 17 pruebas
```

Con los datos actuales no se verifica ninguno de los 10 repuestos: no hay registro de reservas ni de bloqueos, 9 de las
10 cotizaciones están vencidas y 2 conteos físicos no coinciden con el saldo. La configuración está en `data/raw/hu-09/configuracion.json`. El contrato del CSV de
demanda prevista (`data/raw/hu-09/demanda_prevista.csv`, solo la cabecera) se sigue validando al cargar.

## Qué cambió el 12-11-2026

- La evaluación del riesgo de faltante de la versión de Sabrina (venta durante la entrega contra stock disponible)
  pasó a la lógica única del motor, junto con sus criterios. Su generador quedó dividido: `generar_alertas.py` exporta
  las alertas del motor y `verificar_datos.py` conserva la conciliación.
- Se retiró el modo de demostración, con sus configuraciones, sus resultados y su informe. La política
  `asumir_libre_solo_simulacion`, que solo existía para ese modo, ya no se acepta.
- De sus 40 pruebas, las 17 de conciliación siguen en `tests/test_verificar_datos.py`, con la configuración real y
  un pronóstico de prueba escrito en la propia prueba. Las de alertas pasaron a `tests/test_generar_alertas.py`. La
  prueba que reproducía la demostración y las del calendario de días hábiles y de las series diarias de demanda se
  retiraron, porque la lógica única usa el pronóstico del motor.
- `reports/hu-09/AUDITORIA_FINAL_HU09.md` y `reports/hu-09/VALIDACION_HU09.md` registran la entrega del 10-11-2026 tal
  como se hizo. Llevan una nota al inicio que remite a este documento.

Todo lo anterior sigue en el historial del repositorio, en el commit 307c1fb.
