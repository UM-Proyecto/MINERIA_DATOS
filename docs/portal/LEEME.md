# Portal de MULTIPARTES (SCRUM-73, SCRUM-77 y SCRUM-78)

El portal es la misma app del simulador, servida desde un servidor con base de datos. Con eso puede guardar lo que la
app sola no guarda: cotizaciones, repuestos cargados y clientes dados de alta. Cada usuario ve lo que le corresponde.

Encuadre (decisión de Sam del 13-11-2026): el portal es una **fuente de datos de demanda** para la decisión de compra.
Una cotización guardada dice qué pidió un cliente aunque no haya comprado. Las que no se convierten en venta son
demanda que no se cerró, y las que sí se convierten alimentan el tablero de clientes (SCRUM-76).

## Quién ve qué

| Rol | Cómo entra | Qué ve |
|---|---|---|
| Cliente | Sin cuenta | Catálogo y cotizador; cada cotización que emite queda guardada |
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
| `tests/test_portal.py` y `tests/_portal_runner.mjs` | 11 pruebas de la API contra una D1 simulada |

El servidor recalcula cada cotización con el mismo motor de la app (`Motor.cotizar`) y con el dólar oficial del día.
No usa el precio que manda el navegador. El dólar lo lee del CSV de SCRUM-54 publicado en este repositorio, que la
tarea diaria de SCRUM-71 actualiza; si no lo puede leer, usa el valor que trae incorporado y dice su fecha.

### Base de datos

Tres tablas, que se crean solas en el primer pedido:
- `cotizaciones`: número correlativo, fecha (UTC), cliente, repuesto, cantidad, dólar y su fecha, precio de lista,
  descuento, total, y si se convirtió en venta;
- `clientes`: los dados de alta en el portal (`CLI-N001`, …);
- `repuestos`: los cargados en el portal (`REP-N001`, …).

Un repuesto cargado no tiene historial de venta. Aparece en el catálogo, el cotizador, las alertas (como «Sin datos»,
con el motivo) y el plan, pero no en las vistas que necesitan historial: simulador, temporadas, clasificación y «¿Qué
hubiera pasado?».

### API

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/tc` | Todos | Dólar oficial del día, con su fecha y de dónde salió |
| `POST /api/entrar` | Todos | Devuelve un token de sesión de 8 horas, firmado con HMAC-SHA256 |
| `GET /api/repuestos` | Todos | Repuestos cargados (para el catálogo) |
| `POST /api/cotizaciones` | Todos | Emite y guarda una cotización |
| `GET /api/cotizaciones` | Importador | Lista con filtros `cliente`, `repuesto` y `mes`; con `formato=csv`, exporta |
| `POST /api/cotizaciones/{n}/venta` | Importador | Marca la cotización como venta |
| `GET /api/ventas-clientes` | Importador | Ventas salidas de cotizaciones, para el tablero de clientes |
| `GET` y `POST /api/clientes` | Importador | Lista y alta de clientes |
| `POST /api/repuestos` | Importador | Carga de un repuesto |
| `GET /api/proveedor` | Proveedor | Sus repuestos con el estado de reposición |

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

El portal está en Cloudflare Pages, plan gratuito, con una base D1. La clave de sesión `SECRETO` es un valor al azar
de 64 caracteres, guardado como secreto del proyecto en Cloudflare; no está en el repositorio. Para publicar una
versión nueva con Wrangler:

```bash
python3 src/portal/armar_portal.py
npx wrangler pages deploy build/portal --project-name <proyecto>
```

El enlace, el proyecto y la base están anotados en el informe de la entrega.
