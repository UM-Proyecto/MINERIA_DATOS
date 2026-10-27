import pandas as pd
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
catalogo = pd.read_csv(RAIZ / "data" / "raw" / "hu-17" / "catalogo_repuestos.csv")
movimientos = pd.read_csv(RAIZ / "data" / "raw" / "hu-17" / "movimientos_inventario.csv")

equivalencias = {
    "FIL-001": "REP-0001",
    "TOY-F001": "REP-0001",
    "FIL-002": "REP-0002",
    "TOY-FA01": "REP-0002",
    "PAS-001": "REP-0003",
    "TOY-PF01": "REP-0003",
    "AMO-001": "REP-0004",
    "TOY-AM01": "REP-0004",
    "BAT-001": "REP-0005",
    "BOS-B70": "REP-0005",
    "BUJ-001": "REP-0006",
    "NGK-BKR6": "REP-0006",
    "COR-001": "REP-0007",
    "TOY-CD01": "REP-0007",
    "BOM-001": "REP-0008",
    "TOY-BA01": "REP-0008",
    "FIL-003": "REP-0009",
    "TOY-FF01": "REP-0009",
    "DIS-001": "REP-0010",
    "TOY-DF01": "REP-0010"
}

movimientos["codigo_unico"] = movimientos["codigo_repuesto"].map(equivalencias)

movimientos["estado"] = "ORIGINAL"
movimientos["motivo"] = "Registro válido"

columnas_duplicado = [
    "fecha",
    "codigo_unico",
    "tipo_movimiento",
    "cantidad",
    "documento"
]

duplicados = movimientos.duplicated(
    subset=columnas_duplicado,
    keep="first"
)

movimientos.loc[duplicados, "estado"] = "DUPLICADO"
movimientos.loc[duplicados, "motivo"] = "Mismo movimiento registrado anteriormente"

for i in range(len(movimientos)):
    if movimientos.loc[i, "estado"] == "ORIGINAL":
        codigo = movimientos.loc[i, "codigo_unico"]
        documento = movimientos.loc[i, "documento"]

        anteriores = movimientos[
            (movimientos["codigo_unico"] == codigo) &
            (movimientos["documento"] != documento) &
            (movimientos["estado"] == "ORIGINAL")
        ]

        if len(anteriores) > 0:
            movimientos.loc[i, "estado"] = "PENDIENTE_REVISION"
            movimientos.loc[i, "motivo"] = "Mismo repuesto pero documento diferente"

reporte = movimientos[
    [
        "id_movimiento",
        "fecha",
        "codigo_repuesto",
        "codigo_unico",
        "tipo_movimiento",
        "cantidad",
        "documento",
        "proveedor_cliente",
        "usuario",
        "estado",
        "motivo"
    ]
]

reporte.to_csv(
    RAIZ / "data" / "processed" / "hu-17" / "reporte_depuracion_final.csv",
    index=False,
    encoding="utf-8-sig"
)

print("Proceso de depuración terminado.")
print("Archivo generado: reporte_depuracion_final.csv")

print("\nResumen:")
print(reporte["estado"].value_counts())
