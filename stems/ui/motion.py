from __future__ import annotations

import os
import re
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


_RGBA_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9]*\.?[0-9]+)\s*)?\)"
)


def is_reduced_motion() -> bool:
    return os.environ.get("STEMS_REDUCE_MOTION", "").strip() == "1"


def effective_duration(duration_ms: int) -> int:
    if is_reduced_motion():
        return 0
    return max(0, int(duration_ms))


def parse_css_color(value: str) -> QColor:
    match = _RGBA_RE.fullmatch(value.strip())
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        alpha_raw = match.group(4)
        a = 1.0 if alpha_raw is None else max(0.0, min(1.0, float(alpha_raw)))
        color = QColor(r, g, b)
        color.setAlphaF(a)
        return color
    return QColor(value)


def lerp_color(start: QColor, end: QColor, t: float) -> QColor:
    clamped = max(0.0, min(1.0, float(t)))
    return QColor.fromRgbF(
        start.redF() + (end.redF() - start.redF()) * clamped,
        start.greenF() + (end.greenF() - start.greenF()) * clamped,
        start.blueF() + (end.blueF() - start.blueF()) * clamped,
        start.alphaF() + (end.alphaF() - start.alphaF()) * clamped,
    )


class FloatTween(QVariantAnimation):
    def __init__(
        self,
        parent: QObject | None,
        initial: float = 0.0,
        on_change: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._value = float(initial)
        self._target = float(initial)
        self._on_change = on_change
        self._on_finished: Callable[[], None] | None = None
        self.setEasingCurve(QEasingCurve.OutCubic)
        self.valueChanged.connect(self._handle_value_changed)
        self.finished.connect(self._handle_finished)

    @property
    def value(self) -> float:
        return self._value

    @property
    def target(self) -> float:
        return self._target

    def _handle_value_changed(self, value: object) -> None:
        self._value = float(value)
        if self._on_change is not None:
            self._on_change(self._value)

    def _handle_finished(self) -> None:
        self._value = self._target
        cb = self._on_finished
        self._on_finished = None
        if cb is not None:
            cb()

    def animate_to(
        self,
        target: float,
        duration_ms: int,
        *,
        animate: bool = True,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        target_f = float(target)
        dur = effective_duration(duration_ms) if animate else 0
        self._on_finished = None
        if self.state() == QVariantAnimation.Running:
            self.stop()
        self._target = target_f
        if dur <= 0 or abs(self._value - target_f) < 1e-6:
            self._value = target_f
            if self._on_change is not None:
                self._on_change(self._value)
            if on_finished is not None:
                on_finished()
            return
        self._on_finished = on_finished
        self.setStartValue(self._value)
        self.setEndValue(target_f)
        self.setDuration(dur)
        self.setEasingCurve(QEasingCurve.OutCubic)
        self.start()

    def snap_to(self, target: float) -> None:
        self._on_finished = None
        if self.state() == QVariantAnimation.Running:
            self.stop()
        target_f = float(target)
        self._target = target_f
        self._value = target_f
        if self._on_change is not None:
            self._on_change(self._value)

    def stop_and_snap(self) -> None:
        self._on_finished = None
        if self.state() == QVariantAnimation.Running:
            self.stop()
            self._value = self._target
            if self._on_change is not None:
                self._on_change(self._value)


class ColorTween(QVariantAnimation):
    def __init__(
        self,
        parent: QObject | None,
        initial: QColor,
        on_change: Callable[[QColor], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._value = QColor(initial)
        self._target = QColor(initial)
        self._on_change = on_change
        self.setEasingCurve(QEasingCurve.OutCubic)
        self.valueChanged.connect(self._handle_value_changed)
        self.finished.connect(self._handle_finished)

    @property
    def value(self) -> QColor:
        return self._value

    def _handle_value_changed(self, value: object) -> None:
        if isinstance(value, QColor):
            self._value = QColor(value)
            if self._on_change is not None:
                self._on_change(self._value)

    def _handle_finished(self) -> None:
        self._value = QColor(self._target)

    def animate_to(self, target: QColor, duration_ms: int, *, animate: bool = True) -> None:
        target_c = QColor(target)
        dur = effective_duration(duration_ms) if animate else 0
        if self.state() == QVariantAnimation.Running:
            self.stop()
        self._target = target_c
        if dur <= 0 or self._value == target_c:
            self._value = QColor(target_c)
            if self._on_change is not None:
                self._on_change(self._value)
            return
        self.setStartValue(QColor(self._value))
        self.setEndValue(QColor(target_c))
        self.setDuration(dur)
        self.setEasingCurve(QEasingCurve.OutCubic)
        self.start()

    def snap_to(self, target: QColor) -> None:
        if self.state() == QVariantAnimation.Running:
            self.stop()
        self._target = QColor(target)
        self._value = QColor(target)
        if self._on_change is not None:
            self._on_change(self._value)

    def stop_and_snap(self) -> None:
        if self.state() == QVariantAnimation.Running:
            self.stop()
            self._value = QColor(self._target)
            if self._on_change is not None:
                self._on_change(self._value)


def stop_fade_widget(widget: QWidget) -> None:
    anim = getattr(widget, "_fade_anim", None)
    if anim is not None and anim.state() == QPropertyAnimation.Running:
        anim.stop()


def fade_widget(
    widget: QWidget,
    target_opacity: float,
    duration_ms: int,
    *,
    start_opacity: float | None = None,
    effect: QGraphicsOpacityEffect | None = None,
    animate: bool = True,
    clear_effect_on_finish: bool = False,
    on_finished: Callable[[], None] | None = None,
) -> QPropertyAnimation | None:
    stop_fade_widget(widget)

    existing = widget.graphicsEffect()
    if effect is not None:
        eff = effect
        if existing is not eff:
            widget.setGraphicsEffect(eff)
    elif isinstance(existing, QGraphicsOpacityEffect):
        eff = existing
    else:
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)

    dur = effective_duration(duration_ms) if animate else 0
    if dur <= 0:
        eff.setOpacity(target_opacity)
        if clear_effect_on_finish:
            widget.setGraphicsEffect(None)
        if on_finished is not None:
            on_finished()
        return None

    if start_opacity is not None:
        eff.setOpacity(start_opacity)

    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(dur)
    anim.setStartValue(eff.opacity())
    anim.setEndValue(target_opacity)
    anim.setEasingCurve(QEasingCurve.OutCubic)

    def _done() -> None:
        if clear_effect_on_finish and widget.graphicsEffect() is eff:
            widget.setGraphicsEffect(None)
        if on_finished is not None:
            on_finished()

    anim.finished.connect(_done)
    setattr(widget, "_fade_anim", anim)
    anim.start()
    return anim


def stop_window_fade(window: QWidget) -> None:
    anim = getattr(window, "_window_opacity_anim", None)
    if anim is not None and anim.state() == QPropertyAnimation.Running:
        anim.stop()


def fade_window_opacity(
    window: QWidget,
    target_opacity: float,
    duration_ms: int,
    *,
    start_opacity: float | None = None,
    animate: bool = True,
) -> QPropertyAnimation | None:
    stop_window_fade(window)
    dur = effective_duration(duration_ms) if animate else 0
    if dur <= 0:
        window.setWindowOpacity(target_opacity)
        return None
    if start_opacity is not None:
        window.setWindowOpacity(start_opacity)
    anim = QPropertyAnimation(window, b"windowOpacity", window)
    anim.setDuration(dur)
    anim.setStartValue(window.windowOpacity())
    anim.setEndValue(target_opacity)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    setattr(window, "_window_opacity_anim", anim)
    anim.start()
    return anim
