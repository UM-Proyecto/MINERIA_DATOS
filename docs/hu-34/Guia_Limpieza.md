# Guía de ejecución y explicación

Desde la raíz del repositorio, ejecuta `python src/hu-34/limpieza_multiparte.py`. El script lee los CSV de `data/raw/hu-34/`, guarda los resultados en `data/processed/hu-34/` y escribe el informe en `reports/hu-34/`. El notebook está en `notebooks/hu-34/`. En Databricks, importa el notebook y modifica BASE y SALIDA a rutas de volumen autorizadas.

## 1. Carga de los datos

Cambia BASE si guardaste los CSV en otra carpeta. En Databricks utiliza una ruta de volumen a la que tengas acceso. Pandas maneja las tablas, NumPy verifica números y Path organiza los archivos. originales guarda una copia previa para documentar cambios.

## 2. Normalización y revisión

Se quitan espacios, se detectan duplicados exactos y se convierten fechas y cantidades. Los identificadores se escriben en mayúsculas. Las claves fecha + sku e id_compra no pueden estar vacías ni repetidas. El proceso se detiene ante un conflicto, en lugar de borrar información arbitrariamente.

## 3. Precios e ingresos

groupby separa los repuestos y ffill arrastra el último precio conocido hacia adelante en el tiempo. No toma precios de otro producto ni de una fecha futura. Si falta un precio al inicio de la serie, el código se detiene para pedir otra regla. Se recalculan los ingresos afectados como unidades por precio, con dos decimales. precio_estimado e ingreso_recalculado marcan las intervenciones.

## 4. Fletes, proveedores y almacén

Se calcula el flete por unidad de las compras con flete conocido y se obtiene su mediana global. Ese valor se multiplica por las unidades de cada compra con flete ausente. La mediana reduce la influencia de importes extremos. NO_INFORMADO etiqueta proveedores desconocidos sin inventar su identidad. Central se asigna solo porque esta simulación documenta un único almacén. Cada cambio tiene un indicador.

## 5. Validaciones

verificar cuenta incidencias y detiene el proceso si encuentra alguna. Comprueba nulos, claves, valores negativos, períodos, balance y continuidad del stock. Las compras se agregan por fecha de recepción y sku antes de unirlas al inventario. Se verifican unidades e importes con tolerancia de redondeo. Los 662 días y las 100 unidades iniciales son supuestos específicos de estos archivos.

## 6. Exportación e informe

Se guardan los tres CSV limpios, se vuelven a leer y se comprueban filas y nulos. El informe detalla faltantes por columna, cambios, porcentajes y resultados. Los CSV no conservan tipos nativos; hay que asignarlos al importar. Los valores completados son estimaciones académicas. Si el flete se usa en un modelo con separación temporal, la mediana debe calcularse solo con los datos de entrenamiento.
