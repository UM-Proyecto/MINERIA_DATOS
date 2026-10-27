# HU-02: fuente y fecha de actualización de los datos

Registro de cada conjunto de datos del repositorio: de dónde viene, quién lo arma, si es FICTICIO, PÚBLICO o MIXTO, cuándo se cargó bien por última vez y hasta qué fecha llegan sus datos. Si una carga falla, el registro conserva la última fecha válida y deja anotado el motivo.

## Cómo correrlo

Python 3.8 o superior, sin librerías externas. Desde la raíz del repositorio:

    python src/hu-02/registro_fuentes.py consultar              # muestra la tabla
    python src/hu-02/registro_fuentes.py actualizar --todos     # vuelve a cargar todos los conjuntos
    python src/hu-02/registro_fuentes.py actualizar stock_inicial conteos_fisicos
    python -m unittest tests.test_registro_fuentes -v           # pruebas de los tres criterios

`actualizar` sale con código 1 si alguna carga falló, así otro script puede enterarse.

## Archivos

| Archivo | Qué es |
|---|---|
| `src/hu-02/registro_fuentes.py` | El script |
| `tests/test_registro_fuentes.py` | Las 8 pruebas |
| `data/raw/hu-02/conjuntos.csv` | La lista de conjuntos: archivo, fuente, tipo de dato, responsable, columnas obligatorias y columna de fecha. Para sumar un conjunto basta con agregar un renglón |
| `data/processed/hu-02/registro_actualizaciones.csv` | El estado actual, un renglón por conjunto |
| `data/processed/hu-02/historial_cargas.csv` | Cada intento de carga, bueno o malo |
| `reports/hu-02/REPORTE_HU02.md` | La prueba de los tres criterios, con un fallo provocado |

## Cuándo una carga se toma como fallida

Si el archivo no está, no se puede leer como texto, le falta alguna columna obligatoria, no tiene registros o trae una fecha mal escrita. Una celda de fecha vacía no es fallo, porque en los costos PENDIENTE todavía no hay dato, y un rango como `2025-09 a 2026-08` cuenta por su fecha final.
