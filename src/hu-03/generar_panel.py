"""HU-03 · MULTIPARTE: reconstruir el HTML con los CSV finales de limpieza.

Uso: python generar_panel.py
Solo utiliza la biblioteca estándar de Python. El panel ya está generado;
este archivo permite comprender y reproducir cómo se incorporaron los datos.
Los filtros y los gráficos se ejecutan en JavaScript dentro del navegador.
"""
from pathlib import Path
import csv
import json
from datetime import date

# 1. Ubicar archivos respecto a este script, independientemente de la carpeta
# desde la que se ejecute. No necesitas editar rutas de tu computadora.
BASE = Path(__file__).resolve().parent
RAIZ = BASE.parents[1]
DATOS = RAIZ / 'data' / 'processed' / 'hu-34'
PLANTILLA = BASE / 'plantilla_panel.html'
SALIDA = RAIZ / 'reports' / 'hu-03' / 'MULTIPARTE_Precios_Interactivo.html'


def leer_csv(nombre, requeridas):
    """Lee encabezados y filas; informa si faltan columnas necesarias."""
    with (DATOS / nombre).open(encoding='utf-8-sig', newline='') as archivo:
        lector = csv.DictReader(archivo)
        faltantes = set(requeridas) - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError(f'{nombre}: faltan columnas {sorted(faltantes)}')
        return list(lector)


def positivo(valor):
    """Los precios, las cantidades compradas y las tasas deben ser positivos."""
    import math
    numero = float(valor)
    if not math.isfinite(numero) or numero <= 0:
        raise ValueError(f'Número positivo y finito esperado: {valor!r}')
    return numero


def booleano(valor):
    """Convierte True/False del CSV sin confundir el texto False con verdadero."""
    valor = valor.strip().lower()
    if valor not in ('true', 'false'):
        raise ValueError(f'Indicador booleano inválido: {valor!r}')
    return valor == 'true'


def crear_panel():
    # 2. Reutilizar los archivos limpios. No se simulan nuevas observaciones
    # ni se vuelven a imputar precios o fletes.
    ventas = leer_csv('ventas_limpias.csv', [
        'fecha', 'sku', 'categoria', 'precio_unitario_bs',
        'precio_estimado', 'unidades_vendidas'])
    compras = leer_csv('compras_limpias.csv', [
        'fecha_pedido', 'sku', 'costo_unitario_usd', 'tipo_cambio_bs_usd',
        'cantidad', 'id_compra', 'proveedor'])

    # 3. Construir un catálogo SKU → categoría a partir de ventas. Compras
    # no tiene categoría propia. Se rechazan asignaciones contradictorias.
    catalogo = {}
    for fila in ventas:
        sku, categoria = fila['sku'], fila['categoria']
        if not sku or not categoria:
            raise ValueError('SKU o categoría vacíos.')
        if sku in catalogo and catalogo[sku] != categoria:
            raise ValueError(f'{sku} tiene más de una categoría.')
        catalogo[sku] = categoria

    # 4. Preparar filas compactas para incorporar todos los datos necesarios
    # dentro del HTML. La posición de cada valor se documenta en la guía.
    # Los otros campos de los CSV permanecen en datos/, aunque esta HU no los use.
    filas_compras = []
    for fila in compras:
        if fila['sku'] not in catalogo:
            raise ValueError(f"SKU de compra sin categoría: {fila['sku']}")
        fecha = date.fromisoformat(fila['fecha_pedido']).isoformat()
        cantidad = int(fila['cantidad'])
        if cantidad <= 0:
            raise ValueError('La cantidad comprada debe ser positiva.')
        filas_compras.append([
            fecha, fila['sku'], positivo(fila['costo_unitario_usd']),
            positivo(fila['tipo_cambio_bs_usd']), cantidad,
            fila['id_compra'], fila['proveedor']])

    filas_ventas = []
    for fila in ventas:
        fecha = date.fromisoformat(fila['fecha']).isoformat()
        unidades = int(fila['unidades_vendidas'])
        if unidades < 0:
            raise ValueError('Las unidades vendidas no pueden ser negativas.')
        filas_ventas.append([
            fecha, fila['sku'], positivo(fila['precio_unitario_bs']),
            booleano(fila['precio_estimado']), unidades])

    # 5. Serializar en JSON: el navegador lee este bloque como datos, no como
    # código. Escapar < protege el cierre del bloque si hubiera texto especial.
    datos = dict(catalogo=catalogo, compras=filas_compras, ventas=filas_ventas)
    contenido = json.dumps(datos, ensure_ascii=False, separators=(',', ':'))
    contenido = contenido.replace('<', '\\u003c')

    # 6. Reemplazar una única marca de la plantilla y guardar un HTML autónomo.
    # CSS, JavaScript y datos quedan incluidos. No hace falta servidor ni Internet.
    plantilla = PLANTILLA.read_text(encoding='utf-8')
    if plantilla.count('__DATA__') != 1:
        raise ValueError('La plantilla debe contener una única marca __DATA__.')
    SALIDA.write_text(plantilla.replace('__DATA__', contenido), encoding='utf-8')
    print(f'HTML creado: {SALIDA.name}')
    print(f'{len(compras):,} compras, {len(ventas):,} registros diarios de venta.')
    print(f'{len(catalogo)} repuestos. Datos ficticios; no se añadieron registros.')


if __name__ == '__main__':
    crear_panel()
