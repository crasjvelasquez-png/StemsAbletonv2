#!/usr/bin/env python3
"""Generate the padded macOS app icon and its complete iconset."""

from pathlib import Path
import shutil
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "stems-tower.png"
MASTER = ROOT / "stems-tower-icon.png"
ICONSET = ROOT / "stems-tower.iconset"
ICNS = ROOT / "stems-tower.icns"

CANVAS_SIZE = 1024
ARTWORK_SIZE = 820
PADDING = (CANVAS_SIZE - ARTWORK_SIZE) // 2

ICON_FILES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def resized(image: QImage, size: int) -> QImage:
    return image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def main() -> None:
    source = QImage(str(SOURCE))
    if source.isNull():
        raise RuntimeError(f"Could not read source icon: {SOURCE}")

    master = QImage(CANVAS_SIZE, CANVAS_SIZE, QImage.Format.Format_RGBA8888)
    master.fill(Qt.GlobalColor.transparent)
    painter = QPainter(master)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage(PADDING, PADDING, resized(source, ARTWORK_SIZE))
    painter.end()

    if not master.save(str(MASTER), "PNG"):
        raise RuntimeError(f"Could not write icon master: {MASTER}")

    shutil.rmtree(ICONSET, ignore_errors=True)
    ICONSET.mkdir()
    for filename, size in ICON_FILES.items():
        if not resized(master, size).save(str(ICONSET / filename), "PNG"):
            raise RuntimeError(f"Could not write icon size: {filename}")

    subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET), "-o", str(ICNS)],
        check=True,
    )
    print(f"Generated {ICNS} from a {CANVAS_SIZE}px master ({ARTWORK_SIZE}px artwork).")


if __name__ == "__main__":
    main()
