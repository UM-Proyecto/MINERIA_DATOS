"""SCRUM-76: clientes SINTÉTICOS repartidos sobre las ventas REALES de carparts.

carparts trae cuántas unidades se vendieron de cada repuesto por mes, pero no a quién. Para el tablero de clientes,
cada unidad vendida se asigna a uno de 20 clientes SINTÉTICOS con una regla escrita y una semilla fija:
- hay cuatro tipos de cliente (talleres, flotas de empresas, repuesteras que revenden y particulares), cada uno con
  un tamaño relativo y una preferencia por ciertas categorías del catálogo (SCRUM-74);
- el peso de un cliente para una unidad es su tamaño por su preferencia por la categoría de ese repuesto;
- con random.Random(SEMILLA) se sortea el cliente de cada unidad, recorriendo repuestos y meses en orden.
El total por repuesto y mes queda igual al real. Quién compra qué lo decide la regla, no los datos: por eso todo
dato por cliente es SINTÉTICO. Los meses de temporada no se fijan acá; los calcula la app con las ventas reales.

Uso, desde cualquier carpeta:
    python3 src/scrum-76/generar_clientes.py

Solo usa la biblioteca estándar.
"""
import csv
import random
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
VENTAS = BASE / "data/processed/scrum-55/ventas_mensuales.csv"
CATALOGO = BASE / "data/processed/scrum-74/catalogo.csv"
SAL_CLIENTES = BASE / "data/processed/scrum-76/clientes.csv"
SAL_VENTAS = BASE / "data/processed/scrum-76/ventas_por_cliente.csv"
SEMILLA = 20261113

# Preferencia por categoría de cada tipo de cliente (1 = normal). SINTÉTICO: supuesto del equipo.
PREFERENCIA = {
    "Taller mecánico": {"Pastillas de freno": 2.0, "Disco de freno": 2.0, "Kit de embrague": 2.5, "Amortiguador": 2.0,
                        "Correa de distribución": 1.8, "Cubo y rodamiento de rueda": 1.8},
    "Flota de empresa": {"Filtro de aceite": 3.0, "Bujía de encendido": 2.5, "Pastillas de freno": 1.5},
    "Repuestera": {},
    "Particular": {"Bujía de encendido": 2.0, "Filtro de aceite": 2.0, "Kit de embrague": 0.3, "Amortiguador": 0.5},
}
# (cliente_id, nombre, tipo, zona, tamaño relativo). Nombres genéricos y ficticios.
CLIENTES = [
    ("CLI-01", "Taller El Cruce (ficticio)", "Taller mecánico", "Norte", 9),
    ("CLI-02", "Repuestera Los Pozos (ficticio)", "Repuestera", "Centro", 8),
    ("CLI-03", "Transportes Oriente (ficticio)", "Flota de empresa", "Parque Industrial", 7),
    ("CLI-04", "Taller Doble Vía (ficticio)", "Taller mecánico", "Este", 6),
    ("CLI-05", "Repuestera Mutualista (ficticio)", "Repuestera", "Este", 6),
    ("CLI-06", "Distribuidora Agro Norte (ficticio)", "Flota de empresa", "Norte", 5),
    ("CLI-07", "Taller Plan 3000 (ficticio)", "Taller mecánico", "Sur", 5),
    ("CLI-08", "Repuestera Ramada (ficticio)", "Repuestera", "Centro", 4),
    ("CLI-09", "Taller Equipetrol (ficticio)", "Taller mecánico", "Oeste", 4),
    ("CLI-10", "Radiomóviles Unidos (ficticio)", "Flota de empresa", "Centro", 4),
    ("CLI-11", "Taller Villa 1° de Mayo (ficticio)", "Taller mecánico", "Este", 3),
    ("CLI-12", "Repuestera Warnes (ficticio)", "Repuestera", "Norte", 3),
    ("CLI-13", "Constructora Piraí (ficticio)", "Flota de empresa", "Oeste", 3),
    ("CLI-14", "Taller Banzer km 9 (ficticio)", "Taller mecánico", "Norte", 2),
    ("CLI-15", "Taller Pampa de la Isla (ficticio)", "Taller mecánico", "Este", 2),
    ("CLI-16", "Cliente particular 1 (ficticio)", "Particular", "Centro", 1.5),
    ("CLI-17", "Cliente particular 2 (ficticio)", "Particular", "Norte", 1.2),
    ("CLI-18", "Cliente particular 3 (ficticio)", "Particular", "Sur", 1),
    ("CLI-19", "Cliente particular 4 (ficticio)", "Particular", "Oeste", 1),
    ("CLI-20", "Cliente particular 5 (ficticio)", "Particular", "Este", 0.8),
]


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def repartir(ventas, categoria, semilla=SEMILLA):
    """Asigna cada unidad vendida a un cliente. Devuelve filas (mes, repuesto, cliente, unidades)."""
    rnd = random.Random(semilla)
    pesos_cat = {}
    for cat in sorted(set(categoria.values())):
        pesos_cat[cat] = [c[4] * PREFERENCIA[c[2]].get(cat, 1.0) for c in CLIENTES]
    filas = []
    for v in sorted(ventas, key=lambda r: (r["repuesto_id"], r["mes"])):
        u = int(v["unidades"])
        if u < 0:
            raise SystemExit(f"Unidades negativas en {v['repuesto_id']} {v['mes']}")
        if u == 0:
            continue
        cuenta = {}
        pesos = pesos_cat[categoria[v["repuesto_id"]]]
        for _ in range(u):
            cid = rnd.choices(CLIENTES, weights=pesos)[0][0]
            cuenta[cid] = cuenta.get(cid, 0) + 1
        for cid in sorted(cuenta):
            filas.append({"mes": v["mes"], "repuesto_id": v["repuesto_id"], "cliente_id": cid, "unidades": cuenta[cid]})
    return filas


def escribir(ruta, columnas, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)
    tmp.replace(ruta)


def main():
    categoria = {c["repuesto_id"]: c["categoria"] for c in leer(CATALOGO)}
    filas = repartir(leer(VENTAS), categoria)
    marca = {"origen_dato": "SINTÉTICO: cliente asignado por regla sobre ventas REALES de carparts", "marca": "SINTÉTICO"}
    escribir(SAL_CLIENTES, ["cliente_id", "nombre", "tipo", "zona", "tamano_relativo", "origen_dato", "marca"],
             [{"cliente_id": c[0], "nombre": c[1], "tipo": c[2], "zona": c[3], "tamano_relativo": c[4], **marca} for c in CLIENTES])
    escribir(SAL_VENTAS, ["mes", "repuesto_id", "cliente_id", "unidades", "origen_dato", "marca"], [dict(f, **marca) for f in filas])
    print(f"{SAL_VENTAS.relative_to(BASE)}: {len(filas)} filas, {sum(f['unidades'] for f in filas)} unidades, "
          f"{len(CLIENTES)} clientes SINTÉTICOS")


if __name__ == "__main__":
    main()
