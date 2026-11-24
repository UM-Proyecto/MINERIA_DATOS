# Aplicaciones repuesto ↔ vehículo (decisión D9)

`data/processed/scrum-74/aplicaciones.csv` dice a qué vehículos sirve cada uno de los 30 repuestos del catálogo. Con
ella, la tienda y el catálogo del área de la empresa filtran por marca, modelo y año del vehículo.

**Los datos son ilustrativos.** Ninguna fuente del proyecto trae la compatibilidad real: la base carparts solo da un
código numérico por repuesto, y los nombres del catálogo ya son ilustrativos (los asigna `armar_catalogo.py`). Por eso
cada fila lleva `procedencia=ILUSTRATIVO` y las dos pantallas muestran el rótulo «Compatibilidades de demostración
(prototipo académico)». No sirven para decidir una compra real.

Ojo con el campo `marca` de `catalogo.csv` y de `datos_app.json`: indica la procedencia del dato («ILUSTRATIVO» o
«SINTÉTICO / ADAPTADO»), no la marca del vehículo. La marca del vehículo está solo en esta tabla.

## Columnas

| Columna | Qué es |
|---|---|
| `repuesto_id` | Repuesto del catálogo (`REP-0001` a `REP-0030`). |
| `marca` | Marca del vehículo, una de las 10 de `data/raw/tienda/contenido_sitio.json` → `marcas_vehiculos`. |
| `modelo` | Modelo común en Bolivia (Hilux, Corolla, Frontier, D-Max…). |
| `anio_desde`, `anio_hasta` | Años de la generación del modelo, ambos incluidos. |
| `motor` | Cilindrada y combustible, por ejemplo `2.5 diésel`. |
| `procedencia` | Siempre `ILUSTRATIVO`. |

Un repuesto tiene varias filas (entre 3 y 6) y un modelo aparece en varios repuestos: la relación es de muchos a muchos.

## Cómo se genera

```
python3 src/scrum-74/armar_aplicaciones.py
python3 src/simulador/preparar_datos.py && python3 src/simulador/generar_app.py && python3 src/tienda/generar_tienda.py
```

El script parte de una lista fija de 37 combinaciones de modelo, generación y motor de las 10 marcas (la Hilux, la Frontier, el Corolla y
el Swift tienen dos generaciones, para que el filtro por año cambie el resultado), y lee el nombre de cada
repuesto con una regla: «motor 1.6» lleva a los motores a gasolina de 1.6, «diésel 2.5» a los diésel de 2.5, «para
camioneta» a las camionetas, «motor diésel» a todos los diésel, las bujías solo a motores a gasolina, y lo genérico
(pastillas, discos, cubos, amortiguadores, filtros) a autos y SUV. Si la regla deja más de seis vehículos, elige seis
con la semilla fija 20261124, así que la tabla sale idéntica en cada corrida. Antes de escribir, valida años, marcas,
procedencia y que ningún repuesto quede sin aplicación; si algo falla, se detiene.

Los repuestos que se cargan en el portal (tabla D1) no tienen aplicaciones: se muestran con «Compatibilidad no
registrada» y no aparecen cuando hay un filtro de vehículo activo.

Las pruebas están en `tests/test_aplicaciones.py`.
