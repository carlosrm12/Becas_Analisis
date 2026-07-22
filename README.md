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
- [ ] Motor de análisis (perfil, impacto por sección, comparación por tipo de beca, relaciones entre dimensiones)
- [ ] Editor visual del diccionario de preguntas (UC3/UC5/UC6)
- [ ] Interfaz PySide6 (pantallas: carga, resolución de mapeo, vista previa, exportar)
- [ ] Generación de informe final en Word (`python-docx`)
- [ ] Detección de duplicados y filtrado por consentimiento
- [ ] Comparación entre rondas/semestres (histórico)

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Probar la carga + mapeo (paso actual)

```bash
python tests/test_mapping.py "ruta/al/excel_exportado.xlsx"
```

Esto debería mostrar cuántas preguntas se mapearon correctamente contra la
plantilla, y avisar si hay columnas nuevas sin clasificar o preguntas
conocidas que no aparecieron en ese archivo.

## Nota sobre datos sensibles

Los archivos Excel de respuestas reales contienen datos personales (cédula,
nombre, correo) y **no deben subirse al repositorio** — por eso están
excluidos en `.gitignore`. Solo se versiona la plantilla del diccionario de
preguntas, que no contiene respuestas de estudiantes.
