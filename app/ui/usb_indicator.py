"""Indicador d'USB connectat, a la fila d'accions de la finestra.

Ocupa el lloc que abans tenia el botó "Còpia de seguretat" (que ara viu
només al menú Fitxer). Pinta la icona clàssica del USB —el trident— en
verd si hi ha algun llapis de memòria connectat i en vermell si no n'hi
ha, amb la llista d'unitats al tooltip.

La detecció és de veritat, no un adorn, i es fa amb el mecanisme de cada
sistema (no s'hi dona per suposada cap lletra d'unitat com D: o E:):

  - Windows: `GetLogicalDrives` + `GetDriveTypeW` de kernel32 via ctypes
    (biblioteca estàndard, cap dependència nova). Es queda amb les unitats
    de tipus DRIVE_REMOVABLE, que és el que retornen els llapis USB.
  - macOS i Linux: `QStorageInfo.mountedVolumes()` —el que ja fa servir Qt,
    que és la tecnologia de l'app— filtrant els punts de muntatge on el
    sistema penja els volums externs (/Volumes, /media, /run/media, /mnt).

Qt no té cap senyal de "s'ha connectat un dispositiu" multiplataforma, així
que es consulta cada `_POLL_MS`; només es repinta quan l'estat canvia de
debò, i a Windows la consulta no toca el disc (només llegeix la taula
d'unitats), de manera que no desperta res.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from app.i18n import t

_POLL_MS = 3000

_CONNECTED_COLOR = "#1a9c6d"
_DISCONNECTED_COLOR = "#c62828"

# Windows: valor de GetDriveTypeW per a una unitat extraïble (llapis USB).
_DRIVE_REMOVABLE = 2
# macOS/Linux: on hi pengen els volums externs.
_EXTERNAL_MOUNTS = ("/Volumes/", "/media/", "/run/media/", "/mnt/")


def removable_drives() -> list[str]:
    """Unitats extraïbles connectades ara mateix (llista buida si cap)."""
    if sys.platform.startswith("win"):
        return _windows_removable_drives()
    return _unix_removable_drives()


def _windows_removable_drives() -> list[str]:
    import ctypes

    try:
        kernel32 = ctypes.windll.kernel32
        mask = kernel32.GetLogicalDrives()
    except (AttributeError, OSError):
        return []
    drives = []
    for i in range(26):
        if not mask & (1 << i):
            continue
        root = f"{chr(ord('A') + i)}:\\"
        try:
            if kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == _DRIVE_REMOVABLE:
                drives.append(root)
        except OSError:
            continue
    return drives


def _unix_removable_drives() -> list[str]:
    from PySide6.QtCore import QStorageInfo

    drives = []
    for volume in QStorageInfo.mountedVolumes():
        if not volume.isValid() or not volume.isReady():
            continue
        root = volume.rootPath()
        if any(root.startswith(prefix) for prefix in _EXTERNAL_MOUNTS):
            drives.append(root)
    return drives


class UsbIndicator(QWidget):
    """Icona d'USB petita, verda o vermella segons si n'hi ha algun connectat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Petita: el dibuix és relatiu a la mida, així que es veu igual
        # de nítida però ocupa molt menys a la fila d'accions.
        self.setFixedSize(20, 20)
        self._drives: list[str] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(_POLL_MS)
        self.refresh()

    def refresh(self):
        """Torna a mirar si hi ha cap USB; només repinta si ha canviat."""
        drives = removable_drives()
        if drives == self._drives:
            return
        self._drives = drives
        self.setToolTip(
            t("usb.connected", drives=", ".join(drives)) if drives else t("usb.disconnected")
        )
        self.update()

    @property
    def connected(self) -> bool:
        return bool(self._drives)

    def paintEvent(self, event):
        # El trident de l'USB, dibuixat a mà amb coordenades relatives a la
        # mida del widget: així no depèn de cap fitxer d'icona ni de cap
        # tipus de lletra de la plataforma, es veu igual a qualsevol
        # escalat de pantalla i es pinta directament del color que toca.
        color = QColor(_CONNECTED_COLOR if self.connected else _DISCONNECTED_COLOR)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = min(self.width(), self.height()) - 6
        x0 = (self.width() - size) / 2
        y0 = (self.height() - size) / 2
        cx = x0 + size / 2

        pen = QPen(color)
        pen.setWidthF(max(1.4, size * 0.09))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(color)

        stem_top = y0 + size * 0.18
        stem_bottom = y0 + size * 0.84
        painter.drawLine(QPointF(cx, stem_top), QPointF(cx, stem_bottom))

        # Punta de fletxa de dalt
        painter.drawPolygon(QPolygonF([
            QPointF(cx, y0),
            QPointF(cx - size * 0.13, stem_top),
            QPointF(cx + size * 0.13, stem_top),
        ]))
        # Base rodona
        painter.drawEllipse(QPointF(cx, stem_bottom), size * 0.12, size * 0.12)
        # Braç esquerre, acabat en quadrat
        left_x, left_y = x0 + size * 0.17, y0 + size * 0.38
        painter.drawLine(QPointF(cx, y0 + size * 0.60), QPointF(left_x, left_y))
        side = size * 0.18
        painter.drawRect(QRectF(left_x - side / 2, left_y - side / 2, side, side))
        # Braç dret, acabat en rodona
        right_x, right_y = x0 + size * 0.83, y0 + size * 0.50
        painter.drawLine(QPointF(cx, y0 + size * 0.70), QPointF(right_x, right_y))
        painter.drawEllipse(QPointF(right_x, right_y), size * 0.10, size * 0.10)
        painter.end()
