import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


FUENTE = Path(__file__).resolve().parents[1] / "proyecto_HU17" / "reporte_depuracion_final.csv"
METODOS = ("ultimo_periodo", "promedio_movil_3", "mismo_dia_semana")


def leer_movimientos(ruta):
    ventas = defaultdict(lambda: defaultdict(int))
    excluidos = defaultdict(lambda: defaultdict(int))
    repuestos = set()
    fechas = []
    with open(ruta, newline="", encoding="utf-8-sig") as archivo:
        for fila in csv.DictReader(archivo):
            codigo = fila["codigo_unico"]
            fecha = date.fromisoformat(fila["fecha"])
            repuestos.add(codigo)
            fechas.append(fecha)
            if fila["tipo_movimiento"] != "SALIDA":
                continue
            if fila["estado"] != "ORIGINAL":
                excluidos[codigo][fila["estado"]] += 1
                continue
            cantidad = int(fila["cantidad"])
            if cantidad < 0:
                raise ValueError(f"Cantidad negativa en {codigo}, {fecha}")
            ventas[codigo][fecha] += cantidad
    if not fechas:
        raise ValueError("El archivo no contiene movimientos")
    return ventas, excluidos, sorted(repuestos), min(fechas), max(fechas)


def pronosticar(entrenamiento, horizonte, metodo):
    historia = list(entrenamiento)
    pronosticos = []
    for _ in range(horizonte):
        if metodo == "ultimo_periodo":
            valor = historia[-1]
        elif metodo == "promedio_movil_3":
            valor = sum(historia[-3:]) / 3
        elif metodo == "mismo_dia_semana":
            valor = historia[-7]
        else:
            raise ValueError(f"Método desconocido: {metodo}")
        pronosticos.append(valor)
        historia.append(valor)
    return pronosticos


def evaluar(ruta, dias_prueba=5):
    ventas, excluidos, repuestos, inicio, fin = leer_movimientos(ruta)
    fechas = [inicio + timedelta(days=i) for i in range((fin - inicio).days + 1)]
    if dias_prueba < 1 or len(fechas) - dias_prueba < 7:
        raise ValueError("Se necesitan al menos 7 días de entrenamiento y 1 de evaluación")
    corte = len(fechas) - dias_prueba
    filas = []
    for codigo in repuestos:
        serie = [ventas[codigo].get(fecha, 0) for fecha in fechas]
        entrenamiento, prueba = serie[:corte], serie[corte:]
        errores = {}
        errores_por_mes = {}
        for metodo in METODOS:
            pronosticos = pronosticar(entrenamiento, dias_prueba, metodo)
            errores[metodo] = sum(abs(real - estimado) for real, estimado in zip(prueba, pronosticos)) / dias_prueba
            meses_metodo = defaultdict(list)
            for fecha, real, estimado in zip(fechas[corte:], prueba, pronosticos):
                meses_metodo[fecha.strftime("%Y-%m")].append(abs(real - estimado))
            errores_por_mes[metodo] = "; ".join(
                f"{mes}:{sum(valores) / len(valores):.3f}" for mes, valores in sorted(meses_metodo.items())
            )
        ventas_entrenamiento = sum(valor > 0 for valor in entrenamiento)
        ventas_evaluacion = sum(valor > 0 for valor in prueba)
        meses_entrenamiento = len({fecha.strftime("%Y-%m") for fecha in fechas[:corte]})
        meses_evaluacion = len({fecha.strftime("%Y-%m") for fecha in fechas[corte:]})
        ventas_por_mes_evaluado = defaultdict(int)
        for fecha, valor in zip(fechas[corte:], prueba):
            ventas_por_mes_evaluado[fecha.strftime("%Y-%m")] += valor
        limites = []
        if corte < 365 or dias_prueba < 365 or meses_entrenamiento < 12 or meses_evaluacion < 12:
            limites.append("sin un año de entrenamiento y uno de evaluacion: no se puede comparar epoca del año")
        if ventas_entrenamiento < 3:
            limites.append("menos de 3 dias con ventas en entrenamiento")
        if ventas_evaluacion == 0:
            limites.append("sin ventas registradas en evaluacion: MAE cero no valida el metodo")
        elif any(valor == 0 for valor in ventas_por_mes_evaluado.values()):
            limites.append("hay meses evaluados sin ventas registradas")
        if excluidos[codigo]["PENDIENTE_REVISION"]:
            limites.append("salidas pendientes de revision excluidas")
        limites.append("salidas observadas; faltantes de stock pueden ocultar demanda")
        mejor = min(METODOS, key=lambda metodo: (errores[metodo], METODOS.index(metodo)))
        datos_suficientes = (
            corte >= 365
            and dias_prueba >= 365
            and meses_entrenamiento >= 12
            and meses_evaluacion >= 12
            and ventas_entrenamiento >= 3
            and all(ventas_por_mes_evaluado.values())
            and excluidos[codigo]["PENDIENTE_REVISION"] == 0
        )
        seleccion = mejor if datos_suficientes else "SIN_SELECCION_FIABLE"
        for metodo in METODOS:
            filas.append({
                "codigo_unico": codigo,
                "metodo": metodo,
                "mae": f"{errores[metodo]:.3f}",
                "mae_por_mes": errores_por_mes[metodo],
                "periodos_evaluados": dias_prueba,
                "desde_evaluacion": fechas[corte].isoformat(),
                "hasta_evaluacion": fechas[-1].isoformat(),
                "epocas_evaluadas": ", ".join(sorted({fecha.strftime("%Y-%m") for fecha in fechas[corte:]})),
                "dias_con_ventas_entrenamiento": ventas_entrenamiento,
                "dias_con_ventas_evaluacion": ventas_evaluacion,
                "salidas_duplicadas_excluidas": excluidos[codigo]["DUPLICADO"],
                "salidas_pendientes_excluidas": excluidos[codigo]["PENDIENTE_REVISION"],
                "seleccion": seleccion,
                "limitaciones": "; ".join(limites),
            })
    return filas, fechas[corte - 1], fechas[corte]


def main():
    parser = argparse.ArgumentParser(description="Compara pronósticos diarios de salidas por repuesto")
    parser.add_argument("--entrada", type=Path, default=FUENTE)
    parser.add_argument("--salida", type=Path, default=Path(__file__).with_name("comparacion_pronosticos.csv"))
    parser.add_argument("--dias-prueba", type=int, default=5)
    args = parser.parse_args()
    filas, ultimo_entrenamiento, primera_evaluacion = evaluar(args.entrada, args.dias_prueba)
    with open(args.salida, "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=filas[0].keys(), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"Entrenamiento hasta {ultimo_entrenamiento}; evaluación desde {primera_evaluacion}")
    print(f"{len(filas) // len(METODOS)} repuestos, {len(METODOS)} métodos; resultado: {args.salida}")
    for fila in filas:
        print(f"{fila['codigo_unico']} {fila['metodo']}: MAE={fila['mae']}, n={fila['periodos_evaluados']}, selección={fila['seleccion']}")


if __name__ == "__main__":
    main()
