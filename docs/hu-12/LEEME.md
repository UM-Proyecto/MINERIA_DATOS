# HU-12: pantalla de decisión de compra

Esta pantalla responde al pedido del docente para el sprint de la semana 4: elegir un repuesto y ver de tres a cuatro alternativas de compra, cada una con su puntaje y con la herramienta que la respalda. **La decisión la toma quien compra**: la pantalla no elige por él.

Se abre con doble clic en `reports/hu-12/MULTIPARTES_Decision_Compra.html`, en cualquier navegador y sin instalar nada.

## Qué muestra

Se elige un repuesto y aparecen cuatro alternativas, todas con el proveedor de menor costo: **reponer lo justo**, **cubrir 30 días más**, **cubrir 60 días más** y **dividir en dos pedidos**. Cada una indica la cantidad a pedir, el desembolso en bolivianos, el margen de stock que queda después de la entrega y el riesgo de quedarse sin stock.

El puntaje se calculó así: cada alternativa se probó en 1.500 escenarios de 90 días, con ventas, plazos de entrega y dólar distintos en cada uno. El puntaje es en cuántos de cada 100 escenarios esa alternativa dejó más ganancia que las otras tres. Sirve para comparar las alternativas entre sí; no es la probabilidad de acertar.

## Herramientas que la respaldan

1. **Pronóstico de demanda (HU-07):** se comparan tres técnicas con el error medio absoluto (MAE) y las alternativas usan la de menor error.
2. **Compras y proveedores (HU-34, HU-31):** último precio, flete y plazo de entrega de cada proveedor del repuesto.
3. **Tipo de cambio (HU-32):** serie oficial del BCB. La referencia del equipo es 11 Bs por dólar, el punto medio entre el mínimo (9,73) y el máximo (12,64).

## Origen de los datos

Ventas, compras e inventario son datos FICTICIOS de prueba (HU-34). El tipo de cambio es público (BCB). La identidad visual sale de multipartes.com.bo: el logotipo publicado en el sitio, el verde de la marca y la tipografía Poppins. La estructura de la pantalla sigue la del panel de precios de HU-03.

## Cómo se vuelve a generar

Desde la raíz del repositorio:

```bash
python src/hu-12/analisis_tc.py
python src/hu-12/generar_panel.py
```

El primero cruza el tipo de cambio con las compras y ventas, y guarda el resultado en `data/processed/hu-12/analisis_tc.json`. El segundo arma la pantalla con los datos y el logotipo incluidos en el propio archivo. Solo usan la biblioteca estándar de Python.
