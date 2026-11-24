# Portal de MULTIPARTES (SCRUM-73, SCRUM-77 y SCRUM-78)

El portal es la misma app del simulador, servida desde un servidor con base de datos. Con eso puede guardar lo que la
app sola no guarda: cotizaciones, repuestos cargados y clientes dados de alta. Cada usuario ve lo que le corresponde.

Encuadre (decisión de Sam del 13-11-2026): el portal es una **fuente de datos de demanda** para la decisión de compra.
Una cotización guardada dice qué pidió un cliente aunque no haya comprado. Las que no se convierten en venta son
demanda que no se cerró, y las que sí se convierten alimentan el tablero de clientes (SCRUM-76).

## Dos entradas: la tienda y el área de la empresa (mejora v2, 14-11-2026)

| Dirección | Para quién | Qué es |
|---|---|---|
| `/` | Clientes, sin cuenta | Tienda pública: mejora del sitio actual de MULTIPARTES (www.multipartes.com.bo) |
| `/empresa` | Importador y proveedor, con usuario | La app del simulador y del portal; sin sesión solo muestra la pantalla de entrada |

La tienda (`src/tienda/`, generada en `reports/tienda/MULTIPARTES_Tienda.html`) **mantiene** lo del sitio actual: barra
verde con el logotipo, marcas de vehículos, «¿Por qué elegirnos?», los nueve rubros con sus fotos, los catálogos PDF,
WhatsApp y redes. **Mejora** la portada (el carrusel del sitio se veía vacío), los rubros (los que tienen productos
llevan al catálogo), los distribuidores (en texto, porque los logos del sitio no cargan) y suma sucursales y horario
a la misma página. **Agrega** el catálogo con precio y stock, el cotizador (en la portada y en su sección) y el acceso
a la empresa.

Todo el texto real sale de `data/raw/tienda/contenido_sitio.json`, copiado del sitio el 14-11-2026, y las imágenes
de `data/raw/tienda/imagenes/`, con su origen en `fuentes_imagenes.csv`. Lo que hay que confirmar con MULTIPARTES
va marcado «A CONFIRMAR» en la página: el WhatsApp de la portada (se usa el de ventas de Casa Matriz, 690 08189) y la
cantidad de sucursales («Nosotros» dice cinco; «Contacto» lista seis más Accesorios, y se muestra lo de Contacto).

Como usa la marca, los teléfonos y las sucursales reales pero con precios de prueba, la tienda dice siempre, en una
franja fija arriba, que es un prototipo académico y no el sitio oficial, con el enlace al sitio oficial. Además pide
no ser indexada (`<meta name="robots">` y la cabecera `X-Robots-Tag` en las dos páginas).

## Quién ve qué

| Rol | Cómo entra | Qué ve |
|---|---|---|
| Cliente | Sin cuenta, en la tienda (`/`) | Catálogo y cotizador; cada cotización que emite queda guardada |
| Importador | Usuario `importador` | Todo el simulador, más cotizaciones guardadas y carga de repuestos y clientes |
| Proveedor | Usuario `proveedor` | Solo sus repuestos: estado, stock y cuánto se le pediría |

Los usuarios son de **DEMOSTRACIÓN** (`importador` / `demo-importador`, `proveedor` / `demo-proveedor`) y la pantalla de
entrada los muestra. El rol se controla en dos lugares:
- la app oculta las pantallas que no corresponden y, si se escribe la dirección a mano, lleva a la del rol;
- la API rechaza con 401 (sin sesión) o 403 (otro rol) cualquier pedido que no corresponda, y eso es lo que protege
  los datos guardados.

Un límite: los datos del simulador (ventas de carparts, proveedores y clientes SINTÉTICOS) van dentro de la página,
como en el archivo que se abre con doble clic, y además están publicados en este repositorio. El control por rol
protege lo que se guarda en la base, no esos datos de ejemplo.

## Cómo está hecho

| Pieza | Qué hace |
|---|---|
| `src/portal/worker_api.js` | Rutas de la API y la página. Corre en Cloudflare Pages (modo avanzado, `_worker.js`) con una base D1 |
| `src/portal/armar_portal.py` | Arma `build/portal/_worker.js`: motor del simulador + `datos_app.json` + la app + la API |
| `src/portal/servir_local.mjs` | Sirve el portal en `http://localhost:8788` con una base SQLite en memoria, para probar sin Cloudflare |
| `tests/test_portal.py` y `tests/_portal_runner.mjs` | Pruebas de la API contra una D1 simulada |

El servidor recalcula cada cotización con el mismo motor de la app (`Motor.cotizar`) y con el dólar oficial del día.
No usa el precio que manda el navegador. El dólar lo lee del CSV de SCRUM-54 publicado en este repositorio, que la
tarea diaria de SCRUM-71 actualiza; si no lo puede leer, usa el valor que trae incorporado y dice su fecha.

### Base de datos

Las tablas se crean solas en el primer pedido (`CREATE TABLE IF NOT EXISTS`):
- `cotizaciones`: número correlativo, fecha (UTC), cliente, repuesto, cantidad, dólar y su fecha, precio de lista,
  descuento, total, si se convirtió en venta, y el correo al que se «envió» con su hora (`correo`, `correo_enviado`,
  SCRUM-83). Estas dos columnas se agregaron después de publicar el portal: la primera vez que el servidor arranca
  con una base vieja, revisa `PRAGMA table_info` y las agrega con `ALTER TABLE … ADD COLUMN`, sin tocar las filas.
- `clientes`: los dados de alta en el portal (`CLI-N001`, …);
- `repuestos`: los cargados en el portal (`REP-N001`, …);
- `secuencias`: el último número entregado de cada código correlativo (`clientes`, `repuestos`). Antes el código se
  calculaba con `COUNT(*) + 1` y un borrado hacía repetir un código existente. Ahora cada alta toma el mayor entre el
  último entregado y el máximo numérico que ya existe en la tabla, más uno, así que una base anterior a este cambio
  sigue desde su máximo;
- `movimientos_stock` (D6, decisión de Sam del 24-11-2026): cada salida o entrada de stock, con el repuesto, la
  cantidad con signo, el motivo (`venta` o `ajuste`), el número de cotización en las ventas, la fecha (UTC) y el
  usuario. Un índice único impide que una cotización descuente dos veces;
- `ajustes_repuestos` (D8): los cambios del importador a los 30 repuestos del dataset (nombre, categoría, descripción,
  costo, margen y proveedor), con la fecha y el usuario de la última modificación. Cada columna no nula se pone
  encima del dato del dataset, que no se toca. El stock no está aquí: se ajusta con un movimiento.

- `marca` (D7): una fila, `cambios`, con un contador y la fecha del último cambio. Toda escritura del portal (venta,
  alta de cliente o de repuesto, edición, CSV y, con ellas, los movimientos de stock) le suma 1 en la misma
  `db.batch`. Las cotizaciones nuevas no la tocan, porque ya cambian `MAX(numero)`.

Columnas agregadas a tablas existentes, con `ALTER TABLE … ADD COLUMN` la primera vez que el servidor arranca con
una base vieja (revisa `PRAGMA table_info` y no toca las filas): `cotizaciones.correo` y `correo_enviado`
(SCRUM-83), y `repuestos.modificado` y `repuestos.usuario` (D8).

### Stock vigente (D6)

El stock vigente de un repuesto es su **stock base** más la suma de sus movimientos. El stock base es el del dataset
al 10-11-2026 (`stock_al_2026_11_10`) para `REP-0001`…`REP-0030` y la columna `stock` del alta para los cargados.

- **Cotizar no descuenta ni reserva.** Dos cotizaciones seguidas ven las mismas unidades.
- **Marcar la venta descuenta** la cantidad cotizada. La marca de venta y el movimiento se escriben en una misma
  `db.batch`, que D1 ejecuta como una transacción; las dos sentencias repiten las condiciones (cotización sin vender
  y stock suficiente), así que si otra venta se cuela entre la lectura y la escritura no se escribe nada.
- Si la venta deja el stock en negativo, el servidor responde **409** con el stock que hay y cuánto quedaría. El
  importador puede confirmarla de todos modos (la pantalla lo pregunta y reenvía con `{"forzar": true}`), por ejemplo
  si las unidades sí salieron del almacén y el conteo estaba atrasado.
- Un stock negativo se ve con su signo en `/api/stock` y en el historial. Al motor (cotizador, alertas, vista del
  proveedor) le llega como 0, porque el motor toma un número negativo por dato inválido.
- Las ventas marcadas **antes** de este cambio no descuentan: no tienen movimiento y el stock base no se tocó.
- La tienda, el catálogo y el cotizador del área de la empresa, las alertas y el plan leen el stock vigente de
  `/api/stock` al cargar la página y después de cada venta o alta. La vista del proveedor lo calcula en el servidor.

### Datos en vivo (D7)

Decisión de Sam del 24-11-2026: botón «Actualizar» y consulta automática cada 30 segundos. El servidor ya servía
fresco lo guardado en D1; el retraso estaba en el navegador.

- **Área de la empresa**: botón «Actualizar» en la barra de sesión, con «Actualizado hace …» al lado. Vuelve a pedir
  repuestos, stock, ajustes, clientes y ventas y pinta la vista actual con los mismos filtros y en la misma posición.
- **Consulta automática**: con sesión y con la pestaña visible, cada 30 s el navegador pide `GET /api/version`, que
  lee dos filas. Si la versión cambió, vuelve a pedir todo. Con la pestaña oculta el temporizador se apaga y no sale
  ningún pedido; al volver a la pestaña, y al entrar a una vista con datos guardados, se consulta la versión enseguida.
- **Tienda**: botón «Actualizar precios y stock» y consulta de la versión al volver a la pestaña. No consulta sola cada
  30 s: es pública y anónima, y cada pestaña abierta sumaría pedidos al plan gratuito.

### Edición de repuestos y carga masiva por CSV (D8)

Decisión de Sam del 24-11-2026: se pueden editar **todos** los repuestos, los cargados y los 30 del dataset, y se
suma una carga masiva por CSV. Solo el importador (401 sin sesión, 403 con otro rol).

- **Qué se edita**: nombre, categoría, descripción, costo de fábrica en USD, margen, proveedor y stock. El precio de
  venta no se escribe: se recalcula. En los 30 del dataset, si cambia el costo, el margen o el proveedor, el servidor
  recalcula el costo puesto (flete y gastos del proveedor) y el precio, como SCRUM-55; si no cambian, quedan los del
  dataset centavo por centavo. En los cargados el precio sigue siendo costo × (1 + margen), como en el alta.
- **Categoría de una lista cerrada**: las ocho del catálogo del dataset. Vale también para el alta (`POST
  /api/repuestos`), que antes aceptaba texto libre.
- **Stock**: se escribe el stock vigente que se quiere tener. No se pisa la base: se registra un movimiento
  «ajuste» por la diferencia, calculada dentro de la misma sentencia para que una venta que llegue en el medio no
  se pierda.
- Un nombre o una descripción que empiezan con `=`, `+`, `-` o `@` se rechazan, porque Excel los tomaría como
  fórmula al abrir un CSV exportado.
- En la pantalla: botón «Editar» en cada ficha del Catálogo del área de la empresa (solo con el usuario
  importador). Se envían solo los campos que cambiaron.

**Carga masiva por CSV** (pantalla «Registrar repuestos y clientes»):

- La plantilla (`GET /api/repuestos/plantilla.csv`) trae todos los repuestos actuales con el stock vacío: una celda
  vacía no cambia nada, y así una plantilla bajada hace días no deshace las ventas registradas después.
- Encabezado exacto `repuesto_id,nombre,categoria,descripcion,costo_unitario_usd,margen_pct,stock,proveedor_id,fecha_ingreso`.
  El separador se decide una vez, por el encabezado: coma (con punto decimal) o punto y coma (con coma decimal, como
  guarda Excel en español).
- Fila con `repuesto_id` vacío = alta, con todos los datos y la fecha de ingreso. Fila con código = edición de ese
  repuesto. Se rechazan: un código que no existe, el mismo código dos veces, una fecha en una edición, un alta con
  el mismo nombre y proveedor que un repuesto existente o que otra fila, y cualquier dato fuera de las reglas del alta.
- Primero se revisa (`POST /api/repuestos/csv`): el servidor devuelve qué hará cada fila y sus errores, sin escribir.
  Con `?aplicar=1` vuelve a revisar todo y, solo si no hay ningún error, escribe todas las filas en una `db.batch`
  (todo o nada); si hay errores responde 422 y no escribe nada.
- Topes: 500 filas y 256 KB por archivo. Es la única ruta con un cuerpo mayor que `MAX_CUERPO` (8 KB). Cada fila son
  hasta dos escrituras en D1, así que 500 filas quedan muy por debajo de las 100 000 escrituras diarias del plan
  gratuito, y la `db.batch` cuenta como una sola consulta para el límite de consultas por invocación.

Un repuesto cargado no tiene historial de venta. Aparece en el catálogo, el cotizador, las alertas (como «Sin datos»,
con el motivo) y el plan, pero no en las vistas que necesitan historial: simulador, temporadas y predicciones. En rotación aparece como «Sin datos».

### API

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/version` | Todos | Versión de lo guardado: `{"v": "<máx. cotización>.<cambios>", "cotizaciones", "cambios", "fecha"}` |
| `GET /api/tc` | Todos | Dólar oficial del día, con su fecha y de dónde salió |
| `POST /api/entrar` | Todos | Devuelve un token de sesión de 8 horas, firmado con HMAC-SHA256 |
| `GET /api/repuestos` | Todos | Repuestos cargados (para el catálogo), con el stock vigente |
| `GET /api/ajustes` | Todos | Cambios del importador a los 30 del dataset, ya aplicados (nombre, categoría, descripción, costo, margen, costo puesto, precio y proveedor) |
| `GET /api/stock` | Todos | Stock vigente de todos los repuestos: `{"base": "2026-11-10", "repuestos": [{"repuesto_id", "stock"}]}`. Sin datos internos |
| `GET /api/movimientos` | Importador | Historial de movimientos de stock, del más nuevo al más viejo; filtro `repuesto` |
| `POST /api/cotizaciones` | Todos | Emite y guarda una cotización |
| `GET /api/cotizaciones` | Importador | Lista con filtros `cliente`, `repuesto` y `mes`; con `formato=csv`, exporta |
| `POST /api/cotizaciones/{n}/venta` | Importador | Marca la cotización como venta y descuenta el stock en la misma transacción. 409 si deja el stock negativo, salvo `{"forzar": true}` |
| `GET /api/ventas-clientes` | Importador | Ventas salidas de cotizaciones, para el tablero de clientes |
| `GET` y `POST /api/clientes` | Importador | Lista y alta de clientes |
| `POST /api/repuestos` | Importador | Carga de un repuesto (categoría de la lista cerrada) |
| `PATCH /api/repuestos/{id}` | Importador | Edita un repuesto del dataset o cargado; el stock se ajusta con un movimiento |
| `GET /api/repuestos/plantilla.csv` | Importador | Plantilla CSV con los repuestos actuales |
| `POST /api/repuestos/csv` | Importador | Revisa un CSV fila por fila; con `?aplicar=1`, lo aplica entero o nada |
| `GET /api/proveedor` | Proveedor | Sus repuestos con el estado de reposición |

### Cotización por correo y cotización imprimible (SCRUM-83)

En la tienda, la cotización pide un correo. El navegador y el servidor validan que tenga la forma `nombre@dominio.xx`:
el campo vacío o un correo mal escrito no se envía, y la pantalla dice por qué.

Al enviar, **no sale ningún correo**: el envío es de demostración. El servidor guarda la dirección y la hora junto a
la cotización. La pantalla confirma «Cotización N° … enviada a …» y muestra cómo llegaría el correo: para, de,
asunto, cuerpo y el adjunto `Cotizacion_MULTIPARTES_NNNNNN.pdf`. Una etiqueta y una frase dicen que es una
demostración, para que nadie espere un correo de verdad.

El adjunto es la cotización imprimible. La arma `src/portal/cotizacion_doc.js`, el mismo código en la tienda y en el
área de la empresa (los dos generadores lo incrustan después del motor). Lleva:

- el logotipo de MULTIPARTES, blanco sobre su verde #016726;
- la franja de prototipo académico;
- número, fecha y validez de 7 días;
- el cliente y su correo;
- el repuesto con precio de lista, descuento, precio por unidad e importe;
- subtotal, descuento y total;
- el dólar oficial con su fecha y los tramos de descuento, con el aplicado resaltado;
- las condiciones y la nota sobre el origen de los datos.

Se abre en una pestaña y se imprime o se guarda en PDF con el diálogo del navegador. No calcula precios: presenta
los que guardó el servidor.

En Cotizaciones guardadas, la columna «Enviada a» muestra el correo y la hora, y «Ver PDF» abre la misma cotización.

### Origen de los datos

La nota al pie del menú y de la tienda enlaza la base de datos de ventas: carparts, de Hyndman, Koehler, Ord y
Snyder (2008), en <https://robjhyndman.com/expsmooth/>. Qué es cada dato y de dónde sale está en
`docs/GUIA_ESTUDIO_PORTAL.md` y en `docs/scrum-55/LEEME.md`.

## Probarlo en la computadora

```bash
python3 src/simulador/preparar_datos.py
python3 src/simulador/generar_app.py
python3 src/portal/armar_portal.py
node src/portal/servir_local.mjs        # http://localhost:8788
python3 -m unittest tests.test_portal -v
```

Necesita Node 22 o superior (usa `node:sqlite`).

## Publicarlo

Dónde vive: Cloudflare Pages, plan gratuito, proyecto `multipartes-univalle` (https://multipartes-univalle.pages.dev),
con la base D1 `multipartes-portal-db` enlazada como `DB`. El proyecto tiene dos variables:
- `SECRETO`: la clave de sesión, 64 caracteres al azar generados dentro de Cloudflare. Es secreta y no está en el
  repositorio;
- `FUENTE_REF`: la rama o el commit de donde el servidor lee los datos y la app. Mientras el PR no esté unido vale
  `feature/temporadas-cotizador`; después de unirlo hay que cambiarla a `main`.

Lo que se publica es la versión liviana del servidor (`armar_portal.py --liviano`, unos 52 KB): motor y API. Los datos
y la app los lee del repositorio y los guarda 10 minutos en memoria. Por eso el dólar diario de SCRUM-71 entra al
portal sin volver a publicar, y hace falta publicar de nuevo solo cuando cambia el código del servidor o del motor.

La publicación la hace `.github/workflows/portal-deploy.yml` en cada push que toque ese código, o a mano desde la
pestaña Actions. Corre las pruebas, arma el servidor, lo sube con Wrangler y comprueba que responde. Necesita:
- la variable del repositorio `CLOUDFLARE_ACCOUNT_ID` (ya cargada);
- el secreto del repositorio `CLOUDFLARE_API_TOKEN`: un token de Cloudflare con el permiso «Account · Cloudflare
  Pages · Edit» sobre la cuenta. Lo crea el dueño de la cuenta en el panel de Cloudflare (My Profile › API Tokens) y
  lo guarda con `gh secret set CLOUDFLARE_API_TOKEN --repo UM-Proyecto/MINERIA_DATOS`. Sin ese secreto la tarea avisa
  y no publica.

Para publicar a mano desde una computadora con Wrangler:

```bash
python3 src/portal/armar_portal.py --liviano
npx wrangler pages deploy build/portal --project-name multipartes-univalle --branch main
```
