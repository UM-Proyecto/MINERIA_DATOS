# SCRUM-54: tipo de cambio oficial (TCO) diario del BCB

## Qué hace

El script `src/scrum-54/obtener_tco_bcb.py` lee la página pública del Banco Central de Bolivia
(https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php), donde la tabla «Tipo de cambio oficial, diario»
trae un valor por día desde el 27 de junio de 2026. Con esa tabla reescribe el archivo
`data/processed/scrum-54/tco_bcb_diario.csv`, que alimenta el análisis del tipo de cambio y el simulador.

Usa solo la biblioteca estándar de Python (3.8 o superior).

## Cómo se usa

```
python3 src/scrum-54/obtener_tco_bcb.py                      # descarga la página de hoy
python3 src/scrum-54/obtener_tco_bcb.py --desde-archivo RUTA   # sin red, desde una captura guardada
python3 src/scrum-54/obtener_tco_bcb.py --inseguro            # solo si falla el certificado SSL
```

Para repetir el resultado sin internet use la captura incluida:
`--desde-archivo data/raw/scrum-54/tco_bcb_2026-11-10.html` (137 filas, hasta el 10-11-2026).

## Qué guarda

- **Captura cruda**: `data/raw/scrum-54/tco_bcb_AAAA-MM-DD.html`, con la fecha de la descarga en el nombre.
  Su huella sha256 queda en `data/raw/scrum-54/SHA256SUMS.txt`, para comprobar que el archivo no cambió.
- **CSV limpio**: columnas `fecha`, `tco_bs_por_usd`, `fuente` y `fecha_lectura` (el día en que se leyó la
  página). Si un día ya estaba en el CSV con el mismo valor, se conserva su `fecha_lectura` original.

## Cómo funciona

1. Quita de la página los bloques `<style>` y `<script>`, y luego las etiquetas HTML, para quedarse con el texto.
2. Lee el encabezado (la última cotización y la fecha de VIGENCIA).
3. Lee cada fila de la tabla: una fecha escrita en español («sábado 27 de junio de 2026») y su valor («9,73»).
4. Valida y, solo si todo está bien, escribe el CSV.

## Cuándo se detiene

El script termina con un mensaje de error, sin tocar el CSV, en estos casos:

- Faltan días entre la primera y la última fecha de la tabla (el mensaje dice cuáles).
- Un valor queda fuera del rango de 5 a 20 Bs por dólar (por ejemplo, un 115,0 por error de tipeo).
- La fecha de vigencia del encabezado no coincide con la última fila de la tabla, o el valor de la
  «última cotización» del encabezado difiere del de esa fila.
- No se encuentra el encabezado o la tabla, es decir, el BCB cambió el formato de la página.

## Aviso sobre `--inseguro`

La opción `--inseguro` desactiva la verificación del certificado SSL. Úsela únicamente si la descarga normal
falla por el certificado y entiende el riesgo: sin verificación, otra persona podría suplantar el sitio. Por eso
no es el comportamiento por defecto y el script lo avisa cada vez que se usa. En la corrida del 12-11-2026 no
fue necesaria.

## Pruebas

```
python3 -m unittest tests.test_scrum54_tco
```

Las pruebas no usan la red. Con la captura del 10-11-2026 comprueban que se obtienen exactamente las 137
filas del CSV, y con capturas alteradas en memoria (un día borrado, un valor 115,0, una vigencia distinta)
comprueban que el script se detiene.
