"""Corre en orden la generación de datos ficticios, la carga de HU-30 y el registro de costos de HU-31.

Uso: python ejecutar_todo.py [--semilla N] [--fecha-actualizacion AAAA-MM-DD]
Funciona desde cualquier carpeta y en Windows, Linux o Mac.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PASOS = ["genera_datos_sinteticos.py", "carga_historico.py", "cotizaciones_costos.py"]


def main():
    for i, paso in enumerate(PASOS):
        extra = sys.argv[1:] if i == 0 else []
        print(f"[{i + 1}/{len(PASOS)}] {paso}")
        r = subprocess.run([sys.executable, str(AQUI / paso)] + extra)
        if r.returncode != 0:
            sys.exit(f"Falló {paso} (código {r.returncode}); no se siguió con los pasos restantes")
    print("Listo: sintetico/ y hu31_costos_importacion.csv actualizados")


if __name__ == "__main__":
    main()
