"""
schema.py
---------
Define el "diccionario de preguntas": el catálogo editable que le dice al
resto del programa qué preguntas existen en el formulario, de qué tipo son,
a qué sección pertenecen y cómo deben tratarse en el análisis.

El motor de análisis (analysis.py) NUNCA debe tener nombres de preguntas o
columnas escritos directamente en su código. Todo pasa por este diccionario,
para que el programa siga funcionando si el formulario de Microsoft Forms
cambia (se agregan, eliminan o renombran preguntas).

El diccionario se guarda y carga como un archivo JSON (ver config/plantilla_default.json).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class TipoPregunta(str, Enum):
    METADATO = "metadato"              # ID, correo, cédula, nombre, timestamps -> nunca entra al análisis agregado
    CATEGORICA = "categorica"          # opción única (ej. tipo de beca)
    NUMERICA = "numerica"              # promedio, horas trabajadas
    LIKERT = "likert"                  # escala 1-5
    MULTISELECCION = "multiseleccion"  # varias opciones separadas por ';'
    TEXTO_LIBRE = "texto_libre"        # respuesta abierta


@dataclass
class Pregunta:
    """Una pregunta del formulario, tal como la conoce el programa."""

    id: str                                  # identificador estable interno, ej. "q07_apoyo_economico"
    texto_columna: str                       # encabezado EXACTO tal como aparece en el Excel exportado
    texto_pregunta: str                      # texto legible de la pregunta, para mostrar en el informe
    tipo: TipoPregunta
    seccion: str                             # ej. "Perfil del Becario", "Impacto Económico y Eficiencia Académica"
    invertida: bool = False                  # True si un puntaje alto es negativo (ej. estrés)
    opciones: list[str] = field(default_factory=list)   # opciones válidas, solo para categórica/multiselección
    grupo: Optional[str] = None              # id del grupo si es sub-ítem de una pregunta matriz (ej. Q12)
    activa: bool = True                      # False = archivada, se ignora en análisis nuevos pero se conserva el histórico

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        return d

    @staticmethod
    def from_dict(d: dict) -> "Pregunta":
        d = dict(d)
        d["tipo"] = TipoPregunta(d["tipo"])
        return Pregunta(**d)


@dataclass
class DiccionarioPreguntas:
    """Colección completa de preguntas conocidas por el programa."""

    preguntas: list[Pregunta] = field(default_factory=list)

    # ---------- carga / guardado ----------

    @staticmethod
    def cargar(ruta: str | Path) -> "DiccionarioPreguntas":
        ruta = Path(ruta)
        data = json.loads(ruta.read_text(encoding="utf-8"))
        preguntas = [Pregunta.from_dict(p) for p in data.get("preguntas", [])]
        return DiccionarioPreguntas(preguntas=preguntas)

    def guardar(self, ruta: str | Path) -> None:
        ruta = Path(ruta)
        data = {"preguntas": [p.to_dict() for p in self.preguntas]}
        ruta.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- utilidades ----------

    def activas(self) -> list[Pregunta]:
        return [p for p in self.preguntas if p.activa]

    def por_id(self, id_: str) -> Optional[Pregunta]:
        return next((p for p in self.preguntas if p.id == id_), None)

    def por_texto_columna(self, texto: str) -> Optional[Pregunta]:
        texto_norm = _normalizar(texto)
        for p in self.preguntas:
            if _normalizar(p.texto_columna) == texto_norm:
                return p
        return None

    def agregar(self, pregunta: Pregunta) -> None:
        if self.por_id(pregunta.id) is not None:
            raise ValueError(f"Ya existe una pregunta con id '{pregunta.id}'")
        self.preguntas.append(pregunta)

    def archivar(self, id_: str) -> None:
        p = self.por_id(id_)
        if p is not None:
            p.activa = False


def _normalizar(texto: str) -> str:
    """Normaliza texto de encabezado para comparar de forma tolerante
    a espacios extra, mayúsculas/minúsculas y saltos de línea."""
    return " ".join(texto.strip().lower().split())
