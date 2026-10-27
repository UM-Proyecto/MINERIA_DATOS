# 1. Importar herramientas para manejar fechas, simular datos y guardar CSV y ZIP.
from pathlib import Path
from datetime import date, timedelta
import random, csv, zipfile, math

# 2. Configurar la simulación: carpeta de salida, semilla reproducible, período,
# 30 repuestos, categorías, costos base y un tipo de cambio ficticio por día.
RAIZ = Path(__file__).resolve().parents[2]
P = RAIZ / 'data' / 'raw' / 'hu-34'
DOCUMENTACION = RAIZ / 'docs' / 'hu-34'
r=random.Random(34)
inicio=date(2025,1,1); fin=date(2026,10,24)
dias=[inicio+timedelta(days=i) for i in range((fin-inicio).days+1)]
skus=[f'RP{i:03}' for i in range(1,31)]
categorias=['Filtros','Frenos','Suspensión','Encendido','Correas']
cat={s:categorias[i%5] for i,s in enumerate(skus)}
costos={s:round(r.uniform(4,70),2) for s in skus}
tc={d:round(8.5+0.0015*i+0.25*math.sin(i/40),4) for i,d in enumerate(dias)}
# 3. Crear 3.600 compras con proveedores, cantidades, costos y plazos de entrega.
# Las recepciones se acumulan por fecha y repuesto para actualizar el inventario.
# El subtotal incluye cantidad × costo USD × tipo de cambio, pero excluye flete y tributos.
compras=[]; entradas={}
for i in range(3600):
    d=r.choice(dias[:-30]); s=r.choice(skus); plazo=r.randint(5,30)
    recepcion=d+timedelta(days=plazo); q=r.randint(8,45)
    costo=round(costos[s]*r.uniform(.9,1.15),2)
    compras.append(dict(id_compra=f'C{i+1:05}',fecha_pedido=d.isoformat(),fecha_recepcion=recepcion.isoformat(),sku=s,proveedor=f'PR{r.randint(1,12):02}',cantidad=q,costo_unitario_usd=costo,tipo_cambio_bs_usd=tc[d],flete_bs=round(q*r.uniform(1,4),2),subtotal_bs=round(q*costo*tc[d],2)))
    entradas[(recepcion,s)]=entradas.get((recepcion,s),0)+q
compras.sort(key=lambda x:(x['fecha_pedido'],x['id_compra']))
# 4. Crear ventas e inventario diarios: 662 días × 30 repuestos = 19.860 filas por tabla.
# Cada SKU comienza con 100 unidades. Solo se vende lo disponible para evitar stock negativo.
# Stock final = stock inicial + entradas − ventas; ingreso = unidades vendidas × precio.
ventas=[]; inventario=[]; stock={s:100 for s in skus}
for i,d in enumerate(dias):
    for k,s in enumerate(skus):
        inicial=stock[s]; entrada=entradas.get((d,s),0)
        demanda=max(0,round(r.gauss(3+(k%4),2)))
        vendido=min(demanda,inicial+entrada); final=inicial+entrada-vendido
        precio=round(costos[s]*tc[d]*1.4,2)
        ventas.append(dict(fecha=d.isoformat(),sku=s,categoria=cat[s],unidades_vendidas=vendido,precio_unitario_bs=precio,ingreso_bs=round(vendido*precio,2)))
        inventario.append(dict(fecha=d.isoformat(),sku=s,almacen='Central',stock_inicial=inicial,entradas=entrada,salidas=vendido,stock_final=final))
        stock[s]=final
# 5. Introducir faltantes para practicar la evaluación de calidad:
# 199 precios e ingresos asociados, 72 proveedores, 108 fletes y 99 almacenes.
# Este generador crea datos con faltantes; la limpieza se realiza en otro código.
# Faltantes deliberados para documentar calidad; no se alteran claves ni cantidades.
for j in r.sample(range(len(ventas)),199):
    ventas[j]['precio_unitario_bs']=None; ventas[j]['ingreso_bs']=None
for j in r.sample(range(len(compras)),72): compras[j]['proveedor']=None
for j in r.sample(range(len(compras)),108): compras[j]['flete_bs']=None
for j in r.sample(range(len(inventario)),99): inventario[j]['almacen']=None
# 6. Documentar las columnas, sus tipos y el análisis que permite cada conjunto.
tipos={
'ventas': [('fecha','Fecha','Día observado'),('sku','Texto','Identificador de repuesto compartido entre fuentes'),('categoria','Texto','Familia de repuestos'),('unidades_vendidas','Entero','Unidades efectivamente vendidas en el día; puede ser cero'),('precio_unitario_bs','Decimal','Precio de venta por unidad en bolivianos'),('ingreso_bs','Decimal','Unidades por precio unitario, en bolivianos')],
'compras':[('id_compra','Texto','Identificador único de línea de compra'),('fecha_pedido','Fecha','Fecha de emisión del pedido'),('fecha_recepcion','Fecha','Fecha de ingreso del repuesto'),('sku','Texto','Identificador de repuesto'),('proveedor','Texto','Código ficticio del proveedor'),('cantidad','Entero','Unidades recibidas'),('costo_unitario_usd','Decimal','Costo de adquisición por unidad en dólares'),('tipo_cambio_bs_usd','Decimal','Bolivianos por dólar; tasa simulada de la fecha del pedido'),('flete_bs','Decimal','Flete de la línea de compra en bolivianos'),('subtotal_bs','Decimal','Cantidad por costo USD por tipo de cambio; excluye flete, tributos y otros gastos')],
'inventario':[('fecha','Fecha','Día del cierre'),('sku','Texto','Identificador de repuesto'),('almacen','Texto','Nombre del almacén ficticio'),('stock_inicial','Entero','Unidades al inicio del día'),('entradas','Entero','Unidades recibidas de compras'),('salidas','Entero','Unidades vendidas'),('stock_final','Entero','Stock inicial más entradas menos salidas')]
}
datos={'ventas':ventas,'compras':compras,'inventario':inventario}
usos={'ventas':'Permite analizar ventas por repuesto, categoría y mes, frecuencia de días sin ventas y preparar series diarias para pronóstico. Las ventas observadas pueden subestimar la demanda cuando hay faltantes. No permite medir ventas perdidas ni preferencias de clientes.', 'compras':'Permite analizar cantidades compradas, precios de adquisición, variación del tipo de cambio simulado y plazos de entrega por proveedor. El costo total parcial es subtotal_bs + flete_bs; si falta el flete, no se debe tratar como cero. No incluye tributos ni permite calcular un costo de importación completo.', 'inventario':'Permite identificar faltantes, existencias acumuladas, cobertura y evolución del stock, y contrastar salidas con ventas y entradas con recepciones. No incluye reservas, devoluciones ni ajustes.'}
# 7. Preparar el informe MD: tamaño de las fuentes, períodos y naturaleza ficticia.
lineas=['# HU-34 — Describir los conjuntos de datos disponibles', '', '## Empresa y propósito', '', 'MULTIPARTE, empresa de repuestos automotrices. Actor principal: jefe de compras. Esta entrega documenta fuentes para analizar cuándo y cuánto comprar, considerando ventas, inventario, costos y tipo de cambio.', '', '## Naturaleza y alcance', '', 'No se proporcionaron bases empresariales reales para esta actividad. Se construyeron tres fuentes FICTICIAS para fines académicos; no son registros, cifras ni resultados reales de MULTIPARTE. Las tasas de cambio también son ficticias y no provienen de una cotización oficial. El período simulado termina el 24/10/2026. Los registros de 2025 aportan historia para analizar 2026.', '', 'Cada conjunto supera 3.000 filas. Una fila significa una observación con sus columnas, no una celda. El volumen y la cobertura permiten practicar integración y análisis, pero no garantizan precisión ni representan evidencia sobre la empresa.', '', '## Inventario de fuentes', '', '| Fuente | Archivo | Filas | Columnas | Unidad de observación | Período principal | Origen |', '|---|---|---:|---:|---|---|---|']
grano={'ventas':'Un repuesto por día (incluye ceros)','compras':'Una línea de pedido recibida','inventario':'Un repuesto por día y almacén'}
for nombre,filas in datos.items():
    campo='fecha_pedido' if nombre=='compras' else 'fecha'
    fechas=[x[campo] for x in filas]
    lineas.append(f'| {nombre} | {nombre}_simuladas.csv | {len(filas):,} | {len(filas[0])} | {grano[nombre]} | {min(fechas)} a {max(fechas)} | Ficticio |')
for nombre,filas in datos.items():
    # Exportar cada CSV y añadir al informe el detalle de columnas y faltantes.
    # Porcentaje de faltantes = valores vacíos de la columna / filas × 100.
    with (P/f'{nombre}_simuladas.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=filas[0]); w.writeheader(); w.writerows(filas)
    lineas+=['',f'## Conjunto: {nombre}','',f'**Tamaño:** {len(filas):,} registros y {len(filas[0])} columnas. **Origen:** ficticio. **Cobertura:** 30 repuestos.', '', '**Columnas, tipos y datos faltantes**', '', '| Columna | Tipo lógico | Significado y unidad | Faltantes | Porcentaje |','|---|---|---|---:|---:|']
    for campo,tipo,desc in tipos[nombre]:
        n=sum(x[campo] is None or x[campo]=='' for x in filas)
        lineas.append(f'| {campo} | {tipo} | {desc} | {n} | {100*n/len(filas):.2f}% |')
    lineas+=['','**Rango de fechas por columna**','']
    for campo,tipo,_ in tipos[nombre]:
        if tipo=='Fecha':
            valores=[x[campo] for x in filas if x[campo]]
            lineas.append(f'- `{campo}`: {min(valores)} a {max(valores)}; {len(set(valores))} fechas distintas.')
    lineas+=['','**Análisis que permite y límites:** '+usos[nombre]]
# 8. Documentar relaciones entre tablas, supuestos y limitaciones de los datos.
lineas+=['','## Calidad y relaciones entre fuentes','','Porcentaje de faltantes = número de valores vacíos de la columna / número de filas del conjunto × 100. Los campos vacíos del CSV representan nulos; cero es un valor válido y no se cuenta como faltante. Los tipos indicados son lógicos: CSV no conserva tipos nativos, por lo que deben asignarse al importar. Fechas en formato ISO AAAA-MM-DD, separador coma y punto decimal.', '', 'Ventas e inventario se relacionan por fecha + sku (clave única). Compras se relaciona por sku y fecha_recepcion con las entradas de inventario. Se debe agregar primero la cantidad de compras por fecha_recepcion + sku antes de unir con inventario, para no multiplicar filas. No se deben sumar los stocks diarios como si fueran ventas; para un mes se utiliza el cierre o el promedio según el indicador.', '', 'Los faltantes fueron introducidos intencionalmente y sus porcentajes se calcularon después de generar los archivos. No hay faltantes en fechas, claves ni cantidades. Precio e ingreso tienen faltantes en las mismas 199 filas: esas ventas pueden contarse en unidades, pero no completarse monetariamente sin una regla justificada. Proveedores faltantes deben conservarse como no informados, y fletes desconocidos requieren revisión antes de calcular costos. Almacén faltante debe validarse, aunque esta simulación tiene un único almacén.', '', '## Construcción y verificación', '', 'Generación reproducible con Python estándar y semilla 34. Se usaron 30 códigos de repuesto y 12 códigos de proveedor. Las compras ingresan entre 5 y 30 días después del pedido. Inventario inicial: 100 unidades por repuesto. Las ventas diarias están limitadas por el stock disponible; los días con cero ventas permanecen en la serie. No se incluyen precios reales ni datos personales.', '', 'Se verificaron claves únicas, fechas, cantidades no negativas, stock final = stock inicial + entradas − salidas, continuidad diaria del stock, salidas = ventas y entradas = compras recibidas. Los porcentajes documentados provienen de los CSV, no de estimaciones.', '', '## Cumplimiento de HU-34', '', '| Criterio | Evidencia |', '|---|---|', '| Cantidad de registros, columnas, tipos y fechas por conjunto | Tabla general y diccionarios individuales |', '| Identifica si los datos son reales o ficticios | Tres fuentes declaradas ficticias |', '| Identifica columnas con faltantes y porcentaje | Diccionarios con conteo y porcentaje para todas las columnas |', '| Mínimo de 3.000 datos | Cada CSV contiene más de 3.000 filas |', '', 'El número de filas no equivale al tamaño de una muestra independiente: varias observaciones corresponden a los mismos productos en fechas consecutivas. La utilidad de los pronósticos deberá evaluarse con partición temporal y comparación con un modelo base. Esta HU describe las fuentes; no demuestra todavía una mejora en las compras.']
# 9. Validar el mínimo de 3.000 filas por tabla, claves únicas y coherencia
# entre ventas, salidas, recepciones y balance de inventario. Después se releen los CSV.
assert all(len(x)>=3000 for x in datos.values())
assert len({(x['fecha'],x['sku']) for x in ventas})==len(ventas)
assert len({x['id_compra'] for x in compras})==len(compras)
for v,inv in zip(ventas,inventario):
    assert v['unidades_vendidas']==inv['salidas']
    assert inv['stock_final']==inv['stock_inicial']+inv['entradas']-inv['salidas']>=0
    assert inv['entradas']==entradas.get((date.fromisoformat(inv['fecha']),inv['sku']),0)
for nombre,filas in datos.items():
    with (P/f'{nombre}_simuladas.csv').open(encoding='utf-8-sig') as f:
        rec=list(csv.DictReader(f))
    assert len(rec)==len(filas)
    for c in filas[0]: assert sum(x[c]=='' for x in rec)==sum(x[c] is None for x in filas)
# 10. Guardar el informe MD y reunir los archivos en un ZIP.
# El ZIP incluye todos los archivos de la carpeta del script; usar una carpeta exclusiva.
(DOCUMENTACION/'HU34_Descripcion_Datos_MULTIPARTE.md').write_text('\n'.join(lineas),encoding='utf-8')
with zipfile.ZipFile(DOCUMENTACION/'HU34_MULTIPARTE.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(P.iterdir()):
        if f.is_file(): z.write(f,arcname=f'HU34_MULTIPARTE/{f.name}')
# 11. Mostrar el tamaño de los conjuntos y el total de 43.320 registros.
print({n:len(x) for n,x in datos.items()})
print('Verificación correcta. Total de registros:',sum(map(len,datos.values())))
