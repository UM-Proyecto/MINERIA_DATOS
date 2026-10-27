# Minería de Datos

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

Los datos y resultados de cada historia de usuario usan el mismo identificador (`hu-02`, `hu-03`, `hu-07`, `hu-17`, `hu-18`, `hu-30-31`, `hu-32`, `hu-33` y `hu-34`) para mantener su trazabilidad.

## Ejecución

Ejecutar desde la raíz del repositorio:

```bash
python src/hu-07/comparar_pronosticos.py
python src/hu-32/obtener_series_tc.py
python src/hu-34/generar_datos.py
python src/hu-34/limpieza_multiparte.py
python src/hu-03/generar_panel.py
python src/hu-30-31/ejecutar_todo.py
python src/hu-02/registro_fuentes.py actualizar --todos
python -m unittest discover -s tests -p "test_*.py" -v
```
