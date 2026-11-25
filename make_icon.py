"""Создаёт assets/app.ico (несколько размеров, PNG внутри ICO) для сборки exe."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv)
from ui.icons import app_icon  # noqa: E402

sizes = [16, 24, 32, 48, 64, 128, 256]
icon = app_icon()
blobs = []
for s in sizes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    icon.pixmap(s, s).toImage().save(buf, "PNG")
    blobs.append(bytes(ba))
out = bytearray(struct.pack("<HHH", 0, 1, len(sizes)))
offset = 6 + 16 * len(sizes)
for s, b in zip(sizes, blobs):
    out += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(b), offset)
    offset += len(b)
for b in blobs:
    out += b
p = Path(__file__).resolve().parent / "assets" / "app.ico"
p.parent.mkdir(exist_ok=True)
p.write_bytes(out)
print("иконка:", p)
