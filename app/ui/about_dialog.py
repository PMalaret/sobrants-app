"""Diàleg 'Sobre Sobrants' (menú Fitxer): versió, creador i logotip, en
una sola columna."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from app.i18n import t
from app.version import APP_VERSION

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
CREATOR_URL = "https://luvnus.es/"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("menu.about"))
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel(t("menu.about"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        version_label = QLabel(t("menu.version", version=APP_VERSION))
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        creator_label = QLabel(t("about.creator", url=CREATOR_URL))
        creator_label.setAlignment(Qt.AlignCenter)
        creator_label.setTextFormat(Qt.RichText)
        creator_label.setOpenExternalLinks(True)
        layout.addWidget(creator_label)

        image_path = ASSETS_DIR / "luvnus.webp"
        if image_path.exists():
            pixmap = QPixmap(str(image_path))
            if not pixmap.isNull():
                image_label = QLabel()
                image_label.setPixmap(pixmap.scaledToWidth(220, Qt.SmoothTransformation))
                image_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(image_label)
