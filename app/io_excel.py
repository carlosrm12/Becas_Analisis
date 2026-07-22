"""
io_excel.py
-----------
Carga el Excel exportado desde Microsoft Forms y lo compara contra el
diccionario de preguntas vigente (schema.py).

El mapeo es SIEMPRE por texto de encabezado, nunca por posición de columna,
para que no se rompa si el orden de las columnas cambia entre exportaciones.

Devuelve un ResultadoMapeo que distingue tres casos:
- columnas que sí coinciden con una pregunta conocida (mapeo_ok)
- columnas del Excel que no coinciden con ninguna pregunta conocida
  (columnas_sin_clasificar) -> pregunta nueva en el formulario (UC3)
- preguntas conocidas que no aparecen en este Excel
  (preguntas_ausentes) -> pregunta eliminada del formulario (UC4)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .schema import DiccionarioPreguntas, Pregunta, _normalizar


@dataclass
class ResultadoMapeo:
    mapeo_ok: dict[str, str] = field(default_factory=dict)          # id_pregunta -> nombre_columna_excel
    columnas_sin_clasificar: list[str] = field(default_factory=list)  # encabezados del excel sin pregunta conocida
    preguntas_ausentes: list[str] = field(default_factory=list)       # ids de preguntas activas que no aparecieron

    @property
    def requiere_resolucion(self) -> bool:
        return bool(self.columnas_sin_clasificar or self.preguntas_ausentes)


def cargar_respuestas(ruta_excel: str) -> pd.DataFrame:
    """Carga la hoja de respuestas de Forms. Devuelve un DataFrame con
    los encabezados originales, sin ninguna transformación todavía."""
    df = pd.read_excel(ruta_excel, dtype=str)
    # Los encabezados de Forms a veces traen espacios/saltos de línea de más.
    df.columns = [str(c).strip() for c in df.columns]
    return df


def mapear_columnas(df: pd.DataFrame, diccionario: DiccionarioPreguntas) -> ResultadoMapeo:
    """Compara los encabezados del Excel cargado contra el diccionario
    de preguntas activo y clasifica cada columna."""
    resultado = ResultadoMapeo()

    columnas_excel = list(df.columns)
    columnas_usadas: set[str] = set()

    for pregunta in diccionario.activas():
        columna_encontrada = _buscar_columna(pregunta, columnas_excel)
        if columna_encontrada is not None:
            resultado.mapeo_ok[pregunta.id] = columna_encontrada
            columnas_usadas.add(columna_encontrada)
        else:
            resultado.preguntas_ausentes.append(pregunta.id)

    for columna in columnas_excel:
        if columna not in columnas_usadas:
            resultado.columnas_sin_clasificar.append(columna)

    return resultado


def _buscar_columna(pregunta: Pregunta, columnas_excel: list[str]) -> str | None:
    objetivo = _normalizar(pregunta.texto_columna)
    for columna in columnas_excel:
        if _normalizar(columna) == objetivo:
            return columna
    return None


def resumen_legible(resultado: ResultadoMapeo, diccionario: DiccionarioPreguntas) -> str:
    """Genera un resumen en texto plano del resultado del mapeo,
    pensado para mostrarse en la UI o en consola durante pruebas."""
    lineas = []
    lineas.append(f"Preguntas mapeadas correctamente: {len(resultado.mapeo_ok)}")

    if resultado.columnas_sin_clasificar:
        lineas.append(f"\nColumnas SIN CLASIFICAR ({len(resultado.columnas_sin_clasificar)}):")
        for col in resultado.columnas_sin_clasificar:
            lineas.append(f"  - '{col}'")

    if resultado.preguntas_ausentes:
        lineas.append(f"\nPreguntas conocidas AUSENTES en este archivo ({len(resultado.preguntas_ausentes)}):")
        for pid in resultado.preguntas_ausentes:
            p = diccionario.por_id(pid)
            texto = p.texto_pregunta if p else pid
            lineas.append(f"  - [{pid}] {texto}")

    if not resultado.requiere_resolucion:
        lineas.append("\nTodo coincide con el diccionario vigente. Listo para analizar.")

    return "\n".join(lineas)
