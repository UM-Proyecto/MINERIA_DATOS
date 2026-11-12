# Minería de Datos: apoyo a las decisiones de compra de MULTIPARTES

Proyecto de Minería de Datos (Universidad Privada del Valle, VI semestre, 2026). Equipo: Sabrina Adrian Zelaya, Samuel
Castillo y Fiorella Sandoval. Docente: Ing. William Mauricio. Tablero de trabajo:
[Jira SCRUM](https://fsandoval09.atlassian.net/jira/software/projects/SCRUM/boards/1).

**Pregunta enfocada.** ¿Qué técnicas de análisis de datos permiten apoyar las decisiones de compra de la empresa
MULTIPARTES de Santa Cruz de la Sierra durante el segundo semestre de 2026?

**Respuesta del proyecto: un simulador de compras.** La app
[`reports/simulador/MULTIPARTES_Simulador_Compras.html`](reports/simulador/MULTIPARTES_Simulador_Compras.html) se abre
con doble clic y le dice al jefe de compras cuánto pedir y cuándo. Junta cinco técnicas: clasificación de la demanda
(Syntetos y Boylan, ABC), pronóstico para demanda intermitente (SBA), simulación de Monte Carlo con 1.500 futuros,
análisis de sensibilidad con dólar de quiebre y validación con los últimos 12 meses. El detalle está en la sección
[Simulador de compras](#simulador-de-compras-scrum-53-a-scrum-70).

## De dónde salen los datos

- **FICTICIOS:** movimientos de inventario, stock, catálogo, ventas y compras. MULTIPARTES facilitó una muestra inicial
  pequeña, de unos 20 registros. Para poder aplicar y comparar las técnicas, el equipo la amplió con datos de prueba
  con la misma estructura. Cada archivo indica si es de prueba.
- **PÚBLICOS y reales, del simulador:** las ventas mensuales de repuestos de auto del conjunto carparts (Hyndman,
  Koehler, Ord y Snyder, 2008), con las fechas adaptadas a 2022-2026, y el tipo de cambio oficial diario del BCB desde el
  27-06-2026. Proveedores, costos, precios y stock del simulador son SINTÉTICOS y así están marcados.
- **PÚBLICOS y reales:** los fletes de importación (INE de Bolivia, cotizaciones de un agente de carga y el índice SCFI de
  Shanghái) y el tipo de cambio oficial del Banco Central de Bolivia.
- **MIXTOS:** los costos de importación de HU-31 y la comparación del tipo de cambio de HU-32 combinan las fuentes
  públicas con datos FICTICIOS de la empresa.
- El registro de cada conjunto, con su origen, su fecha de corte y su fecha de actualización, está en
  [`data/processed/hu-02/registro_actualizaciones.csv`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-02/registro_actualizaciones.csv).

## Criterios de éxito (HU-33)

| Criterio | Meta | Línea base (datos ficticios) |
|---|---|---|
| Pronóstico de salidas mejor que la referencia «último periodo» (MAE) | 15 % menos de error | Sin método elegible: falta un año de historial |
| Costo de importación con respaldo documentado | 80 % o más | 6 de 15 componentes (40 %) |
| Días entre la fecha de los datos y la decisión de compra | 30 días o menos | 42 días |

## Documentos del equipo

- Pregunta enfocada y objetivo: [`docs/pregunta-enfocada/`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/pregunta-enfocada)
- HU-29, fuentes y permisos de acceso: [`docs/hu-29/`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-29)
- Los `.zip` de `docs/hu-18` y `docs/hu-32` son las entregas originales tal como se subieron. Los archivos que valen son
  los de `data/` y `src/`.

## Historias de usuario terminadas

| HU | Jira | Responsable | Qué hace | Origen de los datos | Código | Resultado | Documento |
|---|---|---|---|---|---|---|---|
| Pregunta enfocada | [SCRUM-37](https://fsandoval09.atlassian.net/browse/SCRUM-37) | Fiorella | Pregunta y objetivo de investigación | No usa datos | — | — | [`docs/pregunta-enfocada`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/pregunta-enfocada) |
| HU-29 | [SCRUM-5](https://fsandoval09.atlassian.net/browse/SCRUM-5) | Sabrina | Fuentes de datos y permisos de acceso | No usa datos | — | — | [`docs/hu-29`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-29) |
| HU-02 | [SCRUM-12](https://fsandoval09.atlassian.net/browse/SCRUM-12) | Samuel | Registro de origen y fecha de actualización de cada conjunto de datos | FICTICIO y público, según el conjunto (lo dice el propio registro) | [`src/hu-02`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-02) | [`data/processed/hu-02`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-02) | [`reports/hu-02`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/reports/hu-02) |
| HU-03 | [SCRUM-16](https://fsandoval09.atlassian.net/browse/SCRUM-16) · [SCRUM-51](https://fsandoval09.atlassian.net/browse/SCRUM-51) | Fiorella | Panel interactivo de evolución de precios (con la referencia de 11 BOB/USD) | FICTICIO (precios), convertidos con 11 BOB/USD, una referencia fija elegida por el equipo | [`src/hu-03`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-03) | [`reports/hu-03`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/reports/hu-03) | [`docs/hu-03`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-03) |
| HU-06 | — | Equipo | Comparación de escenarios cambiarios y logísticos con una canasta fija | MIXTO SIMULADO: compras ficticias, referencias de HU-31/HU-32 y supuestos explícitos | [`src/hu-06`](src/hu-06) | [`data/processed/hu-06`](data/processed/hu-06) · [`informe`](reports/hu-06/REPORTE_HU06.md) | [`docs/hu-06`](docs/hu-06/LEEME.md) |
| HU-07 | [SCRUM-20](https://fsandoval09.atlassian.net/browse/SCRUM-20) | Fiorella | Comparación de tres técnicas de pronóstico (MAE) | FICTICIO (movimientos de HU-17) | [`src/hu-07`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-07) | [`data/processed/hu-07`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-07) | [`reports/hu-07`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/reports/hu-07) |
| HU-09 | — | Equipo | Alertas de faltantes con stock, demanda futura y plazo | Integración incompleta de fuentes ficticias; demostración sintética separada | [`src/hu-09`](src/hu-09) | [`resultados`](data/processed/hu-09) · [`informe`](reports/hu-09/REPORTE_HU09.md) | [`docs/hu-09`](docs/hu-09/LEEME.md) |
| HU-17 | [SCRUM-9](https://fsandoval09.atlassian.net/browse/SCRUM-9) | Sabrina | Normalización de códigos y depuración de duplicados | FICTICIO | [`src/hu-17`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-17) | [`data/raw/hu-17`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/raw/hu-17) | [`data/processed/hu-17`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-17) |
| HU-18 | [SCRUM-10](https://fsandoval09.atlassian.net/browse/SCRUM-10) | Sabrina | Conciliación del inventario con conteos físicos | FICTICIO | [`src/hu-18`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-18) | [`data/raw/hu-18`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/raw/hu-18) | [`data/processed/hu-18`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-18) |
| HU-30 | [SCRUM-6](https://fsandoval09.atlassian.net/browse/SCRUM-6) | Samuel | Histórico de movimientos de inventario | FICTICIO | [`src/hu-30-31`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-30-31) | [`data/processed/hu-30-31`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-30-31) | [`docs/hu-30-31`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-30-31) |
| HU-31 | [SCRUM-7](https://fsandoval09.atlassian.net/browse/SCRUM-7) | Samuel | Cotizaciones y costos de importación | MIXTO: fletes públicos (INE, agente de carga, SCFI) y cotizaciones de proveedor FICTICIAS | [`src/hu-30-31`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-30-31) | [`data/processed/hu-30-31`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-30-31) | [`docs/hu-30-31`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-30-31) |
| HU-32 | [SCRUM-8](https://fsandoval09.atlassian.net/browse/SCRUM-8) | Sabrina | Series históricas del tipo de cambio | MIXTO: tipo de cambio oficial del BCB (público) y tipo de cambio pagado por la empresa (FICTICIO) | [`src/hu-32`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-32) | [`data/processed/hu-32`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-32) | [`docs/hu-32`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-32) |
| HU-33 | [SCRUM-44](https://fsandoval09.atlassian.net/browse/SCRUM-44) | Samuel | Criterios de éxito del proyecto (3 indicadores) | Se calculan sobre HU-02, HU-07, HU-30 y HU-31 | [`docs/hu-33`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-33) | [`docs/hu-33/CRITERIOS_APROBADOS.md`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-33/CRITERIOS_APROBADOS.md) | [`docs/hu-33`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/docs/hu-33) |
| HU-34 | [SCRUM-45](https://fsandoval09.atlassian.net/browse/SCRUM-45) · [SCRUM-50](https://fsandoval09.atlassian.net/browse/SCRUM-50) | Fiorella | Descripción y limpieza de los conjuntos de datos | FICTICIO (simulados) | [`src/hu-34`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/src/hu-34) | [`data/processed/hu-34`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/data/processed/hu-34) | [`reports/hu-34`](https://github.com/UM-Proyecto/MINERIA_DATOS/tree/main/reports/hu-34) |
| HU-36 | [SCRUM-47](https://fsandoval09.atlassian.net/browse/SCRUM-47) | Fiorella | Repetición de los pronósticos con 284 días de historial | FICTICIO | Pendiente de subir | Pendiente de subir | Resultado comentado en Jira |

## Simulador de compras (SCRUM-53 a SCRUM-70)

Todas las historias son de Samuel. Cada una tiene sus criterios de aceptación en Jira.

| Jira | Qué hace | Código | Documento |
|---|---|---|---|
| [SCRUM-54](https://fsandoval09.atlassian.net/browse/SCRUM-54) | Lee el tipo de cambio oficial diario del BCB, guarda la página con su sha256 y valida la serie | [`src/scrum-54`](src/scrum-54) | [`docs/scrum-54`](docs/scrum-54/LEEME.md) |
| [SCRUM-55](https://fsandoval09.atlassian.net/browse/SCRUM-55) | Adapta las ventas reales de carparts a 30 repuestos de MULTIPARTES, con proveedores y stock SINTÉTICOS | [`src/scrum-55`](src/scrum-55) | [`docs/scrum-55`](docs/scrum-55/LEEME.md) |
| [SCRUM-53](https://fsandoval09.atlassian.net/browse/SCRUM-53), [SCRUM-56](https://fsandoval09.atlassian.net/browse/SCRUM-56) a [SCRUM-63](https://fsandoval09.atlassian.net/browse/SCRUM-63) | Motor: costo puesto con Incoterm y flete, dólar a 90 días, venta, atraso del proveedor, riesgo de quedarse sin stock, capital inmovilizado, cuatro alternativas con puntaje, dólar de quiebre y qué supuesto pesa más | [`src/simulador/motor.js`](src/simulador/motor.js) y su referencia [`motor_ref.py`](src/simulador/motor_ref.py) | [`docs/simulador/MOTOR.md`](docs/simulador/MOTOR.md) |
| [SCRUM-64](https://fsandoval09.atlassian.net/browse/SCRUM-64) | La app, con la explicación de cada campo | [`src/simulador`](src/simulador) | [`docs/simulador/LEEME.md`](docs/simulador/LEEME.md) |
| [SCRUM-66](https://fsandoval09.atlassian.net/browse/SCRUM-66) a [SCRUM-70](https://fsandoval09.atlassian.net/browse/SCRUM-70) | Alertas de reposición, comparar proveedores, clasificación de repuestos, ¿qué hubiera pasado? y plan con presupuesto | [`src/simulador`](src/simulador) | [`docs/simulador/LEEME.md`](docs/simulador/LEEME.md) |
| [SCRUM-65](https://fsandoval09.atlassian.net/browse/SCRUM-65) | Guía del simulador y preguntas del docente | — | [`docs/scrum-65/GUIA_simulador.md`](docs/scrum-65/GUIA_simulador.md) |

Para regenerar todo desde los datos:

```bash
python3 src/scrum-54/obtener_tco_bcb.py          # vuelve a leer el BCB (--desde-archivo para trabajar sin red)
python3 src/scrum-55/adaptar_carparts.py
python3 src/simulador/preparar_datos.py
python3 src/simulador/generar_app.py
python3 -m unittest discover -s tests
```

El motor está escrito en JavaScript para que corra dentro de la página, y tiene una copia en Python que solo sirve para
probarlo: las dos versiones deben dar el mismo resultado en 20 casos fijos.

## Estructura

```text
data/
  raw/        datos fuente, organizados por historia de usuario
  processed/  resultados generados, organizados por historia de usuario
docs/         documentación y material de respaldo
reports/      informes y resultados interpretados
src/          scripts de procesamiento y análisis
tests/        pruebas automatizadas
```

Los datos y resultados de cada historia de usuario usan el mismo identificador (`hu-02`, `hu-03`, `hu-06`, `hu-07`, `hu-09`, `hu-17`, `hu-18`, `hu-30-31`, `hu-32`, `hu-33` y `hu-34`) para mantener su trazabilidad. Las historias nuevas usan su clave de Jira (`scrum-54`, `scrum-55`) y el simulador vive en `simulador`.

## Ejecución

Ejecutar desde la raíz del repositorio:

```bash
python src/hu-06/comparar_escenarios.py
python src/hu-07/comparar_pronosticos.py
python src/hu-09/generar_alertas.py
python src/hu-32/obtener_series_tc.py
python src/hu-34/generar_datos.py
python src/hu-34/limpieza_multiparte.py
python src/hu-03/generar_panel.py
python src/hu-30-31/ejecutar_todo.py
python src/hu-02/registro_fuentes.py actualizar --todos
python -m unittest discover -s tests -p "test_*.py" -v
```

## Comparación de escenarios (HU-06)

La configuración está en [`data/raw/hu-06/escenarios.json`](data/raw/hu-06/escenarios.json).
El módulo reutiliza compras de HU-30/31, excluye duplicados identificados por HU-17
y selecciona cambios por serie y fecha exactas de HU-32. Genera la canasta base,
la comparación y el detalle en `data/processed/hu-06/`, además de un
[informe con gráfico SVG](reports/hu-06/REPORTE_HU06.md).

Incluye un base, una alternativa que solo cambia el tipo de cambio, otra que solo
cambia la logística y un combinado. Los cuatro conservan 205 unidades y
2.740,85 USD de mercancía. El peso de 100 kg es un supuesto explícito; el resultado
es simulado y no incluye una liquidación real de tributos. No modifica entradas
ni resultados de otras historias. No es necesario volver a ejecutar sus generadores.

Instrucciones, fórmulas, cambios expresos y limitaciones en
[`docs/hu-06/LEEME.md`](docs/hu-06/LEEME.md). Para ejecutar solo sus pruebas:

```bash
python -m unittest discover -s tests -p "test_comparar_escenarios.py" -v
```

## Alertas de faltantes (HU-09)

Ejecutar `python src/hu-09/generar_alertas.py` reutiliza HU-17, HU-18 y HU-31,
con la configuración de [`data/raw/hu-09/configuracion.json`](data/raw/hu-09/configuracion.json).
Los diez repuestos actuales quedan NO_CALCULABLE: no hay previsión futura
validada ni disponibilidad confirmada. El MAE de HU-07 no se usa como demanda.
No se modifican datos ni resultados de otras historias.

Para demostrar la lógica con datos sintéticos explícitos:

```bash
python src/hu-09/generar_alertas.py --config data/raw/hu-09/demostracion/configuracion.json
```

La demostración genera cuatro ALERTA, tres SIN_ALERTA y tres NO_CALCULABLE,
con resultados separados en las subcarpetas `demostracion/` de datos e informes.
No representa disponibilidad ni previsiones operativas reales de MULTIPARTES.

Consulta el [informe de integración](reports/hu-09/REPORTE_HU09.md),
el [informe de demostración](reports/hu-09/demostracion/REPORTE_HU09.md)
y la [guía de contrato CSV, fórmulas y pruebas](docs/hu-09/LEEME.md).
