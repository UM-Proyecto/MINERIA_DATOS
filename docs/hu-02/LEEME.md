# SCRUM-12 (HU-02): fuente y fecha de actualización de los datos

La HU-02 lleva un registro de cada conjunto de datos del repositorio: de dónde viene, quién lo arma, si es FICTICIO o público, cuándo se cargó bien por última vez y hasta qué fecha llegan sus datos. Si una carga falla, el registro conserva la última fecha válida y deja anotado el fallo.

## Cómo correrlo

Hace falta Python 3.8 o superior y ninguna librería externa. Desde la raíz del repositorio:

    python src/hu-02/registro_fuentes.py consultar             # muestra la tabla
    python src/hu-02/registro_fuentes.py actualizar --todos    # vuelve a cargar todos los conjuntos
    python src/hu-02/registro_fuentes.py actualizar stock_inicial conteos_fisicos
    cd src/hu-02 && python -m unittest test_registro_fuentes   # pruebas de los tres criterios

`actualizar` sale con código 1 si alguna carga falló, así otro script puede enterarse.

## Dónde está cada cosa

- `src/hu-02/registro_fuentes.py` y `src/hu-02/test_registro_fuentes.py`: el script y sus pruebas.
- `data/raw/hu-02/conjuntos.csv`: la lista de conjuntos. Por cada uno, el archivo (ruta desde la raíz del repositorio), la fuente, el tipo de dato, la responsable, las columnas que tiene que traer y la columna de fecha. Para sumar un conjunto nuevo basta con agregar un renglón.
- `data/processed/hu-02/registro_actualizaciones.csv`: el estado actual. Un renglón por conjunto con su última actualización válida, la fecha hasta la que llegan sus datos, cuántos registros tiene y cómo terminó el último intento.
- `data/processed/hu-02/historial_cargas.csv`: cada intento, bueno o malo, con su fecha.
- `reports/hu-02/REPORTE_HU02.md`: la prueba de los tres criterios con un fallo provocado.

## Cuándo una carga se toma como fallida

Si el archivo no está, no se puede leer como texto, le falta alguna columna de las pedidas, no tiene registros o trae una fecha mal escrita. Una celda de fecha vacía no es fallo, porque en los costos PENDIENTE todavía no hay dato, y un rango como `2025-09 a 2026-08` cuenta por su final.

## Lo que no hace

No copia ni modifica los archivos de las otras historias: solo los lee. Tampoco decide si el contenido es correcto (eso lo revisan HU-17, HU-18 y HU-30); solo verifica que el archivo sirva para cargarse. Mientras no lleguen los datos reales de MULTIPARTES, casi todos los conjuntos son FICTICIOS y así figuran en la tabla.

## Cambios del 27/10/2026

Con la reorganización del repositorio por historia de usuario, las rutas de `conjuntos.csv` pasaron a `data/raw/` y `data/processed/`. Se sumaron cuatro conjuntos nuevos: las series de tipo de cambio de la HU-32 y las ventas, compras e inventario simulados de la HU-34. Son 17 en total, y los 17 cargaron bien el 27/10/2026. El historial conserva los intentos anteriores con sus rutas viejas.
