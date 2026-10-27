# Borrador de criterios de éxito (SCRUM-44, HU-33)

BORRADOR para llevar al equipo. No está aprobado. La HU pide al menos tres criterios medibles, cada uno con indicador, unidad y fuente, aprobados por el equipo con fecha. Las metas son una propuesta para discutir, y las líneas base salen de los datos FICTICIOS del repositorio al 26 de octubre de 2026, así que se tienen que volver a medir cuando lleguen los datos de MULTIPARTES.

Todos apuntan a la pregunta enfocada: qué técnicas de análisis de datos apoyan las decisiones de compra de MULTIPARTES en el segundo semestre de 2026.

## Criterios propuestos

**1. Pronóstico de salidas mejor que la referencia simple.**
Indicador: error medio absoluto (MAE) del método elegido sobre un periodo reservado, comparado con el método "último periodo".
Unidad: repuestos por día, y porcentaje de mejora sobre la referencia.
Fuente: historial de movimientos (HU-30) y comparación de pronósticos (HU-07).
Meta propuesta: al menos 15 % menos de error que la referencia, con un año de historial y un periodo reservado de 3 meses.
Línea base: hoy no hay método elegible. Los 10 repuestos dan "sin selección fiable" porque HU-07 solo tiene del 1 al 14 de septiembre.

**2. Inventario registrado igual al físico.**
Indicador: porcentaje de repuestos contados cuya diferencia entre stock registrado y conteo físico queda en cero después de la conciliación.
Unidad: porcentaje de repuestos contados.
Fuente: conciliación de inventario (HU-18).
Meta propuesta: 95 % o más.
Línea base: 9 de 13 conteos sin diferencia (69 %); hay 3 faltantes y 1 sobrante.

**3. Costo de importación con respaldo.**
Indicador: porcentaje de los componentes del costo de importación que tienen respaldo documentado (factura, cotización o publicación), frente a los estimados o pendientes.
Unidad: porcentaje de componentes.
Fuente: tabla de costos de importación (HU-31).
Meta propuesta: 80 % o más.
Línea base: 6 de 15 componentes documentados (40 %), 5 estimados y 4 pendientes.

**4. Datos vigentes al momento de decidir.**
Indicador: días entre la fecha hasta la que llegan los datos de movimientos y la fecha en que se usa el análisis para decidir una compra.
Unidad: días.
Fuente: registro de fuentes y fechas (HU-02).
Meta propuesta: 30 días o menos.
Línea base: los movimientos llegan al 14 de septiembre; al 26 de octubre son 42 días.

**5. (Opcional) Tiempo para preparar un pedido.**
Indicador: horas que le lleva al encargado de compras juntar la información para decidir un pedido (costos, stock, tipo de cambio, plazos).
Unidad: horas por pedido.
Fuente: entrevista al jefe de compras de MULTIPARTES, antes y después de usar el análisis.
Meta propuesta: la mitad del tiempo actual.
Línea base: no medida en MULTIPARTES. En las entrevistas de Programa Emprendedor a importadoras de repuestos se mencionaron entre 6 y 10 horas por pedido, pero ese dato no es de MULTIPARTES.

## Para cerrar la HU

Que el equipo elija al menos tres, ajuste las metas, y deje en Jira la lista aprobada con la fecha de aprobación.
