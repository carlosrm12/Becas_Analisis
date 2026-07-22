"""
mapping_dialog.py
------------------
Diálogo que se muestra cuando el Excel cargado no coincide perfectamente
con el diccionario de preguntas vigente:

- Columnas del Excel que no corresponden a ninguna pregunta conocida
  (el Forms tiene una pregunta nueva) -> el usuario clasifica cada una
  o la marca para ignorar.
- Preguntas conocidas que no aparecieron en este Excel (el Forms perdió
  una pregunta) -> se muestran solo como aviso informativo.

Si el usuario clasifica columnas nuevas, estas se agregan al diccionario
en memoria (y opcionalmente se guardan en el archivo de plantilla local
para que la próxima carga ya las reconozca automáticamente).
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..io_excel import ResultadoMapeo
from ..schema import DiccionarioPreguntas, Pregunta, TipoPregunta

TIPOS_SELECCIONABLES = [
    (TipoPregunta.CATEGORICA, "Categórica (opción única)"),
    (TipoPregunta.NUMERICA, "Numérica"),
    (TipoPregunta.LIKERT, "Escala (Likert 1-5)"),
    (TipoPregunta.MULTISELECCION, "Opción múltiple"),
    (TipoPregunta.TEXTO_LIBRE, "Texto libre"),
    (TipoPregunta.METADATO, "Metadato (ignorar en el análisis)"),
]


class FilaColumnaNueva(QWidget):
    """Una fila del formulario para clasificar una columna sin reconocer."""

    def __init__(self, nombre_columna: str, secciones_existentes: list[str], parent=None):
        super().__init__(parent)
        self.nombre_columna = nombre_columna

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Columna del Excel:</b> {nombre_columna}"))

        fila_1 = QHBoxLayout()
        self.check_ignorar = QCheckBox("Ignorar esta columna (no incluir en el análisis)")
        self.check_ignorar.toggled.connect(self._actualizar_habilitado)
        fila_1.addWidget(self.check_ignorar)
        layout.addLayout(fila_1)

        fila_2 = QHBoxLayout()
        fila_2.addWidget(QLabel("Tipo de pregunta:"))
        self.combo_tipo = QComboBox()
        for tipo, etiqueta in TIPOS_SELECCIONABLES:
            self.combo_tipo.addItem(etiqueta, tipo)
        fila_2.addWidget(self.combo_tipo)

        fila_2.addWidget(QLabel("Sección:"))
        self.combo_seccion = QComboBox()
        self.combo_seccion.setEditable(True)
        for seccion in secciones_existentes:
            self.combo_seccion.addItem(seccion)
        fila_2.addWidget(self.combo_seccion)
        layout.addLayout(fila_2)

        fila_3 = QHBoxLayout()
        fila_3.addWidget(QLabel("Texto de la pregunta (para el informe):"))
        self.texto_pregunta = QLineEdit(nombre_columna)
        fila_3.addWidget(self.texto_pregunta)
        layout.addLayout(fila_3)

        self.check_invertida = QCheckBox("Escala invertida (un puntaje alto es negativo, ej. estrés)")
        layout.addWidget(self.check_invertida)

        linea = QWidget()
        linea.setFixedHeight(1)
        linea.setStyleSheet("background-color: #cccccc;")
        layout.addWidget(linea)

    def _actualizar_habilitado(self, ignorar: bool):
        for widget in (self.combo_tipo, self.combo_seccion, self.texto_pregunta, self.check_invertida):
            widget.setEnabled(not ignorar)

    def a_pregunta(self, id_sugerido: str) -> Pregunta | None:
        if self.check_ignorar.isChecked():
            return None
        tipo = self.combo_tipo.currentData()
        return Pregunta(
            id=id_sugerido,
            texto_columna=self.nombre_columna,
            texto_pregunta=self.texto_pregunta.text().strip() or self.nombre_columna,
            tipo=tipo,
            seccion=self.combo_seccion.currentText().strip() or "Sin sección",
            invertida=self.check_invertida.isChecked(),
        )


class DialogoResolucionMapeo(QDialog):
    def __init__(self, resultado: ResultadoMapeo, diccionario: DiccionarioPreguntas, parent=None):
        super().__init__(parent)
        self.resultado = resultado
        self.diccionario = diccionario
        self.filas_nuevas: list[FilaColumnaNueva] = []

        self.setWindowTitle("El formulario cambió: revisa las diferencias")
        self.resize(700, 600)

        layout_principal = QVBoxLayout(self)

        if resultado.preguntas_ausentes:
            grupo_ausentes = QGroupBox("Preguntas que ya no aparecen en este archivo")
            layout_ausentes = QVBoxLayout(grupo_ausentes)
            layout_ausentes.addWidget(QLabel(
                "Estas preguntas estaban en el diccionario pero no se encontraron en el Excel cargado. "
                "Se omitirán del análisis de esta carga (su historial de rondas anteriores no se pierde)."
            ))
            lista = QListWidget()
            for id_pregunta in resultado.preguntas_ausentes:
                pregunta = diccionario.por_id(id_pregunta)
                texto = pregunta.texto_pregunta if pregunta else id_pregunta
                lista.addItem(f"[{id_pregunta}] {texto}")
            layout_ausentes.addWidget(lista)
            layout_principal.addWidget(grupo_ausentes)

        if resultado.columnas_sin_clasificar:
            grupo_nuevas = QGroupBox("Columnas nuevas sin clasificar")
            layout_nuevas = QVBoxLayout(grupo_nuevas)
            layout_nuevas.addWidget(QLabel(
                "Estas columnas no coinciden con ninguna pregunta conocida. "
                "Clasifica cada una para incluirla en el análisis, o márcala para ignorar."
            ))

            secciones_existentes = sorted({p.seccion for p in diccionario.preguntas})
            area_scroll = QScrollArea()
            area_scroll.setWidgetResizable(True)
            contenedor = QWidget()
            layout_contenedor = QVBoxLayout(contenedor)
            for columna in resultado.columnas_sin_clasificar:
                fila = FilaColumnaNueva(columna, secciones_existentes)
                self.filas_nuevas.append(fila)
                layout_contenedor.addWidget(fila)
            area_scroll.setWidget(contenedor)
            layout_nuevas.addWidget(area_scroll)
            layout_principal.addWidget(grupo_nuevas)

        self.check_guardar_plantilla = QCheckBox(
            "Guardar estas clasificaciones para que la próxima carga ya las reconozca automáticamente"
        )
        self.check_guardar_plantilla.setChecked(True)
        layout_principal.addWidget(self.check_guardar_plantilla)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Ok).setText("Aplicar y continuar")
        botones.accepted.connect(self._aplicar)
        botones.rejected.connect(self.reject)
        layout_principal.addWidget(botones)

        self._debe_guardar_plantilla = False

    def _aplicar(self):
        ids_existentes = {p.id for p in self.diccionario.preguntas}
        for fila in self.filas_nuevas:
            id_sugerido = _generar_id(fila.nombre_columna, ids_existentes)
            pregunta = fila.a_pregunta(id_sugerido)
            if pregunta is not None:
                self.diccionario.agregar(pregunta)
                ids_existentes.add(pregunta.id)

        self._debe_guardar_plantilla = self.check_guardar_plantilla.isChecked()
        self.accept()

    def debe_guardar_plantilla(self) -> bool:
        return self._debe_guardar_plantilla


def _generar_id(texto_columna: str, ids_existentes: set[str]) -> str:
    """Genera un id interno legible a partir del texto de la columna,
    ej. '¿Recibió tutorías?' -> 'q_recibio_tutorias'."""
    base = re.sub(r"[^a-z0-9]+", "_", texto_columna.strip().lower())
    base = re.sub(r"_+", "_", base).strip("_")[:40]
    base = f"q_{base}" if base else "q_nueva_pregunta"

    id_final = base
    contador = 2
    while id_final in ids_existentes:
        id_final = f"{base}_{contador}"
        contador += 1
    return id_final
