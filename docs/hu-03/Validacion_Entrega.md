# Validación de la entrega HTML explicada

- Se ejecutó `generar_panel.py` con los CSV incluidos y se produjo el HTML entregado.
- Se volvió a ejecutar el generador desde una carpeta temporal distinta y el HTML resultante coincidió byte por byte con el entregado.
- Los dos CSV incluidos coinciden byte por byte con los archivos utilizados en el notebook anterior.
- Los datos incorporados en el HTML comentado coinciden con los del panel interactivo anterior: 3.600 compras, 19.860 registros de venta, 30 SKU y 199 precios estimados en ventas.
- Se comprobó la sintaxis del Python y del JavaScript comentado. No se detectaron errores.
- Los cambios en el HTML de esta entrega son comentarios explicativos; se conservan los datos y cálculos del panel previamente revisado en el navegador.
- Se actualizó la documentación de referencia cambiaria: se documenta formalmente el paso del tipo de cambio histórico de 7 BOB/USD a la tasa representativa de mercado de 11 BOB/USD en los ejemplos y notas metodológicas, verificando su consistencia con las fuentes y análisis del proyecto.

## Verificaciones funcionales previas del panel

Se comprobaron en el navegador la conversión USD/BOB (contrastando el escenario actualizado de 11 BOB/USD frente al histórico de 7 BOB/USD), la selección de categoría, el cambio a ventas, los avisos de historial insuficiente con una sola fecha, la tabla de detalle, la paginación y la consulta de un punto mediante el teclado. Además, 10 comprobaciones de las funciones JavaScript pasaron y los resultados de los 30 SKU en compras USD coincidieron con el notebook anterior.

No se ejecutó una nueva sesión de navegador por añadir comentarios al mismo código. El HTML es autónomo, sin recursos externos; los datos son ficticios para la práctica académica.
