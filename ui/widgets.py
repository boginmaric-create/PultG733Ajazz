"""Общие элементы интерфейса и тёмная тема."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QFrame, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

STYLE = """
* { font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: 10pt; color: #e8ebf2; }
QMainWindow, QWidget#root { background: #141821; }
QWidget#page { background: #141821; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QListWidget#nav { background: #1a1f2b; border: none; padding: 8px 6px; outline: 0; }
QListWidget#nav::item { padding: 10px 12px; border-radius: 8px; margin: 2px 0; }
QListWidget#nav::item:selected { background: #2a3550; color: #ffffff; }
QListWidget#nav::item:hover:!selected { background: #222939; }
QFrame#card { background: #1c2230; border: 1px solid #262e40; border-radius: 12px; }
QLabel#cardTitle { font-size: 12pt; font-weight: 600; color: #ffffff; }
QLabel#pageTitle { font-size: 17pt; font-weight: 600; color: #ffffff; }
QLabel#muted { color: #9aa3b5; }
QLabel#big { font-size: 26pt; font-weight: 700; }
QLabel#warn { color: #f2b33d; }
QPushButton { background: #2a3245; border: 1px solid #343e55; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: #333d55; }
QPushButton:pressed { background: #252c3d; }
QPushButton:disabled { color: #667085; background: #20263380; }
QPushButton#primary { background: #4f8cff; border-color: #4f8cff; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #6a9eff; }
QPushButton#primary:disabled { background: #3a4c75; border-color: #3a4c75; color: #aab4c8; }
QComboBox, QSpinBox { background: #232a3a; border: 1px solid #343e55; border-radius: 7px; padding: 5px 8px; min-height: 20px; }
QComboBox QAbstractItemView { background: #232a3a; selection-background-color: #2f4a80; border: 1px solid #343e55; }
QComboBox::drop-down { border: none; width: 22px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QRadioButton::indicator { width: 14px; height: 14px; border: 2px solid #5a6680; border-radius: 9px; background: #232a3a; }
QRadioButton::indicator:checked { border: 2px solid #4f8cff; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #4f8cff, stop:0.55 #4f8cff, stop:0.65 #232a3a); }
QSlider::groove:horizontal { height: 6px; background: #2a3245; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #4f8cff; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; background: #ffffff; }
QSlider::groove:vertical { width: 6px; background: #2a3245; border-radius: 3px; }
QSlider::add-page:vertical { background: #4f8cff; border-radius: 3px; }
QSlider::handle:vertical { width: 16px; height: 16px; margin: 0 -6px; border-radius: 8px; background: #ffffff; }
QProgressBar { background: #2a3245; border: none; border-radius: 5px; height: 10px; text-align: center; }
QProgressBar::chunk { border-radius: 5px; background: #3ccf6e; }
QPlainTextEdit { background: #10131a; border: 1px solid #262e40; border-radius: 8px; font-family: Consolas, monospace; font-size: 9pt; }
QToolTip { background: #232a3a; color: #e8ebf2; border: 1px solid #343e55; }
QMenu { background: #1c2230; border: 1px solid #343e55; padding: 4px; }
QMenu::item { padding: 6px 22px; border-radius: 6px; }
QMenu::item:selected { background: #2a3550; }
QMenu::item:disabled { color: #9aa3b5; }
"""


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 14, 18, 16)
        self.lay.setSpacing(10)
        if title:
            t = QLabel(title)
            t.setObjectName("cardTitle")
            self.lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("muted")
            s.setWordWrap(True)
            self.lay.addWidget(s)

    def add(self, w) -> None:
        if isinstance(w, QWidget):
            self.lay.addWidget(w)
        else:
            self.lay.addLayout(w)


def muted(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("muted")
    l.setWordWrap(True)
    return l


def row(*widgets, stretch_last=False) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(10)
    for w in widgets:
        if w is None:
            h.addStretch(1)
        elif isinstance(w, QWidget):
            h.addWidget(w)
        else:
            h.addLayout(w)
    if stretch_last:
        h.addStretch(1)
    return h


class ColorButton(QPushButton):
    colorChanged = Signal(QColor)

    def __init__(self, color="#ffffff") -> None:
        super().__init__()
        self.setFixedSize(46, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Выбрать цвет")
        self._c = QColor(color)
        self._apply()
        self.clicked.connect(self._pick)

    def color(self) -> QColor:
        return QColor(self._c)

    def setColor(self, c) -> None:
        self._c = QColor(c)
        self._apply()

    def _apply(self) -> None:
        self.setStyleSheet(f"QPushButton {{ background: {self._c.name()}; border: 2px solid #3a4560; border-radius: 7px; }}")

    def _pick(self) -> None:
        c = QColorDialog.getColor(self._c, self, "Выберите цвет")
        if c.isValid():
            self.setColor(c)
            self.colorChanged.emit(c)


class ValueSlider(QWidget):
    """Ползунок с подписью значения справа."""
    valueChanged = Signal(int)

    def __init__(self, lo: int, hi: int, suffix: str = "") -> None:
        super().__init__()
        self.suffix = suffix
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.s = QSlider(Qt.Horizontal)
        self.s.setRange(lo, hi)
        self.lbl = QLabel()
        self.lbl.setMinimumWidth(56)
        self.lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(self.s, 1)
        h.addWidget(self.lbl)
        self.s.valueChanged.connect(self._changed)
        self._changed(self.s.value())

    def _changed(self, v: int) -> None:
        self.lbl.setText(f"{v}{self.suffix}")
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self.s.value()

    def setValue(self, v: int) -> None:
        self.s.blockSignals(True)
        self.s.setValue(int(v))
        self.s.blockSignals(False)
        self.lbl.setText(f"{int(v)}{self.suffix}")


class BatteryCard(Card):
    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.big = QLabel("—")
        self.big.setObjectName("big")
        self.state = muted("Поиск устройства…")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        v = QVBoxLayout()
        v.addWidget(self.state)
        v.addWidget(self.bar)
        self.add(row(self.big, v))

    def set(self, percent, text: str, color: str = "#3ccf6e") -> None:
        self.big.setText(f"{percent}%" if percent is not None else "—")
        self.bar.setValue(percent or 0)
        self.bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; border-radius: 5px; }}")
        self.big.setStyleSheet(f"color: {color if percent is not None else '#8a8f98'};")
        self.state.setText(text)
