"""Punto de entrada de la aplicación de escritorio.

Ejecutar desde la raíz del proyecto:

    python app/main.py
"""

import sys
from pathlib import Path

# Permite ejecutar tanto "python app/main.py" (Python solo agrega la carpeta
# app/ al path, no la raíz del proyecto) como "python -m app.main" desde la raíz.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    ventana = MainWindow()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
