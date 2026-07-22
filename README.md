# Becas_Analisis

Programa de escritorio (PySide6) para analizar las respuestas del formulario
**"Seguimiento del impacto de becas a estudiantes activos"** (Dirección de
Bienestar Universitario, UCE), exportadas desde Microsoft Forms a Excel.

## Principio de diseño

El programa **nunca tiene preguntas del formulario escritas directamente en
el código**. Todo pasa por un diccionario de preguntas editable
(`config/plantilla_default.json`), para que si el formulario cambia
(se agrega, elimina o renombra una pregunta) el programa siga funcionando:
detecta el cambio y permite resolverlo desde la interfaz, sin tocar código.

## Estado actual

- [x] Diccionario de preguntas (`app/schema.py`) — modelo de datos + carga/guardado en JSON
- [x] Carga de Excel y mapeo automático de columnas (`app/io_excel.py`)
- [x] Detección de columnas nuevas sin clasificar y preguntas ausentes
- [x] Plantilla por defecto con las 23 columnas del formulario actual (`config/plantilla_default.json`)
- [x] Motor de análisis (`app/analysis.py`): conversión de estrellas/tipos, filtro por consentimiento, detección de duplicados, perfil, resumen por pregunta segmentado por tipo de beca, índices compuestos, relaciones entre variables, casos prioritarios
- [x] Interfaz PySide6 (`app/ui/`): carga de Excel, diálogo de resolución de mapeo (columnas nuevas / preguntas ausentes), pestañas de resultados (Resumen, Perfil, las 3 secciones de impacto, Índices, Relaciones, Casos prioritarios)
- [ ] Generación de informe final en Word (`python-docx`)
- [ ] Detección de duplicados y filtrado por consentimiento
- [ ] Comparación entre rondas/semestres (histórico)

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar la aplicación

```bash
python app/main.py
```

Desde el menú **Archivo > Cargar Excel...** puedes seleccionar el archivo de
respuestas exportado desde Microsoft Forms. Si el formulario cambió (columna
nueva o pregunta eliminada), se abrirá un diálogo para resolverlo antes de
mostrar el análisis en pestañas.

El diccionario de preguntas que edites desde la app se guarda en
`config/plantilla_local.json` (no versionado en git) — la plantilla base en
`config/plantilla_default.json` no se modifica.

## Probar solo la carga + mapeo (sin interfaz)

```bash
python tests/test_mapping.py "ruta/al/excel_exportado.xlsx"
```

## Nota sobre datos sensibles

Los archivos Excel de respuestas reales contienen datos personales (cédula,
nombre, correo) y **no deben subirse al repositorio** — por eso están
excluidos en `.gitignore`. Solo se versiona la plantilla del diccionario de
preguntas, que no contiene respuestas de estudiantes.
