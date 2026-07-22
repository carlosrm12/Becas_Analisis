"""
main_window.py
--------------
Ventana principal de la aplicación. Flujo:

1. El usuario carga un Excel (Archivo > Cargar Excel...).
2. Si el mapeo contra el diccionario de preguntas requiere resolución
   (columnas nuevas o preguntas ausentes), se abre el diálogo correspondiente.
3. Se corre el análisis completo y se muestra en pestañas.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..analysis import (
    ID_TIPO_BECA,
    calcular_indices,
    casos_prioritarios,
    construir_dataframe_analitico,
    detectar_duplicados,
    filtrar_por_consentimiento,
    perfil_becarios,
    relaciones_notables,
    resumen_por_pregunta,
)
from ..io_excel import cargar_respuestas, mapear_columnas
from ..schema import DiccionarioPreguntas, TipoPregunta
from .mapping_dialog import DialogoResolucionMapeo

RUTA_PLANTILLA_DEFAULT = Path(__file__).resolve().parent.parent.parent / "config" / "plantilla_default.json"
RUTA_PLANTILLA_LOCAL = Path(__file__).resolve().parent.parent.parent / "config" / "plantilla_local.json"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seguimiento del Impacto de Becas — UCE")
        self.resize(1150, 780)

        self.diccionario = self._cargar_diccionario_inicial()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._mostrar_mensaje_inicial()

        self._crear_menu()

    # ------------------------------------------------------------------
    # Configuración inicial
    # ------------------------------------------------------------------

    def _cargar_diccionario_inicial(self) -> DiccionarioPreguntas:
        if RUTA_PLANTILLA_LOCAL.exists():
            return DiccionarioPreguntas.cargar(RUTA_PLANTILLA_LOCAL)
        return DiccionarioPreguntas.cargar(RUTA_PLANTILLA_DEFAULT)

    def _crear_menu(self):
        menu_archivo = self.menuBar().addMenu("&Archivo")
        menu_archivo.addAction("Cargar Excel...", self.cargar_excel)
        menu_archivo.addSeparator()
        menu_archivo.addAction("Salir", self.close)

        menu_diccionario = self.menuBar().addMenu("&Diccionario de preguntas")
        menu_diccionario.addAction("Ver preguntas activas", self.mostrar_diccionario)

    def _mostrar_mensaje_inicial(self):
        self.tabs.clear()
        aviso = QWidget()
        layout = QVBoxLayout(aviso)
        layout.addWidget(QLabel(
            "Usa 'Archivo > Cargar Excel...' para analizar las respuestas del formulario."
        ))
        self.tabs.addTab(aviso, "Inicio")

    # ------------------------------------------------------------------
    # Carga y mapeo
    # ------------------------------------------------------------------

    def cargar_excel(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Excel de respuestas", "", "Archivos Excel (*.xlsx)"
        )
        if not ruta:
            return

        try:
            df_original = cargar_respuestas(ruta)
        except Exception as exc:  # noqa: BLE001 - queremos mostrar cualquier error de lectura al usuario
            QMessageBox.critical(self, "Error al cargar el archivo", str(exc))
            return

        resultado_mapeo = mapear_columnas(df_original, self.diccionario)

        if resultado_mapeo.requiere_resolucion:
            dialogo = DialogoResolucionMapeo(resultado_mapeo, self.diccionario, self)
            if dialogo.exec() != DialogoResolucionMapeo.Accepted:
                return  # el usuario canceló, no se analiza nada

            if dialogo.debe_guardar_plantilla():
                RUTA_PLANTILLA_LOCAL.parent.mkdir(parents=True, exist_ok=True)
                self.diccionario.guardar(RUTA_PLANTILLA_LOCAL)

            # Volver a mapear ya con las preguntas nuevas agregadas al diccionario
            resultado_mapeo = mapear_columnas(df_original, self.diccionario)

        self._analizar_y_mostrar(df_original, resultado_mapeo)

    def mostrar_diccionario(self):
        tabla = QTableWidget()
        preguntas = self.diccionario.activas()
        tabla.setRowCount(len(preguntas))
        tabla.setColumnCount(4)
        tabla.setHorizontalHeaderLabels(["ID", "Pregunta", "Tipo", "Sección"])
        for fila, pregunta in enumerate(preguntas):
            tabla.setItem(fila, 0, QTableWidgetItem(pregunta.id))
            tabla.setItem(fila, 1, QTableWidgetItem(pregunta.texto_pregunta))
            tabla.setItem(fila, 2, QTableWidgetItem(pregunta.tipo.value))
            tabla.setItem(fila, 3, QTableWidgetItem(pregunta.seccion))
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        indice_existente = self._indice_tab("Diccionario de preguntas")
        if indice_existente is not None:
            self.tabs.removeTab(indice_existente)
        self.tabs.addTab(tabla, "Diccionario de preguntas")
        self.tabs.setCurrentWidget(tabla)

    def _indice_tab(self, titulo: str) -> int | None:
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == titulo:
                return i
        return None

    # ------------------------------------------------------------------
    # Análisis y presentación
    # ------------------------------------------------------------------

    def _analizar_y_mostrar(self, df_original, resultado_mapeo):
        df = construir_dataframe_analitico(df_original, resultado_mapeo, self.diccionario)
        df_filtrado, excluidos_consentimiento = filtrar_por_consentimiento(df)
        duplicados = detectar_duplicados(df_filtrado)

        if duplicados.cedulas_repetidas:
            QMessageBox.warning(
                self,
                "Se encontraron respuestas duplicadas",
                f"Hay {len(duplicados.cedulas_repetidas)} cédula(s) con más de una respuesta. "
                "Por ahora se incluyen todas en el análisis; revísalas manualmente si es necesario.",
            )

        self.tabs.clear()
        self._tab_resumen(df_original, df_filtrado, excluidos_consentimiento, duplicados)
        self._tab_perfil(df_filtrado)
        self._tab_seccion(df_filtrado, "Impacto Económico y Eficiencia Académica")
        self._tab_seccion(df_filtrado, "Desarrollo Integral y Entorno Universitario")
        self._tab_seccion(df_filtrado, "Pertenencia y Bienestar Institucional")
        self._tab_indices(df_filtrado)
        self._tab_relaciones(df_filtrado)
        self._tab_casos_prioritarios(df_filtrado)

    def _tab_resumen(self, df_original, df_filtrado, excluidos, duplicados):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"<h2>Resumen de la carga</h2>"))
        layout.addWidget(QLabel(f"Respuestas totales en el archivo: {len(df_original)}"))
        layout.addWidget(QLabel(f"Excluidas por no otorgar consentimiento: {excluidos}"))
        layout.addWidget(QLabel(f"Respuestas incluidas en el análisis: {len(df_filtrado)}"))
        layout.addWidget(QLabel(f"Cédulas con más de una respuesta: {len(duplicados.cedulas_repetidas)}"))
        layout.addStretch()
        self.tabs.addTab(widget, "Resumen")

    def _tab_perfil(self, df):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        perfil = perfil_becarios(df, self.diccionario)

        if ID_TIPO_BECA in perfil:
            layout.addWidget(QLabel("<b>Distribución por tipo de beca</b>"))
            layout.addWidget(self._grafico_barras(perfil[ID_TIPO_BECA]))

        for id_pregunta, serie in perfil.items():
            if id_pregunta == ID_TIPO_BECA:
                continue
            pregunta = self.diccionario.por_id(id_pregunta)
            layout.addWidget(QLabel(f"<b>{pregunta.texto_pregunta}</b>"))
            layout.addWidget(self._tabla_desde_serie(serie))

        self.tabs.addTab(_envolver_en_scroll(widget), "Perfil")

    def _tab_seccion(self, df, nombre_seccion: str):
        resumenes = [r for r in resumen_por_pregunta(df, self.diccionario) if self.diccionario.por_id(r.id).seccion == nombre_seccion]
        if not resumenes:
            return

        widget = QWidget()
        layout = QVBoxLayout(widget)

        for resumen in resumenes:
            texto_nota = " (escala invertida: puntaje alto = negativo)" if self.diccionario.por_id(resumen.id).invertida else ""
            layout.addWidget(QLabel(f"<b>{resumen.texto_pregunta}</b>{texto_nota} — n={resumen.n}"))
            layout.addWidget(self._tabla_resumen_pregunta(resumen))

        self.tabs.addTab(_envolver_en_scroll(widget), nombre_seccion)

    def _tab_indices(self, df):
        indices = calcular_indices(df, self.diccionario)
        if indices.empty:
            return
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h3>Índices compuestos (escala 0-100)</h3>"))
        for columna in indices.columns:
            layout.addWidget(QLabel(f"{columna}: promedio {indices[columna].mean():.1f}"))
        self.tabs.addTab(widget, "Índices")

    def _tab_relaciones(self, df):
        relaciones = relaciones_notables(df, self.diccionario)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        if not relaciones:
            layout.addWidget(QLabel("No se encontraron relaciones notables entre las preguntas con este umbral."))
        else:
            tabla = QTableWidget()
            tabla.setRowCount(len(relaciones))
            tabla.setColumnCount(4)
            tabla.setHorizontalHeaderLabels(["Pregunta A", "Pregunta B", "Correlación", "n"])
            for fila, r in enumerate(relaciones):
                pa = self.diccionario.por_id(r.id_a)
                pb = self.diccionario.por_id(r.id_b)
                tabla.setItem(fila, 0, QTableWidgetItem(pa.texto_pregunta if pa else r.id_a))
                tabla.setItem(fila, 1, QTableWidgetItem(pb.texto_pregunta if pb else r.id_b))
                tabla.setItem(fila, 2, QTableWidgetItem(str(r.correlacion)))
                tabla.setItem(fila, 3, QTableWidgetItem(str(r.n)))
            tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(tabla)
        self.tabs.addTab(widget, "Relaciones")

    def _tab_casos_prioritarios(self, df):
        casos = casos_prioritarios(df)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"Estudiantes con 2 o más señales de riesgo combinadas: {len(casos)}"))
        if not casos.empty:
            tabla = QTableWidget()
            tabla.setRowCount(len(casos))
            tabla.setColumnCount(len(casos.columns))
            tabla.setHorizontalHeaderLabels([str(c) for c in casos.columns])
            for fila_i, (_, fila) in enumerate(casos.iterrows()):
                for col_i, valor in enumerate(fila):
                    tabla.setItem(fila_i, col_i, QTableWidgetItem(str(valor)))
            tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(tabla)
        self.tabs.addTab(widget, "Casos prioritarios")

    # ------------------------------------------------------------------
    # Utilidades de presentación
    # ------------------------------------------------------------------

    def _tabla_desde_serie(self, serie) -> QTableWidget:
        tabla = QTableWidget()
        tabla.setRowCount(len(serie))
        tabla.setColumnCount(2)
        tabla.setHorizontalHeaderLabels(["Categoría", "%"])
        for fila, (categoria, valor) in enumerate(serie.items()):
            tabla.setItem(fila, 0, QTableWidgetItem(str(categoria)))
            tabla.setItem(fila, 1, QTableWidgetItem(f"{valor}%"))
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabla.setMaximumHeight(150)
        return tabla

    def _tabla_resumen_pregunta(self, resumen) -> QTableWidget:
        columnas_segmento = list(resumen.por_tipo_beca.keys())
        tabla = QTableWidget()
        tabla.setRowCount(1 + len(columnas_segmento))
        tabla.setColumnCount(4)
        tabla.setHorizontalHeaderLabels(["Grupo", "n", "Media", "Desv. estándar"])

        def _fila(nombre, datos, indice):
            tabla.setItem(indice, 0, QTableWidgetItem(nombre))
            tabla.setItem(indice, 1, QTableWidgetItem(str(datos.get("n", "-"))))
            tabla.setItem(indice, 2, QTableWidgetItem(str(datos.get("media", datos.get("distribucion", "-")))))
            tabla.setItem(indice, 3, QTableWidgetItem(str(datos.get("desv_std", "-"))))

        _fila("General", resumen.general, 0)
        for i, tipo_beca in enumerate(columnas_segmento, start=1):
            _fila(tipo_beca, resumen.por_tipo_beca[tipo_beca], i)

        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabla.setMaximumHeight(150)
        return tabla

    def _grafico_barras(self, serie) -> FigureCanvasQTAgg:
        figura = Figure(figsize=(5, 3))
        ejes = figura.add_subplot(111)
        ejes.bar(serie.index.astype(str), serie.values)
        ejes.set_ylabel("%")
        ejes.tick_params(axis="x", rotation=20)
        figura.tight_layout()
        return FigureCanvasQTAgg(figura)


def _envolver_en_scroll(widget: QWidget) -> QWidget:
    from PySide6.QtWidgets import QScrollArea

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    return scroll
