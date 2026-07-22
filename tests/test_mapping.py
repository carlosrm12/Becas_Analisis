"""
Prueba manual (no automatizada con pytest todavía) del paso de carga + mapeo.
Ejecutar desde la raíz del proyecto:

    python tests/test_mapping.py "ruta/al/excel.xlsx"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schema import DiccionarioPreguntas
from app.io_excel import cargar_respuestas, mapear_columnas, resumen_legible


def main():
    if len(sys.argv) < 2:
        print("Uso: python tests/test_mapping.py <ruta_excel>")
        sys.exit(1)

    ruta_excel = sys.argv[1]
    ruta_plantilla = Path(__file__).resolve().parent.parent / "config" / "plantilla_default.json"

    diccionario = DiccionarioPreguntas.cargar(ruta_plantilla)
    print(f"Diccionario cargado: {len(diccionario.preguntas)} preguntas ({len(diccionario.activas())} activas)\n")

    df = cargar_respuestas(ruta_excel)
    print(f"Excel cargado: {len(df)} respuestas, {len(df.columns)} columnas\n")

    resultado = mapear_columnas(df, diccionario)
    print(resumen_legible(resultado, diccionario))


if __name__ == "__main__":
    main()
