"""
app.py – Entry point PDF Sanitizer.
"""
import sys
import os

# Linux: gunakan xcb; Windows/macOS: biarkan Qt memilih sendiri
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Sanitizer")
    app.setApplicationVersion("1.0.0")

    # Font default
    font = QFont()
    font.setFamily("Segoe UI")        # Windows
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
