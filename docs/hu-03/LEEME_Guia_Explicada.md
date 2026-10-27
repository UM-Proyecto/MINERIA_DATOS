# HU-03 · Evolución de precios de MULTIPARTE

## Archivos incluidos

| Archivo | Para qué sirve |
|---|---|
| `reports/hu-03/MULTIPARTE_Precios_Interactivo.html` | Panel completo y funcional. Su código incluye comentarios por secciones. |
| `src/hu-03/generar_panel.py` | Código explicado que lee los CSV e incorpora sus datos en el HTML. No genera datos nuevos. |
| `src/hu-03/plantilla_panel.html` | Diseño HTML, estilos CSS y lógica JavaScript comentados. Contiene una marca que Python reemplaza por los datos. |
| `data/processed/hu-34/compras_limpias.csv` | Los mismos 3.600 pedidos de la entrega final de limpieza. |
| `data/processed/hu-34/ventas_limpias.csv` | Los mismos 19.860 registros diarios de venta de la entrega final de limpieza. |
| `docs/hu-03/Validacion_Entrega.md` | Comprobaciones realizadas sobre esta entrega. |

**Los datos son ficticios para fines académicos.** Se reutilizaron los archivos finales sin modificar sus valores. El inventario no interviene en esta historia porque se analiza el historial de precios.

## Qué hace cada tecnología

**HTML** organiza la pantalla: título, filtros, tarjetas, gráfico, tabla y ayuda.

**CSS** determina colores, tamaños, espacios y distribución. Las reglas `@media` adaptan la pantalla al celular y a la impresión.

**JavaScript** realiza la interacción: filtra, convierte monedas, calcula resúmenes, dibuja el gráfico y exporta la selección. Es el código que se ejecuta mientras utilizas el panel.

**Python** prepara el archivo autónomo: lee los CSV, comprueba sus campos, crea un catálogo de categorías y coloca los datos dentro de la plantilla. No controla los botones cuando abres el panel.

## Explicación de generar_panel.py

### 1. Ubicar las carpetas

`BASE` utiliza la ubicación del propio script. A partir de ella localiza los CSV en `data/processed/hu-34/` y la plantilla en `src/hu-03/plantilla_panel.html`. No depende de una ruta fija como `C:\Usuarios\...`.

### 2. Leer los datos limpios

`leer_csv()` carga los registros y comprueba que existan las columnas requeridas. No elimina filas ni realiza otra limpieza. `positivo()` valida números positivos y finitos; `booleano()` interpreta correctamente los textos True y False del CSV.

### 3. Obtener la categoría de cada repuesto

El catálogo relaciona cada `sku` con su `categoria` utilizando ventas. Permite clasificar las compras, cuyo CSV no tiene categoría. Se comprueba que un mismo SKU no esté asociado a categorías contradictorias y que todo SKU comprado exista en el catálogo.

### 4. Seleccionar los campos utilizados

Se mantienen todos los registros, pero se incorporan al HTML los campos necesarios para esta historia:

| Fuente | Orden de los valores en cada fila compacta del JSON |
|---|---|
| Compras | fecha de pedido, SKU, costo unitario USD, tipo de cambio BOB/USD, cantidad, ID del pedido, proveedor |
| Ventas | fecha, SKU, precio unitario BOB, indicador de precio estimado, unidades vendidas |

Los archivos CSV completos también se conservan en `data/processed/hu-34/`. El formato compacto reduce el tamaño del HTML; el catálogo se almacena una sola vez.

### 5. Incorporar la información

`json.dumps()` convierte la estructura en texto JSON. La plantilla tiene una única marca `__DATA__`, que se reemplaza por este contenido. El bloque `script` de tipo `application/json` almacena datos; JavaScript los lee con `JSON.parse()`.

### 6. Guardar el panel

El resultado se guarda como `reports/hu-03/MULTIPARTE_Precios_Interactivo.html`. Al volver a ejecutar Python se reemplaza ese HTML con la plantilla y los CSV procesados.

Para reconstruirlo desde la raíz del repositorio, ejecuta:

```bash
python src/hu-03/generar_panel.py
```

En Windows también puedes usar `py generar_panel.py`; en otros sistemas, `python3 generar_panel.py`. El script solo utiliza la biblioteca estándar de Python y no requiere paquetes adicionales. No necesitas ejecutarlo para abrir el panel ya entregado.

## Explicación del HTML y JavaScript

El HTML y la plantilla incluyen comentarios numerados del 1 al 25, centrados en las partes importantes.

| Parte | Función principal | Qué hace y por qué |
|---|---|---|
| Estructura y estilos | HTML y CSS | Organizan el panel y lo adaptan a diferentes pantallas. |
| Preparación | `prepare()` | Selecciona la fuente, identifica fecha y precio y aplica la conversión cuando corresponde. |
| Selección | `filterRows()` | Combina categoría, repuesto y rango de fechas, incluyendo ambos extremos. |
| Serie diaria | `daily()` | Calcula el precio por SKU y fecha sin mezclar repuestos distintos. |
| Resumen | `summaries()` | Calcula precios inicial y final, variación, cobertura y avisos por SKU. |
| Repuestos disponibles | `skuOptions()` | Muestra solo los repuestos de la categoría elegida. Si el anterior ya no corresponde, selecciona Todos. |
| Cambio de historial | `switchSource()` | Ajusta las fechas al período disponible de la fuente y restringe la moneda de ventas a BOB. |
| Actualización | `render()` | Coordina filtros, avisos, tarjetas, gráfico y tabla. |
| Visualización | `drawChart()` | Dibuja líneas y puntos con SVG, una línea por SKU y cruces para precios estimados. |
| Consulta de puntos | `tooltip()` | Muestra SKU, fecha, precio, moneda y marca de estimación del punto consultado. |
| Tabla | `tableData()` y `renderTable()` | Preparan resumen o detalle y muestran 25 filas por página. |
| Botones y exportación | Eventos `onclick` y `change` | Actualizan el panel, cambian páginas, restablecen filtros o descargan toda la selección. |

**Los filtros funcionan al instante:** cada cambio llama a `render()`, que trabaja sobre los datos ya incorporados en el archivo. No se consulta un servidor ni se cargan archivos externos.

**Las fechas rápidas** de 30 o 90 días terminan en la última fecha disponible de la fuente seleccionada, no en la fecha actual del equipo. El indicador “Disponible” muestra el período completo de esa fuente.

**Al visualizar varios SKU**, las tarjetas de precio inicial, final y variación muestran un guion y remiten al resumen por repuesto. Así se evita resumir productos de precios diferentes en un único valor engañoso.

## Cálculos utilizados

### Conversión de compras a bolivianos

```text
Costo unitario BOB = costo unitario USD × tipo de cambio BOB/USD de cada pedido
```

El tipo de cambio es simulado y se toma de cada fila. Primero se convierte cada pedido y después se agrupa. No se utiliza una tasa actual ni una tasa única para todo el período. Se excluyen flete y tributos: no representa el costo total de importación.

Ventas solo se muestra en BOB porque no contiene un tipo de cambio propio para convertirla a USD.

### Varias compras del mismo repuesto en un día

```text
Precio diario = suma(precio unitario × cantidad) / suma(cantidad)
```

Ejemplo ilustrativo, que no añade registros a los datos: si se comprara una unidad a 10 y tres unidades a 20, el promedio ponderado sería `(10 × 1 + 20 × 3) / 4 = 17,50`. La tabla detallada conserva cada pedido para comprobarlo.

### Variación del precio

```text
Variación % = (último precio diario / primer precio diario − 1) × 100
```

Se calcula por SKU y dentro de las fechas elegidas. No compara directamente compras con ventas.

Para RP001 en Compras y USD, con todo el historial, el panel muestra 121 pedidos en 112 fechas distintas. El precio diario pasa de **42,50 USD**, el **02/01/2025**, a **35,29 USD**, el **19/09/2026**: una variación de **−16,96 %**. Esto describe los extremos del período; no implica que el precio haya bajado todos los días ni que seguirá bajando.

## Faltantes completados e historial insuficiente

Los CSV finales no contienen celdas vacías, pero conservan marcas de los valores estimados durante la limpieza. En ventas hay **199 precios estimados**: el panel los señala con cruces y los cuenta por SKU. Si el precio inicial o final es estimado, la comparación también se identifica como estimada. Los proveedores NO_INFORMADO conservan esa etiqueta.

| Información disponible por SKU en el filtro | Aviso |
|---|---|
| Ningún registro | No hay historial; ampliar fechas o cambiar filtros. |
| Menos de 2 fechas con precios no imputados | Historial insuficiente; la variación no se calcula. |
| Al menos 2 fechas, pero menos de 5 o menos de 30 días de cobertura | Historial limitado. |
| Al menos 5 fechas y al menos 30 días | Comparación descriptiva disponible. |

Son reglas operativas del panel, no mínimos estadísticos universales ni una validación para pronosticar. Los precios completados no se cuentan como nuevas fechas observadas para determinar suficiencia. Las líneas unen fechas registradas; no se crean precios intermedios. Las ventas con cero unidades conservan el precio registrado, aunque no sean transacciones.

## Cumplimiento de HU-03

| Criterio | Cómo se cumple |
|---|---|
| Seleccionar repuesto, categoría y fechas | Controles visibles con actualización automática y selección de SKU dependiente de categoría. |
| Mostrar precios, fecha y moneda o conversión identificada | Gráfico, consulta de puntos, tarjetas y tabla; moneda USD/BOB y explicación de la tasa por pedido. |
| Informar historial insuficiente | Avisos por SKU, estado vacío y variación no calculable cuando faltan fechas observadas. |

## Comentario para presentar el trabajo

Se desarrolló un panel HTML interactivo para visualizar los precios ficticios de MULTIPARTE, utilizando los mismos datos finales de compras y ventas. Permite filtrar por repuesto, categoría y fechas, identificar la moneda y consultar las variaciones. También señala los precios estimados e informa cuando el historial disponible es insuficiente para comparar.
