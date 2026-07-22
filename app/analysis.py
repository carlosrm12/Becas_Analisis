"""
analysis.py
-----------
Motor de análisis. Toma el Excel ya cargado (io_excel.py) y el resultado del
mapeo contra el diccionario de preguntas (schema.py), y produce:

1. Un DataFrame "limpio" con columnas renombradas a los IDs de pregunta y
   valores ya convertidos al tipo correcto (estrellas -> número, texto -> N/A
   para metadatos, etc.)
2. Indicadores: perfil de becarios, resumen por pregunta (general y por tipo
   de beca), índices compuestos, relaciones entre variables y casos
   prioritarios de seguimiento.

Ninguna función de este módulo debe referirse a un nombre de columna de Excel
directamente: todo se hace a través de los IDs del diccionario de preguntas,
para que el motor no dependa de cómo luzca el Excel exportado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .schema import DiccionarioPreguntas, Pregunta, TipoPregunta
from .io_excel import ResultadoMapeo

ID_CONSENTIMIENTO = "q01_consentimiento"
ID_CEDULA = "q02_cedula"
ID_TIPO_BECA = "q03_tipo_beca"


# ---------------------------------------------------------------------------
# 1. Construcción del DataFrame analítico
# ---------------------------------------------------------------------------

def construir_dataframe_analitico(
    df_original: pd.DataFrame,
    resultado_mapeo: ResultadoMapeo,
    diccionario: DiccionarioPreguntas,
) -> pd.DataFrame:
    """Devuelve un nuevo DataFrame con una columna por cada pregunta mapeada
    (nombrada con el id de la pregunta) y los valores ya convertidos según
    su tipo. Las preguntas ausentes en este Excel simplemente no aparecen."""

    columnas: dict[str, pd.Series] = {}

    for id_pregunta, nombre_columna in resultado_mapeo.mapeo_ok.items():
        pregunta = diccionario.por_id(id_pregunta)
        serie_original = df_original[nombre_columna]
        columnas[id_pregunta] = _convertir_serie(serie_original, pregunta)

    return pd.DataFrame(columnas)


def _convertir_serie(serie: pd.Series, pregunta: Pregunta) -> pd.Series:
    if pregunta.tipo == TipoPregunta.LIKERT:
        return serie.apply(_parsear_likert)
    if pregunta.tipo == TipoPregunta.NUMERICA:
        return pd.to_numeric(serie, errors="coerce")
    if pregunta.tipo == TipoPregunta.MULTISELECCION:
        return serie.apply(_parsear_multiseleccion)
    # categórica, texto_libre, metadato: se dejan como texto, solo se limpian espacios
    return serie.apply(lambda v: v.strip() if isinstance(v, str) else v)


def _parsear_likert(valor) -> float:
    """Convierte '★★★★' -> 4.0. Si ya viene como número (1-5), lo respeta."""
    if pd.isna(valor):
        return np.nan
    texto = str(valor).strip()
    if "★" in texto:
        return float(texto.count("★"))
    try:
        return float(texto)
    except ValueError:
        return np.nan


def _parsear_multiseleccion(valor) -> list[str]:
    if pd.isna(valor):
        return []
    partes = [p.strip() for p in str(valor).split(";")]
    return [p for p in partes if p]


def invertir_likert(serie: pd.Series) -> pd.Series:
    """Invierte una escala Likert 1-5 (1<->5, 2<->4, 3 igual), para preguntas
    marcadas como 'invertida' en el diccionario (ej. estrés financiero),
    de forma que un valor más alto siempre signifique 'más impacto positivo'
    en los índices compuestos."""
    return 6 - serie


# ---------------------------------------------------------------------------
# 2. Filtros y calidad de datos (consentimiento, duplicados)
# ---------------------------------------------------------------------------

def filtrar_por_consentimiento(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Excluye filas donde el consentimiento no fue afirmativo.
    Devuelve el DataFrame filtrado y cuántas filas se excluyeron."""
    if ID_CONSENTIMIENTO not in df.columns:
        return df, 0
    mascara = df[ID_CONSENTIMIENTO].astype(str).str.strip().str.lower() == "si"
    excluidas = (~mascara).sum()
    return df[mascara].copy(), int(excluidas)


@dataclass
class ResultadoDuplicados:
    filas_duplicadas: pd.DataFrame
    cedulas_repetidas: list[str] = field(default_factory=list)


def detectar_duplicados(df: pd.DataFrame) -> ResultadoDuplicados:
    """Detecta respuestas repetidas del mismo estudiante (misma cédula)."""
    if ID_CEDULA not in df.columns:
        return ResultadoDuplicados(filas_duplicadas=df.iloc[0:0])
    mascara = df[ID_CEDULA].duplicated(keep=False) & df[ID_CEDULA].notna()
    filas = df[mascara]
    cedulas = sorted(filas[ID_CEDULA].dropna().unique().tolist())
    return ResultadoDuplicados(filas_duplicadas=filas, cedulas_repetidas=cedulas)


# ---------------------------------------------------------------------------
# 3. Perfil de becarios
# ---------------------------------------------------------------------------

def perfil_becarios(df: pd.DataFrame, diccionario: DiccionarioPreguntas) -> dict[str, pd.Series]:
    """Frecuencias (conteo y %) de cada pregunta categórica de la sección
    'Perfil del Becario Activo' (tipo de beca, semestre, ocupación del jefe
    de hogar). Devuelve un diccionario id_pregunta -> Serie con el % por
    categoría, ordenado de mayor a menor."""
    resultado = {}
    for pregunta in diccionario.activas():
        if pregunta.seccion != "Perfil del Becario Activo":
            continue
        if pregunta.tipo != TipoPregunta.CATEGORICA:
            continue
        if pregunta.id not in df.columns:
            continue
        conteo = df[pregunta.id].value_counts(dropna=True)
        porcentaje = (conteo / conteo.sum() * 100).round(1)
        resultado[pregunta.id] = porcentaje.sort_values(ascending=False)
    return resultado


# ---------------------------------------------------------------------------
# 4. Resumen por pregunta (general y segmentado por tipo de beca)
# ---------------------------------------------------------------------------

@dataclass
class ResumenPregunta:
    id: str
    texto_pregunta: str
    tipo: TipoPregunta
    n: int
    general: dict                       # media/distribución general, según el tipo
    por_tipo_beca: dict[str, dict]      # tipo_beca -> mismo formato que 'general'


def resumen_por_pregunta(df: pd.DataFrame, diccionario: DiccionarioPreguntas) -> list[ResumenPregunta]:
    """Calcula un resumen descriptivo por cada pregunta activa (excluyendo
    metadatos y texto libre), tanto general como desglosado por tipo de beca
    -- el corte de comparación principal del informe."""
    resultados = []
    tiene_segmento = ID_TIPO_BECA in df.columns

    for pregunta in diccionario.activas():
        if pregunta.tipo in (TipoPregunta.METADATO, TipoPregunta.TEXTO_LIBRE):
            continue
        if pregunta.id not in df.columns:
            continue

        general = _describir_columna(df[pregunta.id], pregunta)

        por_tipo_beca = {}
        if tiene_segmento:
            for tipo_beca, sub_df in df.groupby(ID_TIPO_BECA):
                por_tipo_beca[tipo_beca] = _describir_columna(sub_df[pregunta.id], pregunta)

        resultados.append(ResumenPregunta(
            id=pregunta.id,
            texto_pregunta=pregunta.texto_pregunta,
            tipo=pregunta.tipo,
            n=int(df[pregunta.id].notna().sum()),
            general=general,
            por_tipo_beca=por_tipo_beca,
        ))

    return resultados


def _describir_columna(serie: pd.Series, pregunta: Pregunta) -> dict:
    if pregunta.tipo in (TipoPregunta.LIKERT, TipoPregunta.NUMERICA):
        limpio = pd.to_numeric(serie, errors="coerce").dropna()
        if limpio.empty:
            return {"n": 0, "media": None, "mediana": None, "desv_std": None}
        return {
            "n": int(limpio.size),
            "media": round(float(limpio.mean()), 2),
            "mediana": float(limpio.median()),
            "desv_std": round(float(limpio.std()), 2) if limpio.size > 1 else 0.0,
        }

    if pregunta.tipo == TipoPregunta.CATEGORICA:
        conteo = serie.value_counts(dropna=True)
        total = conteo.sum()
        if total == 0:
            return {"n": 0, "distribucion": {}}
        return {"n": int(total), "distribucion": (conteo / total * 100).round(1).to_dict()}

    if pregunta.tipo == TipoPregunta.MULTISELECCION:
        todas = [opcion for lista in serie.dropna() for opcion in lista]
        if not todas:
            return {"n": 0, "distribucion": {}}
        conteo = pd.Series(todas).value_counts()
        # % sobre el número de respondentes (una persona puede elegir varias opciones)
        return {"n": int(serie.notna().sum()), "distribucion": (conteo / serie.notna().sum() * 100).round(1).to_dict()}

    return {}


# ---------------------------------------------------------------------------
# 5. Índices compuestos
# ---------------------------------------------------------------------------

@dataclass
class DefinicionIndice:
    id: str
    nombre: str
    ids_preguntas: list[str]


INDICES_POR_DEFECTO = [
    DefinicionIndice(
        id="indice_economico_academico",
        nombre="Impacto Económico y Académico",
        ids_preguntas=["q06_promedio", "q07_apoyo_evita_abandono", "q08_horas_reducidas", "q09_impacto_hogar"],
    ),
    DefinicionIndice(
        id="indice_bienestar_institucional",
        nombre="Bienestar y Pertenencia Institucional",
        ids_preguntas=["q11_relacion_companeros", "q13_estres_financiero", "q14_pertenencia"],
    ),
]


def calcular_indices(
    df: pd.DataFrame,
    diccionario: DiccionarioPreguntas,
    definiciones: list[DefinicionIndice] = INDICES_POR_DEFECTO,
) -> pd.DataFrame:
    """Calcula cada índice compuesto como el promedio (normalizado 0-100) de
    sus preguntas componentes, invirtiendo automáticamente las que están
    marcadas como 'invertida' en el diccionario. Solo usa preguntas Likert
    o numéricas -- si el índice mezcla escalas distintas (ej. promedio 0-20
    con Likert 1-5) cada componente se normaliza a 0-100 antes de promediar.
    Devuelve un DataFrame con una columna por índice, mismo índice de filas que df."""
    columnas_indices = {}

    for definicion in definiciones:
        componentes_normalizados = []
        for id_pregunta in definicion.ids_preguntas:
            pregunta = diccionario.por_id(id_pregunta)
            if pregunta is None or id_pregunta not in df.columns:
                continue  # componente ausente (pregunta eliminada del Forms) -> se ignora, no rompe el índice
            valores = pd.to_numeric(df[id_pregunta], errors="coerce")
            if pregunta.invertida and pregunta.tipo == TipoPregunta.LIKERT:
                valores = invertir_likert(valores)
            normalizado = _normalizar_0_100(valores, pregunta)
            componentes_normalizados.append(normalizado)

        if componentes_normalizados:
            columnas_indices[definicion.id] = pd.concat(componentes_normalizados, axis=1).mean(axis=1, skipna=True)

    return pd.DataFrame(columnas_indices)


def _normalizar_0_100(valores: pd.Series, pregunta: Pregunta) -> pd.Series:
    if pregunta.tipo == TipoPregunta.LIKERT:
        return (valores - 1) / 4 * 100  # escala 1-5 -> 0-100
    if pregunta.id == "q06_promedio":
        return valores / 20 * 100  # escala 0-20 -> 0-100
    # numérica sin escala fija conocida (ej. horas reducidas): normalizar por el máximo observado
    maximo = valores.max()
    if pd.isna(maximo) or maximo == 0:
        return valores * 0
    return valores / maximo * 100


# ---------------------------------------------------------------------------
# 6. Relaciones entre variables
# ---------------------------------------------------------------------------

@dataclass
class RelacionNotable:
    id_a: str
    id_b: str
    correlacion: float
    n: int


def relaciones_notables(
    df: pd.DataFrame,
    diccionario: DiccionarioPreguntas,
    umbral: float = 0.3,
) -> list[RelacionNotable]:
    """Calcula correlaciones entre todas las preguntas Likert/numéricas
    (con las invertidas ya corregidas) y devuelve solo los pares con una
    relación igual o más fuerte que el umbral -- para no saturar el informe
    con relaciones débiles o irrelevantes."""
    ids_numericos = [
        p.id for p in diccionario.activas()
        if p.tipo in (TipoPregunta.LIKERT, TipoPregunta.NUMERICA) and p.id in df.columns
    ]

    datos = {}
    for id_ in ids_numericos:
        pregunta = diccionario.por_id(id_)
        valores = pd.to_numeric(df[id_], errors="coerce")
        if pregunta.invertida and pregunta.tipo == TipoPregunta.LIKERT:
            valores = invertir_likert(valores)
        datos[id_] = valores

    matriz = pd.DataFrame(datos).corr()

    relaciones = []
    vistos = set()
    for id_a in matriz.columns:
        for id_b in matriz.columns:
            if id_a == id_b or (id_b, id_a) in vistos:
                continue
            vistos.add((id_a, id_b))
            valor = matriz.loc[id_a, id_b]
            if pd.isna(valor) or abs(valor) < umbral:
                continue
            n_conjunto = pd.DataFrame({id_a: datos[id_a], id_b: datos[id_b]}).dropna().shape[0]
            relaciones.append(RelacionNotable(id_a=id_a, id_b=id_b, correlacion=round(float(valor), 2), n=n_conjunto))

    relaciones.sort(key=lambda r: abs(r.correlacion), reverse=True)
    return relaciones


# ---------------------------------------------------------------------------
# 7. Casos prioritarios de seguimiento
# ---------------------------------------------------------------------------

def casos_prioritarios(
    df: pd.DataFrame,
    umbral_promedio_bajo: float = 14.0,
    umbral_estres_alto: float = 4.0,
) -> pd.DataFrame:
    """Marca estudiantes que combinan señales de riesgo: promedio bajo,
    estrés financiero alto, y ninguna vinculación institucional.
    Devuelve las filas originales con columnas booleanas de cada bandera."""
    banderas = pd.DataFrame(index=df.index)

    if "q06_promedio" in df.columns:
        banderas["promedio_bajo"] = pd.to_numeric(df["q06_promedio"], errors="coerce") < umbral_promedio_bajo
    else:
        banderas["promedio_bajo"] = False

    if "q13_estres_financiero" in df.columns:
        banderas["estres_alto"] = pd.to_numeric(df["q13_estres_financiero"], errors="coerce") >= umbral_estres_alto
    else:
        banderas["estres_alto"] = False

    if "q10_vinculacion" in df.columns:
        banderas["sin_vinculacion"] = df["q10_vinculacion"].apply(
            lambda lista: isinstance(lista, list) and "No me he vinculado" in lista
        )
    else:
        banderas["sin_vinculacion"] = False

    banderas["cantidad_senales"] = banderas[["promedio_bajo", "estres_alto", "sin_vinculacion"]].sum(axis=1)

    prioritarios = banderas[banderas["cantidad_senales"] >= 2]
    columnas_a_mostrar = [c for c in ["q02_cedula", "q06_promedio", "q13_estres_financiero", "q10_vinculacion"] if c in df.columns]
    return df.loc[prioritarios.index, columnas_a_mostrar].join(prioritarios)
