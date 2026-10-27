# Databricks notebook source
# MAGIC %md
# MAGIC # Limpieza completa de MULTIPARTE
# MAGIC Datos ficticios. Ejecutar desde la carpeta del paquete o ajustar BASE.
# MAGIC Los valores estimados quedan identificados; no son datos reales recuperados.

# COMMAND ----------
# 1. Cargar los tres CSV. Las copias originales permiten comparar antes y después.
from pathlib import Path
import pandas as pd
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / 'data' / 'raw' / 'hu-34'  # En Databricks, cambia por tu ruta /Volumes/...
SALIDA = RAIZ / 'data' / 'processed' / 'hu-34'
SALIDA.mkdir(exist_ok=True)
datos = {n: pd.read_csv(BASE / f'{n}_simuladas.csv')
         for n in ['ventas', 'compras', 'inventario']}
originales = {n: d.copy(deep=True) for n, d in datos.items()}
duplicados = {}

# COMMAND ----------
# 2. Normalizar texto, fechas, cantidades y claves. No borrar compras distintas.
for nombre, tabla in datos.items():
    for col in tabla.select_dtypes('object'):
        tabla[col] = tabla[col].astype('string').str.strip().replace('', pd.NA)
    duplicados[nombre] = int(tabla.duplicated().sum())
    tabla.drop_duplicates(inplace=True)
    for col in [c for c in tabla if c.startswith('fecha')]:
        tabla[col] = pd.to_datetime(tabla[col], format='%Y-%m-%d', errors='raise')
    for col in ['sku', 'id_compra', 'proveedor']:
        if col in tabla:
            tabla[col] = tabla[col].str.upper()
    for col in ['unidades_vendidas', 'cantidad', 'stock_inicial', 'entradas', 'salidas', 'stock_final']:
        if col in tabla:
            valores = pd.to_numeric(tabla[col], errors='raise')
            if valores.isna().any() or (valores % 1 != 0).any():
                raise ValueError(f'Cantidad inválida: {nombre}.{col}')
            tabla[col] = valores.astype('int64')
    claves = ['id_compra'] if nombre == 'compras' else ['fecha', 'sku']
    if tabla[claves].isna().any().any() or tabla.duplicated(claves).any():
        raise ValueError(f'Claves faltantes o repetidas en {nombre}')

ventas, compras, inventario = [datos[n] for n in ['ventas', 'compras', 'inventario']]
ventas.sort_values(['sku', 'fecha'], inplace=True)
compras.sort_values(['fecha_pedido', 'id_compra'], inplace=True)
inventario.sort_values(['sku', 'fecha'], inplace=True)

# COMMAND ----------
# 3. Completar precios e ingresos. ffill usa solamente un precio anterior del SKU.
# Si no hay precio anterior, se detiene para no usar información futura.
ventas['precio_estimado'] = ventas.precio_unitario_bs.isna()
ventas['ingreso_recalculado'] = ventas.ingreso_bs.isna() | ventas.precio_estimado
ventas['precio_unitario_bs'] = ventas.groupby('sku').precio_unitario_bs.ffill()
if ventas.precio_unitario_bs.isna().any():
    raise ValueError('Hay SKU sin precio anterior: se requiere otra regla explícita.')
mascara = ventas.ingreso_recalculado
ventas.loc[mascara, 'ingreso_bs'] = (
    ventas.loc[mascara, 'unidades_vendidas'] * ventas.loc[mascara, 'precio_unitario_bs']
).round(2)

# COMMAND ----------
# 4. Completar proveedores, fletes y almacén según reglas de la simulación.
# NO_INFORMADO es una categoría de información desconocida, no una identidad recuperada.
compras['proveedor_no_informado'] = compras.proveedor.isna()
compras['proveedor'] = compras.proveedor.fillna('NO_INFORMADO')
compras['flete_estimado'] = compras.flete_bs.isna()
validos = compras.flete_bs.notna() & compras.cantidad.gt(0)
flete_por_unidad = (compras.loc[validos, 'flete_bs'] / compras.loc[validos, 'cantidad']).median()
if not np.isfinite(flete_por_unidad):
    raise ValueError('No hay compras completas suficientes para estimar el flete.')
mascara = compras.flete_estimado
compras.loc[mascara, 'flete_bs'] = (
    compras.loc[mascara, 'cantidad'] * flete_por_unidad
).round(2)
inventario['almacen_completado'] = inventario.almacen.isna()
inventario['almacen'] = inventario.almacen.fillna('Central')
# Central es válido aquí porque el diseño ficticio tiene un único almacén.

# COMMAND ----------
# 5. Verificar que no queden nulos y comprobar relaciones entre fuentes.
# Si un control detecta un problema, se detiene antes de exportar.
controles = []
def verificar(control, errores):
    cantidad = int(np.asarray(errores).sum())
    controles.append((control, cantidad))
    if cantidad:
        raise ValueError(f'{control}: {cantidad} incidencias')

for nombre, tabla in datos.items():
    verificar(f'{nombre}: celdas vacías', tabla.isna().to_numpy())
    numericos = tabla.select_dtypes(include='number')
    verificar(f'{nombre}: números negativos', numericos.lt(0).to_numpy())
    verificar(f'{nombre}: números no finitos', (~np.isfinite(numericos)).to_numpy())
    claves = ['id_compra'] if nombre == 'compras' else ['fecha', 'sku']
    verificar(f'{nombre}: claves repetidas', tabla.duplicated(claves))
    for col in [c for c in tabla if c.startswith('fecha')]:
        verificar(f'{nombre}: período de {col}', tabla[col].lt('2025-01-01') | tabla[col].gt('2026-10-24'))
verificar('Recepción anterior al pedido', compras.fecha_recepcion.lt(compras.fecha_pedido))
verificar('Balance de inventario', inventario.stock_final.ne(inventario.stock_inicial + inventario.entradas - inventario.salidas))
anterior = inventario.groupby('sku').stock_final.shift()
verificar('Continuidad diaria del stock', anterior.notna() & inventario.stock_inicial.ne(anterior))
verificar('Stock inicial de apertura', inventario.groupby('sku').head(1).stock_inicial.ne(100))
for nombre, tabla in [('ventas', ventas), ('inventario', inventario)]:
    verificar(f'{nombre}: 662 fechas por SKU', tabla.groupby('sku').fecha.nunique().ne(662))
union = inventario.merge(ventas[['fecha', 'sku', 'unidades_vendidas']], on=['fecha', 'sku'], how='outer', indicator=True, validate='one_to_one')
verificar('Claves de ventas e inventario', union['_merge'].ne('both'))
verificar('Ventas iguales a salidas', union.salidas.ne(union.unidades_vendidas))
recepciones = compras.groupby(['fecha_recepcion', 'sku'], as_index=False).cantidad.sum().rename(columns={'fecha_recepcion': 'fecha'})
union = inventario.merge(recepciones, on=['fecha', 'sku'], how='outer', indicator=True, validate='one_to_one')
verificar('Recepciones sin inventario', union['_merge'].eq('right_only'))
# Aquí cero significa que no hubo una recepción para esa fecha y SKU.
verificar('Entradas iguales a recepciones', union.entradas.ne(union.cantidad.fillna(0)))
verificar('Ingreso igual a unidades por precio', (ventas.ingreso_bs - ventas.unidades_vendidas * ventas.precio_unitario_bs).abs().gt(0.011))
verificar('Subtotal de compras', (compras.subtotal_bs - compras.cantidad * compras.costo_unitario_usd * compras.tipo_cambio_bs_usd).abs().gt(0.011))
verificar('SKU de compras existentes', ~compras.sku.isin(ventas.sku.unique()))

# COMMAND ----------
# 6. Exportar, releer y documentar las transformaciones.
nombres = {'ventas': 'ventas_limpias.csv', 'compras': 'compras_limpias.csv', 'inventario': 'inventario_limpio.csv'}
for nombre, tabla in datos.items():
    orden = ['fecha_pedido', 'id_compra'] if nombre == 'compras' else ['fecha', 'sku']
    tabla.sort_values(orden, inplace=True)
    tabla.to_csv(SALIDA / nombres[nombre], index=False, encoding='utf-8-sig', date_format='%Y-%m-%d')
    lectura = pd.read_csv(SALIDA / nombres[nombre])
    verificar(f'{nombre}: nulos en CSV exportado', lectura.isna().to_numpy())
    verificar(f'{nombre}: filas conservadas al exportar', [len(lectura) != len(tabla)])

lineas = ['# Limpieza completa de datos de MULTIPARTE', '',
    'Datos ficticios para fines académicos. Los valores completados son estimaciones y no información real recuperada de la empresa.', '',
    '## Tamaño y faltantes antes y después', '',
    '| Fuente | Filas antes | Filas después | Columnas antes | Columnas después | Celdas vacías antes | Celdas vacías después | Duplicados eliminados |',
    '|---|---:|---:|---:|---:|---:|---:|---:|']
for nombre, tabla in datos.items():
    ori = originales[nombre]
    lineas.append(f'| {nombre} | {len(ori)} | {len(tabla)} | {len(ori.columns)} | {len(tabla.columns)} | {int(ori.isna().sum().sum())} | {int(tabla.isna().sum().sum())} | {duplicados[nombre]} |')
lineas += ['', 'No se eliminaron filas: no se encontraron duplicados ni conflictos de claves. Se conservaron 43.320 registros. Los ceros de unidades vendidas son válidos y se mantienen.', '',
    '## Reglas aplicadas y trazabilidad', '',
    f'- Precios: {int(ventas.precio_estimado.sum())} valores completados con el último precio anterior disponible del mismo SKU. Si hay varios días vacíos consecutivos, se arrastra el último precio conocido. Campo precio_estimado.',
    f'- Ingresos: {int(ventas.ingreso_recalculado.sum())} valores calculados como unidades vendidas por precio completado, redondeados a dos decimales. Campo ingreso_recalculado.',
    f'- Fletes: {int(compras.flete_estimado.sum())} valores estimados con la mediana global del flete por unidad de las compras originalmente completas: {flete_por_unidad:.8f} Bs/unidad. Se multiplica por las unidades de cada compra y se redondea a dos decimales. Campo flete_estimado.',
    f'- Proveedores: {int(compras.proveedor_no_informado.sum())} etiquetas NO_INFORMADO. La identidad sigue desconocida; no se inventaron proveedores. Campo proveedor_no_informado.',
    f'- Almacén: {int(inventario.almacen_completado.sum())} valores completados como Central por el supuesto documentado de un único almacén ficticio. Campo almacen_completado.',
    '- Se normalizaron textos y se validaron fechas, enteros, claves, cantidades y relaciones. No se detectaron formatos incorrectos que requirieran corrección en estos CSV.', '',
    '## Faltantes por columna original', '',
    '| Fuente | Columna | Faltantes antes | Porcentaje antes | Faltantes después | Porcentaje después |',
    '|---|---|---:|---:|---:|---:|']
for nombre, tabla in datos.items():
    for col in originales[nombre]:
        a = int(originales[nombre][col].isna().sum()); b = int(tabla[col].isna().sum())
        lineas.append(f'| {nombre} | {col} | {a} | {a/len(originales[nombre])*100:.2f}% | {b} | {b/len(tabla)*100:.2f}% |')
lineas += ['', 'Los indicadores nuevos son booleanos True/False sin valores vacíos. True identifica una intervención o una identidad desconocida. El porcentaje se calcula como celdas vacías de la columna dividido entre filas del conjunto, por 100.', '',
    '## Tipos de datos y períodos', '',
    'Fechas en formato AAAA-MM-DD; códigos y categorías como texto; cantidades y stocks como enteros; precios, ingresos, flete, costo y tipo de cambio como decimales. CSV no almacena tipos nativos: deben asignarse al importar.', '',
    '| Fuente | Columna de fecha | Desde | Hasta |', '|---|---|---|---|']
for nombre, tabla in datos.items():
    for col in [c for c in tabla if c.startswith('fecha')]:
        lineas.append(f'| {nombre} | {col} | {tabla[col].min():%Y-%m-%d} | {tabla[col].max():%Y-%m-%d} |')
lineas += ['', '## Controles ejecutados', '', '| Control | Incidencias |', '|---|---:|']
lineas += [f'| {control} | {cantidad} |' for control, cantidad in controles]
lineas += ['', f'Se ejecutaron {len(controles)} controles sin incidencias. Se comprobaron balance, continuidad de stock, correspondencia entre ventas y salidas y entre compras recibidas y entradas. Los importes se compararon con tolerancia de 0,011 Bs por redondeo.', '',
    '## Interpretación y límites', '',
    'Los tres CSV finales no tienen celdas vacías. La ausencia de nulos no convierte los valores estimados en observaciones conocidas. NO_INFORMADO debe permanecer separado en cualquier análisis por proveedor. Los resultados monetarios incluyen estimaciones y deben presentarse como tales.', '',
    'La mediana global de fletes utiliza todas las compras completas del período, por lo que esta regla se aplica a la limpieza descriptiva de esta simulación. Si se utiliza el flete en un modelo con evaluación temporal, la mediana debe estimarse únicamente con el conjunto de entrenamiento. El relleno de precios usa valores anteriores del mismo repuesto.', '',
    'El stock de apertura de 100 unidades y los 662 días son reglas específicas de estos archivos. Las ventas pueden subestimar la demanda si no hay existencias. El subtotal de compras excluye flete y tributos: sumar flete proporciona un costo parcial, no el costo total de importación.', '',
    '## Comentario para la subtarea', '',
    'Se limpiaron y completaron los datos ficticios de ventas, compras e inventario de MULTIPARTE, conservando los 43.320 registros. No se encontraron duplicados ni se eliminaron filas. Se completaron los precios con valores anteriores del mismo repuesto, se recalcularon sus ingresos y se estimaron los fletes con el costo mediano por unidad. También se identificaron los proveedores desconocidos y se completó el almacén según la simulación. Los archivos finales no presentan celdas vacías y los valores estimados quedaron marcados para distinguirlos de los datos originales.']
(RAIZ / 'reports' / 'hu-34' / 'Informe_Limpieza_MULTIPARTE.md').write_text('\n'.join(lineas), encoding='utf-8')
print('Registros conservados:', sum(len(d) for d in datos.values()))
print('Celdas vacías finales:', sum(int(d.isna().sum().sum()) for d in datos.values()))
print('Controles:', len(controles), '| Incidencias:', sum(n for _, n in controles))
print('Mediana del flete por unidad:', flete_por_unidad)
