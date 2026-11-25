"""Рисование значков для трея: наушники / мышь + уровень заряда."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

GREEN = QColor("#3ccf6e")
YELLOW = QColor("#f2b33d")
RED = QColor("#f0524f")
GREY = QColor("#8a8f98")
WHITE = QColor("#f2f4f8")
ACCENT = QColor("#4f8cff")


def level_color(percent, online: bool, low: int = 20) -> QColor:
    if not online or percent is None:
        return GREY
    if percent <= low:
        return RED
    if percent < 50:
        return YELLOW
    return GREEN


def draw_headphones(p: QPainter, r: QRectF, color: QColor) -> None:
    w = r.width()
    pen = QPen(color, w * 0.11, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    band = QRectF(r.left() + w * 0.14, r.top() + w * 0.08, w * 0.72, w * 0.8)
    p.drawArc(band, 0, 180 * 16)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    cup_w, cup_h = w * 0.26, w * 0.42
    y = r.top() + w * 0.46
    p.drawRoundedRect(QRectF(r.left() + w * 0.06, y, cup_w, cup_h), w * 0.08, w * 0.08)
    p.drawRoundedRect(QRectF(r.right() - w * 0.06 - cup_w, y, cup_w, cup_h), w * 0.08, w * 0.08)


def draw_mouse(p: QPainter, r: QRectF, color: QColor) -> None:
    w = r.width()
    body = QRectF(r.left() + w * 0.2, r.top() + w * 0.04, w * 0.6, w * 0.92)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(body, w * 0.3, w * 0.3)
    p.setPen(QPen(QColor(0, 0, 0, 170), w * 0.07, Qt.SolidLine, Qt.RoundCap))
    cx = body.center().x()
    p.drawLine(QPointF(body.left() + w * 0.02, body.top() + w * 0.4), QPointF(body.right() - w * 0.02, body.top() + w * 0.4))
    p.drawLine(QPointF(cx, body.top() + w * 0.06), QPointF(cx, body.top() + w * 0.4))


def draw_bolt(p: QPainter, r: QRectF) -> None:
    w = r.width()
    pts = [(0.58, 0.0), (0.12, 0.56), (0.45, 0.56), (0.36, 1.0), (0.88, 0.40), (0.54, 0.40), (0.66, 0.0)]
    poly = QPolygonF([QPointF(r.left() + x * w, r.top() + y * r.height()) for x, y in pts])
    p.setPen(QPen(QColor(0, 0, 0, 200), w * 0.08))
    p.setBrush(QColor("#ffd84a"))
    p.drawPolygon(poly)


def _text(p: QPainter, rect: QRectF, text: str, color: QColor, px: float) -> None:
    f = QFont("Segoe UI")
    f.setBold(True)
    f.setPixelSize(max(6, int(px)))
    p.setFont(f)
    # тёмная обводка для читаемости на любой панели задач
    path = QPainterPath()
    fm_w = p.fontMetrics().horizontalAdvance(text)
    base = QPointF(rect.center().x() - fm_w / 2, rect.center().y() + p.fontMetrics().capHeight() / 2)
    path.addText(base, f, text)
    p.setPen(QPen(QColor(0, 0, 0, 220), px * 0.16, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path)


def render(kind: str, percent, online: bool, charging: bool = False,
           style: str = "glyph_number", low: int = 20, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    col = level_color(percent, online, low)
    glyph = draw_headphones if kind == "headset" else draw_mouse
    txt = "–" if (not online or percent is None) else str(int(percent))

    if style == "number":
        px = s * (0.62 if len(txt) >= 3 else 0.82)
        _text(p, QRectF(0, 0, s, s * 0.96), txt, col, px)
        # маленькая метка устройства в углу
        glyph(p, QRectF(0, 0, s * 0.34, s * 0.34), WHITE)
    elif style == "glyph_bar":
        glyph(p, QRectF(0, s * 0.06, s * 0.74, s * 0.74), WHITE if online else GREY)
        bar = QRectF(s * 0.80, s * 0.04, s * 0.18, s * 0.92)
        p.setPen(QPen(QColor(0, 0, 0, 200), s * 0.03))
        p.setBrush(QColor(255, 255, 255, 50))
        p.drawRoundedRect(bar, s * 0.05, s * 0.05)
        if online and percent is not None:
            h = (bar.height() - s * 0.06) * max(0.05, percent / 100)
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(bar.left() + s * 0.03, bar.bottom() - s * 0.03 - h,
                                     bar.width() - s * 0.06, h), s * 0.03, s * 0.03)
    else:  # glyph_number
        glyph(p, QRectF(s * 0.22, 0, s * 0.56, s * 0.56), WHITE if online else GREY)
        px = s * (0.46 if len(txt) >= 3 else 0.54)
        _text(p, QRectF(0, s * 0.50, s, s * 0.50), txt, col, px)

    if charging and online:
        draw_bolt(p, QRectF(s * 0.66, 0, s * 0.34, s * 0.42))
    p.end()
    return pm


def tray_icon(kind, percent, online, charging=False, style="glyph_number", low=20) -> QIcon:
    icon = QIcon()
    for sz in (16, 20, 24, 32, 40, 48, 64):
        icon.addPixmap(render(kind, percent, online, charging, style, low, sz))
    return icon


def app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(sz, sz)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        s = float(sz)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1d2230"))
        p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)
        draw_headphones(p, QRectF(s * 0.08, s * 0.12, s * 0.5, s * 0.5), ACCENT)
        draw_mouse(p, QRectF(s * 0.46, s * 0.42, s * 0.48, s * 0.48), GREEN)
        p.end()
        icon.addPixmap(pm)
    return icon
