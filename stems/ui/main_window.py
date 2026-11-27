from __future__ import annotations

import html
import math
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from ..ableton import AbletonClient
from ..automation import bring_process_to_front
from ..models import DEFAULT_RANGE_BARS, ExportJob, ExportRange, ExportResult, StemTrack
from ..osc import OSCGateway
from ..export import find_conflicts, short_failure_reason
from ..preferences import Preferences, PreferencesStore
from ..state import AppState

try:
    from PySide6.QtCore import QEvent, QPointF, QRectF, QSignalBlocker, QSize, QThread, QTimer, Qt, Signal
    from PySide6.QtGui import (
        QColor,
        QFont,
        QFontMetrics,
        QIcon,
        QKeySequence,
        QPainter,
        QPainterPath,
        QPalette,
        QPen,
        QPixmap,
        QShortcut,
    )
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QDialog,
        QFrame,
        QGraphicsOpacityEffect,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

from ..login_item import is_launch_agent_installed, remove_launch_agent
from .motion import (
    ColorTween,
    FloatTween,
    effective_duration,
    fade_widget,
    fade_window_opacity,
    lerp_color,
    parse_css_color,
    stop_fade_widget,
    stop_window_fade,
)
from .path_trail import PathTrail
from .preferences_dialog import PreferencesDialog
from .theme import (
    CLIP_COLORS,
    DESIGN_TOKENS,
    DURATION_BASE,
    DURATION_DIALOG,
    DURATION_FAST,
    DURATION_REBUILD,
    DURATION_SUCCESS,
    DURATION_TWEEN,
    SCAN_COMPLETE_HOLD_MS,
    stylesheet_for_scale,
)
from .worker import ExportWorker, ScanWorker


REFERENCE_WINDOW_SIZE = (620, 760)
MINIMUM_WINDOW_SIZE = (480, 560)
COMPACT_LAYOUT_BREAKPOINT = 560


UI_BASE_SIZES = {
    "window_min": MINIMUM_WINDOW_SIZE,
    "window_default": REFERENCE_WINDOW_SIZE,
    "window_margins": (24, 12, 24, 24),
    "header_button": 32,
    "header_bottom_spacing": 20,
    "stem_lane_height": 40,
    "stem_lane_gap": 4,
    "stem_tab_width": 48,
    "stem_row_height": 44,
    "field_height": 36,
    "export_top_spacing": 20,
    "footer_margins": (24, 16, 24, 16),
    "footer_spacing": 12,
    "progress_spacing": 6,
    "progress_header_spacing": 10,
    "progress_percent_width": 36,
    "progress_bar_height": 2,
    "action_spacing": 8,
    "action_height": 36,
    "action_min_width": 112,
}


def _scaled_value(value: int | tuple[int, ...], scale: float) -> int | tuple[int, ...]:
    if isinstance(value, tuple):
        return tuple(max(0, round(item * scale)) for item in value)
    return max(1, round(value * scale))


def ui_sizes_for_scale(scale: float) -> dict[str, int | tuple[int, ...]]:
    sizes = {key: _scaled_value(value, scale) for key, value in UI_BASE_SIZES.items()}
    sizes["header_button"] = max(28, int(sizes["header_button"]))
    sizes["stem_lane_height"] = max(34, int(sizes["stem_lane_height"]))
    sizes["stem_row_height"] = int(sizes["stem_lane_height"]) + int(sizes["stem_lane_gap"])
    sizes["field_height"] = max(32, int(sizes["field_height"]))
    sizes["action_height"] = max(32, int(sizes["action_height"]))
    return sizes


def _resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


def _app_icon() -> QIcon:
    return QIcon(str(_resource_path("assets", "logo", "stems-tower.png")))


def _gear_icon(size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    color = QColor("#a1a1a6")
    center = QPointF(size / 2.0, size / 2.0)
    scale = size / 16.0

    # 8 radial gear teeth
    painter.setPen(QPen(color, 1.6 * scale, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    inner_r = 4.7 * scale
    outer_r = 6.5 * scale
    for i in range(8):
        angle = i * (math.pi / 4.0)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        painter.drawLine(
            QPointF(center.x() + inner_r * cos_a, center.y() + inner_r * sin_a),
            QPointF(center.x() + outer_r * cos_a, center.y() + outer_r * sin_a),
        )

    # Outer gear ring with a transparent inner hole
    painter.setPen(QPen(color, 1.7 * scale))
    painter.setBrush(Qt.NoBrush)
    ring_r = 4.1 * scale
    painter.drawEllipse(center, ring_r, ring_r)

    painter.end()
    return QIcon(pixmap)


_sliders_icon = _gear_icon


def _relative_luminance(color: QColor) -> float:
    def _linear(channel: int) -> float:
        srgb = channel / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * _linear(color.red())
        + 0.7152 * _linear(color.green())
        + 0.0722 * _linear(color.blue())
    )



class StemTrackRow(QWidget):
    def __init__(
        self,
        track: StemTrack,
        display_index: int,
        *,
        sizes: dict[str, int | tuple[int, ...]] | None = None,
        show_separator: bool = True,  # kept for call compatibility
    ) -> None:
        super().__init__()
        del show_separator
        sizes = sizes or UI_BASE_SIZES
        self.setObjectName("stemTrackRow")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

        self._track_name = track.name
        self._display_index = display_index
        self._clip_color = self._resolve_clip_color(track, display_index)
        self._clip_luminance = _relative_luminance(self._clip_color)
        self._ink_on_clip = QColor("#141415" if self._clip_luminance > 0.179 else "#f4f4f5")
        self._hovered = False
        self._animating = False
        self._lane_height = int(sizes["stem_lane_height"])
        self._lane_gap = int(sizes["stem_lane_gap"])
        self._tab_width = int(sizes["stem_tab_width"])
        self._hatch_phase = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._advance_animation)

        self._hover_color = ColorTween(
            self,
            parse_css_color(DESIGN_TOKENS["panel"]),
            lambda _color: self.update(),
        )
        self._check_mix = FloatTween(
            self,
            1.0 if track.selected else 0.0,
            lambda _value: self.update(),
        )
        self._success_mix = FloatTween(self, 0.0, lambda _value: self.update())
        self._hatch_alpha = FloatTween(self, 0.0, lambda _value: self.update())

        self.checkbox = QCheckBox(self)
        self.checkbox.setObjectName("stemRowCheckbox")
        self.checkbox.setChecked(track.selected)
        self.checkbox.setToolTip(f"Export {track.name}")
        self.checkbox.setAccessibleName(self.checkbox.toolTip())
        self.checkbox.toggled.connect(self._on_checkbox_toggled)
        self.checkbox.hide()

        self.status_label = QLabel("")
        self.status_label.setObjectName("stemRowStatus")
        self.status_label.setProperty("statusState", "detected")
        self.status_label.setStyleSheet(
            f'QLabel#stemRowStatus[statusState="success"] {{ color: {self._ink_on_clip.name()}; }}'
        )
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.hide()

        self.row_layout = QHBoxLayout(self)
        self.row_layout.setSpacing(0)
        self.row_layout.addStretch(1)
        self.row_layout.addWidget(self.status_label)

        self.apply_sizes(sizes)

    @staticmethod
    def _resolve_clip_color(track: StemTrack, display_index: int) -> QColor:
        return (
            QColor.fromRgb(track.color)
            if track.color is not None
            else QColor(CLIP_COLORS[(display_index - 1) % len(CLIP_COLORS)])
        )

    def update_track(
        self,
        track: StemTrack,
        display_index: int,
        *,
        sizes: dict[str, int | tuple[int, ...]] | None = None,
    ) -> None:
        self._display_index = display_index
        self._clip_color = self._resolve_clip_color(track, display_index)
        self._clip_luminance = _relative_luminance(self._clip_color)
        self._ink_on_clip = QColor("#141415" if self._clip_luminance > 0.179 else "#f4f4f5")
        self.status_label.setStyleSheet(
            f'QLabel#stemRowStatus[statusState="success"] {{ color: {self._ink_on_clip.name()}; }}'
        )
        if sizes is not None:
            self.apply_sizes(sizes)
        with QSignalBlocker(self.checkbox):
            self.checkbox.setChecked(track.selected)
        self.checkbox.setToolTip(f"Export {track.name}")
        self.checkbox.setAccessibleName(self.checkbox.toolTip())
        self._check_mix.snap_to(1.0 if track.selected else 0.0)
        self.reset_status()
        self.update()

    def set_checked_immediate(self, checked: bool) -> None:
        self.checkbox.setChecked(checked)
        self._check_mix.snap_to(1.0 if checked else 0.0)
        self.update()

    def fade_in(self, duration_ms: int = DURATION_REBUILD) -> None:
        if not self.isVisible():
            return
        fade_widget(
            self,
            1.0,
            duration_ms,
            start_opacity=0.0,
            clear_effect_on_finish=True,
        )

    def clear_fade_effect(self) -> None:
        stop_fade_widget(self)
        if self.graphicsEffect() is not None:
            self.setGraphicsEffect(None)

    def apply_sizes(self, sizes: dict[str, int | tuple[int, ...]]) -> None:
        self._lane_height = int(sizes["stem_lane_height"])
        self._lane_gap = int(sizes["stem_lane_gap"])
        self._tab_width = int(sizes["stem_tab_width"])
        row_height = int(sizes["stem_row_height"])
        self.setMinimumHeight(row_height)
        self.setMaximumHeight(row_height)
        self.row_layout.setContentsMargins(0, 0, 16, self._lane_gap)

    def _on_checkbox_toggled(self, checked: bool) -> None:
        self._check_mix.animate_to(
            1.0 if checked else 0.0,
            DURATION_TWEEN,
            animate=self.isVisible(),
        )
        self.update()

    def _update_hover_target(self) -> None:
        hovered_active = self._hovered and self.isEnabled()
        target = parse_css_color(
            DESIGN_TOKENS["panel_hover"] if hovered_active else DESIGN_TOKENS["panel"]
        )
        self._hover_color.animate_to(
            target,
            DURATION_TWEEN,
            animate=self.isVisible(),
        )

    def set_animating(self, active: bool) -> None:
        self._animating = active
        if active:
            if self.isVisible():
                if not self._anim_timer.isActive():
                    self._anim_timer.start()
                self._hatch_alpha.animate_to(1.0, DURATION_FAST, animate=True)
            else:
                self._hatch_alpha.snap_to(1.0)
        else:
            if self.isVisible() and effective_duration(DURATION_FAST) > 0:
                def _stop_hatch_timer() -> None:
                    if not self._animating:
                        self._anim_timer.stop()
                        self._hatch_phase = 0.0
                        self.update()

                self._hatch_alpha.animate_to(
                    0.0,
                    DURATION_FAST,
                    animate=True,
                    on_finished=_stop_hatch_timer,
                )
            else:
                self._anim_timer.stop()
                self._hatch_phase = 0.0
                self._hatch_alpha.snap_to(0.0)
        self.update()

    def set_status_state(self, status: str, *, was_hidden: bool) -> None:
        self.clear_fade_effect()
        if status == "success":
            self._success_mix.animate_to(1.0, DURATION_SUCCESS, animate=self.isVisible())
            fade_widget(
                self.status_label,
                1.0,
                DURATION_SUCCESS,
                start_opacity=0.0,
                animate=self.isVisible(),
            )
        else:
            self._success_mix.animate_to(0.0, DURATION_FAST, animate=self.isVisible())
            if was_hidden:
                fade_widget(
                    self.status_label,
                    1.0,
                    DURATION_FAST,
                    start_opacity=0.0,
                    animate=self.isVisible(),
                )
            else:
                fade_widget(self.status_label, 1.0, 0, animate=False)
        self.set_animating(status in {"exporting", "retrying"})

    def reset_status(self) -> None:
        self._animating = False
        self._anim_timer.stop()
        self._hatch_phase = 0.0
        self._hatch_alpha.snap_to(0.0)
        self._success_mix.snap_to(0.0)
        stop_fade_widget(self.status_label)
        if self.status_label.graphicsEffect() is not None:
            self.status_label.setGraphicsEffect(None)
        self.status_label.setText("")
        self.status_label.setToolTip("")
        self.status_label.setProperty("statusState", "detected")
        self.status_label.hide()
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def stop_animations(self) -> None:
        self._anim_timer.stop()
        self._hatch_phase = 0.0
        self._hatch_alpha.stop_and_snap()
        self._success_mix.stop_and_snap()
        self._hover_color.stop_and_snap()
        self._check_mix.stop_and_snap()
        stop_fade_widget(self.status_label)
        eff = self.status_label.graphicsEffect()
        if isinstance(eff, QGraphicsOpacityEffect):
            eff.setOpacity(1.0)
        self.clear_fade_effect()

    def _advance_animation(self) -> None:
        self._hatch_phase = (self._hatch_phase + 0.8) % 20.0
        self.update()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().showEvent(event)
        if self._animating and not self._anim_timer.isActive():
            self._anim_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self.stop_animations()
        super().hideEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if event.type() == QEvent.EnabledChange:
            self._update_hover_target()
        super().changeEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self._hovered = event.position().y() <= self._lane_height
        self._update_hover_target()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self._hovered = False
        self._update_hover_target()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override name
        hovered = event.position().y() <= self._lane_height
        if hovered != self._hovered:
            self._hovered = hovered
            self._update_hover_target()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if (
            event.button() == Qt.LeftButton
            and self.isEnabled()
            and event.position().y() <= self._lane_height
        ):
            self.checkbox.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter) and self.isEnabled():
            self.checkbox.toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        lane_h = float(self._lane_height)
        lane_w = float(self.width())
        tab_w = float(self._tab_width)
        radius = 8.0
        lane_rect = QRectF(0.0, 0.0, lane_w, lane_h)
        lane_path = QPainterPath()
        lane_path.addRoundedRect(lane_rect, radius, radius)

        status = self.status_label.property("statusState") or "detected"
        very_dark_clip = self._clip_luminance < 0.06
        success_t = self._success_mix.value
        check_t = self._check_mix.value
        hatch_t = self._hatch_alpha.value
        base_bg = self._hover_color.value

        painter.save()
        painter.setClipPath(lane_path)

        # Lane background
        lane_bg = (
            lerp_color(base_bg, self._clip_color, success_t)
            if success_t > 0.001
            else base_bg
        )
        painter.fillRect(lane_rect, lane_bg)

        if hatch_t > 0.001 and success_t < 0.999:
            painter.save()
            painter.setPen(Qt.NoPen)
            hatch = QColor(self._clip_color)
            base_alpha = 0.55 if very_dark_clip else 0.30
            pulse = 0.75 + 0.25 * math.sin(2.0 * math.pi * time.monotonic() / 1.6)
            hatch.setAlphaF(base_alpha * pulse * hatch_t * (1.0 - success_t))
            painter.setBrush(hatch)
            painter.rotate(-45)
            diag = int(lane_w + lane_h) + 40
            for x in range(-diag, diag, 20):
                painter.drawRect(
                    QRectF(float(x) + self._hatch_phase, float(-diag), 10.0, float(diag * 2))
                )
            painter.restore()

        if very_dark_clip and success_t > 0.001:
            outline_rect = QRectF(0.5, 0.5, lane_w - 1.0, lane_h - 1.0)
            painter.setPen(QPen(QColor.fromRgbF(1.0, 1.0, 1.0, 0.18 * success_t), 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(outline_rect, radius - 0.5, radius - 0.5)

        # Left tab
        tab_rect = QRectF(0.0, 0.0, tab_w, lane_h)
        if check_t < 0.999:
            inset = 0.75
            t_rect = QRectF(inset, inset, tab_w - inset, lane_h - 2.0 * inset)
            r = max(0.0, radius - inset)
            tab_path = QPainterPath()
            tab_path.moveTo(t_rect.right(), t_rect.top())
            tab_path.lineTo(t_rect.left() + r, t_rect.top())
            tab_path.quadTo(t_rect.left(), t_rect.top(), t_rect.left(), t_rect.top() + r)
            tab_path.lineTo(t_rect.left(), t_rect.bottom() - r)
            tab_path.quadTo(t_rect.left(), t_rect.bottom(), t_rect.left() + r, t_rect.bottom())
            tab_path.lineTo(t_rect.right(), t_rect.bottom())
            tab_path.closeSubpath()
            border_color = QColor("#343437")
            border_color.setAlphaF(1.0 - check_t)
            painter.setPen(QPen(border_color, 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(tab_path)

        if check_t > 0.001:
            tab_fill = QColor(self._clip_color)
            tab_fill.setAlphaF(check_t)
            painter.fillRect(tab_rect, tab_fill)
            if very_dark_clip and success_t < 0.999:
                inset = 0.5
                t_rect = QRectF(inset, inset, tab_w - 2.0 * inset, lane_h - 2.0 * inset)
                r = max(0.0, radius - inset)
                tab_path = QPainterPath()
                tab_path.moveTo(t_rect.right(), t_rect.top())
                tab_path.lineTo(t_rect.left() + r, t_rect.top())
                tab_path.quadTo(t_rect.left(), t_rect.top(), t_rect.left(), t_rect.top() + r)
                tab_path.lineTo(t_rect.left(), t_rect.bottom() - r)
                tab_path.quadTo(t_rect.left(), t_rect.bottom(), t_rect.left() + r, t_rect.bottom())
                tab_path.lineTo(t_rect.right(), t_rect.bottom())
                tab_path.closeSubpath()
                painter.setPen(
                    QPen(QColor.fromRgbF(1.0, 1.0, 1.0, 0.18 * check_t * (1.0 - success_t)), 1.0)
                )
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(tab_path)

        idx_color = lerp_color(QColor("#85858b"), self._ink_on_clip, check_t)
        idx_font = QFont()
        idx_font.setFamilies(["Menlo", "monospace"])
        idx_font.setPixelSize(12)
        idx_font.setWeight(QFont.DemiBold)
        painter.setFont(idx_font)
        painter.setPen(idx_color)
        painter.drawText(tab_rect, Qt.AlignCenter, str(self._display_index))

        # Track name
        name_font = QFont()
        name_font.setFamilies([".AppleSystemUIFont", "Helvetica Neue"])
        name_font.setPixelSize(14)
        name_font.setWeight(QFont.Medium)
        painter.setFont(name_font)
        base_name_color = lerp_color(QColor("#85858b"), QColor("#ededed"), check_t)
        name_color = lerp_color(base_name_color, self._ink_on_clip, success_t)
        name_left = tab_w + 16.0
        right_reserved = (self.status_label.sizeHint().width() + 28.0) if self.status_label.isVisible() else 16.0
        avail_w = max(0, int(lane_w - name_left - right_reserved))
        elided_name = QFontMetrics(name_font).elidedText(self._track_name, Qt.ElideRight, avail_w)
        painter.setPen(name_color)
        painter.drawText(
            QRectF(name_left, 0.0, float(avail_w), lane_h),
            Qt.AlignLeft | Qt.AlignVCenter,
            elided_name,
        )

        painter.restore()

        if self.hasFocus():
            focus_rect = QRectF(0.75, 0.75, lane_w - 1.5, lane_h - 1.5)
            painter.setPen(QPen(QColor("#ededed"), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(focus_rect, radius - 0.75, radius - 0.75)

        painter.end()


def _ruler_total_bars(end_bar: int) -> int:
    target = max(DEFAULT_RANGE_BARS[1], end_bar)
    return ((target + 7) // 8) * 8


class RangeRuler(QWidget):
    def __init__(
        self,
        start_bar: int = DEFAULT_RANGE_BARS[0],
        end_bar: int = DEFAULT_RANGE_BARS[1],
        total_bars: int = DEFAULT_RANGE_BARS[1],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.start_bar = start_bar
        self.end_bar = end_bar
        self.total_bars = max(1, total_bars)
        self._display_start = FloatTween(self, float(start_bar), lambda _v: self.update())
        self._display_end = FloatTween(self, float(end_bar), lambda _v: self.update())
        self.setFixedHeight(40)

    def set_range(self, start_bar: int, end_bar: int, total_bars: int) -> None:
        range_changed = start_bar != self.start_bar or end_bar != self.end_bar
        self.start_bar = start_bar
        self.end_bar = end_bar
        self.total_bars = max(1, total_bars)
        if range_changed:
            animate = self.isVisible()
            self._display_start.animate_to(float(start_bar), DURATION_BASE, animate=animate)
            self._display_end.animate_to(float(end_bar), DURATION_BASE, animate=animate)
        self.update()

    def stop_animations(self) -> None:
        self._display_start.stop_and_snap()
        self._display_end.stop_and_snap()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self.stop_animations()
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        total = max(1, self.total_bars)
        if w <= 0:
            painter.end()
            return

        y = 8

        def bar_x(bar: float) -> float:
            return (bar - 1.0) / total * w

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2a2a2d"))
        painter.drawRoundedRect(QRectF(0, y, w, 8), 4, 4)

        start = max(1.0, min(self._display_start.value, float(total)))
        end = max(start, min(self._display_end.value, float(total)))
        x_start = bar_x(start)
        x_end = bar_x(end + 1.0)
        highlight_w = max(2.0, min(float(w) - x_start, x_end - x_start))
        painter.setBrush(QColor(DESIGN_TOKENS["text"]))
        painter.drawRoundedRect(QRectF(x_start, y, highlight_w, 8), 4, 4)

        font = QFont("Menlo")
        font.setPixelSize(11)
        painter.setFont(font)
        faint_color = QColor(DESIGN_TOKENS["text_faint"])
        for bar in range(1, total + 1, 4):
            major = (bar - 1) % 24 == 0
            tick_color = QColor(faint_color)
            tick_color.setAlpha(200 if major else 90)
            painter.setPen(QPen(tick_color, 1))
            tick_x = int(bar_x(bar))
            painter.drawLine(tick_x, y + 14, tick_x, y + (22 if major else 19))
            label = str(bar)
            if major and tick_x + 4 + painter.fontMetrics().horizontalAdvance(label) <= w:
                painter.setPen(faint_color)
                painter.drawText(tick_x + 4, y + 31, label)

        painter.end()


class SmoothProgressBar(QProgressBar):
    displayRatioChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._display_ratio = FloatTween(self, 0.0, self._on_ratio_changed)
        self._track_color = parse_css_color(DESIGN_TOKENS["border"])
        self._chunk_color = QColor(DESIGN_TOKENS["accent"])

    @property
    def display_ratio(self) -> float:
        return self._display_ratio.value

    def _target_ratio(self) -> float:
        span = self.maximum() - self.minimum()
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.value() - self.minimum()) / span))

    def _sync_display_ratio(self) -> None:
        target = self._target_ratio()
        should_animate = (
            self.isVisible()
            and effective_duration(DURATION_BASE) > 0
            and target >= self._display_ratio.value
        )
        self._display_ratio.animate_to(target, DURATION_BASE, animate=should_animate)

    def _on_ratio_changed(self, ratio: float) -> None:
        self.update()
        self.displayRatioChanged.emit(ratio)

    def setValue(self, value: int) -> None:
        super().setValue(value)
        self._sync_display_ratio()

    def setRange(self, minimum: int, maximum: int) -> None:
        super().setRange(minimum, maximum)
        self._sync_display_ratio()

    def setMinimum(self, minimum: int) -> None:
        super().setMinimum(minimum)
        self._sync_display_ratio()

    def setMaximum(self, maximum: int) -> None:
        super().setMaximum(maximum)
        self._sync_display_ratio()

    def stop_animations(self) -> None:
        self._display_ratio.stop_and_snap()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self.stop_animations()
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override name
        painter = QPainter(self)
        w = float(self.width())
        h = float(self.height())
        if w > 0 and h > 0:
            painter.fillRect(QRectF(0.0, 0.0, w, h), self._track_color)
            fill_w = max(0.0, min(w, w * self._display_ratio.value))
            if fill_w > 0.0:
                painter.fillRect(QRectF(0.0, 0.0, fill_w, h), self._chunk_color)
        painter.end()


class ExportConfirmDialog(QDialog):
    def __init__(
        self,
        job: ExportJob,
        range_headline: str,
        range_detail: str,
        conflict_count: int,
        replace_mode: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Export")
        self.setModal(True)
        self.setFixedWidth(440)
        self.setStyleSheet(stylesheet_for_scale(1.0))
        self.chosen_mode: str | None = None

        track_count = len(job.selected_tracks)
        stem_word = "stem" if track_count == 1 else "stems"
        stems_dir = Path(job.stems_dir)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("exportConfirmContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(14)

        self.title_label = QLabel(f"Export {track_count} {stem_word}?")
        self.title_label.setObjectName("dialogTitle")
        content_layout.addWidget(self.title_label)

        self.summary_card = QWidget()
        self.summary_card.setObjectName("exportConfirmCard")
        self.summary_card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(self.summary_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        range_row = QHBoxLayout()
        range_row.setContentsMargins(0, 0, 0, 0)
        range_row.setSpacing(12)
        self.range_label = QLabel("Range")
        self.range_label.setObjectName("exportConfirmLabel")
        self.range_label.setFixedWidth(52)
        range_text = f"{range_headline} · {range_detail}" if range_detail else range_headline
        self.range_value = QLabel(range_text)
        self.range_value.setObjectName("exportConfirmValue")
        self.range_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        range_row.addWidget(self.range_label)
        range_row.addWidget(self.range_value, 1)
        card_layout.addLayout(range_row)

        separator = QFrame()
        separator.setObjectName("exportConfirmSeparator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedHeight(1)
        card_layout.addWidget(separator)

        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(12)
        self.folder_label = QLabel("Folder")
        self.folder_label.setObjectName("exportConfirmLabel")
        self.folder_label.setFixedWidth(52)
        self.folder_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.folder_value = PathTrail()
        self.folder_value.setPath(stems_dir)
        self.folder_value.setToolTip(str(stems_dir))
        self.folder_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        folder_row.addWidget(self.folder_label)
        folder_row.addWidget(self.folder_value, 1)
        card_layout.addLayout(folder_row)

        content_layout.addWidget(self.summary_card)

        self.conflict_label = QLabel("")
        self.conflict_label.setObjectName("exportConfirmConflict")
        self.conflict_label.setWordWrap(True)
        if conflict_count > 0:
            mode_suffix = {
                "replace": " · will be replaced",
                "keep": " · will be skipped",
                "keep_both": " · will keep both",
            }.get(replace_mode, "")
            self.conflict_label.setText(f"{conflict_count} of {track_count} already exist{mode_suffix}")
        else:
            self.conflict_label.hide()
        content_layout.addWidget(self.conflict_label)

        root_layout.addWidget(content, 1)

        self.footer = QWidget()
        self.footer.setObjectName("footerDock")
        self.footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(8)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.setProperty("actionBarButton", True)
        self.cancel_button.setFixedHeight(34)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)

        self.action_buttons: list[QPushButton] = [self.cancel_button]
        footer_layout.addWidget(self.cancel_button)
        footer_layout.addStretch(1)

        if conflict_count > 0 and replace_mode == "ask":
            for label, mode_value, is_primary in (
                ("Keep both", "keep_both", False),
                ("Skip", "keep", False),
                ("Replace", "replace", True),
            ):
                btn = QPushButton(label)
                btn.setObjectName("primaryAction" if is_primary else "secondary")
                btn.setProperty("actionBarButton", True)
                btn.setFixedHeight(34)
                btn.setDefault(is_primary)
                btn.setAutoDefault(is_primary)
                btn.clicked.connect(lambda _checked=False, m=mode_value: self._choose(m))
                footer_layout.addWidget(btn)
                self.action_buttons.append(btn)
                if is_primary:
                    self.default_action_button = btn
        else:
            resolved_mode = "replace" if replace_mode == "ask" else replace_mode
            export_btn = QPushButton("Export")
            export_btn.setObjectName("primaryAction")
            export_btn.setProperty("actionBarButton", True)
            export_btn.setFixedHeight(34)
            export_btn.setMinimumWidth(88)
            export_btn.setDefault(True)
            export_btn.setAutoDefault(True)
            export_btn.clicked.connect(lambda _checked=False, m=resolved_mode: self._choose(m))
            footer_layout.addWidget(export_btn)
            self.action_buttons.append(export_btn)
            self.default_action_button = export_btn

        root_layout.addWidget(self.footer)
        self.adjustSize()

    def _choose(self, mode: str) -> None:
        self.chosen_mode = mode
        self.accept()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().showEvent(event)
        if effective_duration(DURATION_DIALOG) > 0:
            fade_window_opacity(self, 1.0, DURATION_DIALOG, start_opacity=0.0)
        else:
            self.setWindowOpacity(1.0)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override name
        stop_window_fade(self)
        self.setWindowOpacity(1.0)
        super().hideEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        app = QApplication.instance()
        if app is not None and app.font().family() == "Sans Serif":
            ui_font = QFont()
            ui_font.setFamilies([".AppleSystemUIFont", "Helvetica Neue"])
            app.setFont(ui_font)
        super().__init__()
        self.setWindowTitle("Stems")
        self.setWindowIcon(_app_icon())
        self.setWindowFlags(Qt.Window)

        self.preferences_store = PreferencesStore()
        self.preferences = self.preferences_store.load()
        self.ui_scale = 1.0
        self.ui_sizes = ui_sizes_for_scale(self.ui_scale)
        self.setMinimumSize(*self.ui_sizes["window_min"])
        self.resize(*self.ui_sizes["window_default"])
        self.gateway = OSCGateway()
        self.gateway.start_listener()
        self.state = AppState(AbletonClient(self.gateway))
        self.project = None
        self.current_job: ExportJob | None = None
        self.current_result: ExportResult | None = None
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.export_thread: QThread | None = None
        self.export_worker: ExportWorker | None = None
        self.item_by_track_name: dict[str, QListWidgetItem] = {}
        self.status_by_track_name: dict[str, QLabel] = {}
        self.export_cancel_requested = False
        self._ui_ready = False
        self._compact_layout: bool | None = None
        self._pending_export = False
        self._chosen_replace_mode: str | None = None
        self._current_export_track: str | None = None
        self._scan_snapshot = None
        self._scan_selection = set()
        self._tracks_shown_for_scan = None
        self._last_scan = 0.0
        self._closing = False
        self._readiness_ok = False

        self._build_ui()
        self._quit_shortcut = QShortcut(QKeySequence.Quit, self)
        self._quit_shortcut.setContext(Qt.ApplicationShortcut)
        self._quit_shortcut.activated.connect(self.close)
        self._ui_ready = True
        self._apply_preferences_to_ui()
        if is_launch_agent_installed():
            remove_launch_agent()
        QTimer.singleShot(0, self.scan_current_set)

    def _build_ui(self) -> None:
        self.setStyleSheet(stylesheet_for_scale(self.ui_scale))
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        self.window_layout = QVBoxLayout(central)
        self.window_layout.setContentsMargins(0, 0, 0, 0)
        self.window_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("mainScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setObjectName("mainScrollContent")
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setContentsMargins(*self.ui_sizes["window_margins"])
        self.content_layout.setSpacing(0)

        self.content_layout.addWidget(self._build_header_section())
        self.content_layout.addSpacing(int(self.ui_sizes["header_bottom_spacing"]))
        self.content_layout.addWidget(self._build_export_range_banner())
        self.content_layout.addSpacing(int(self.ui_sizes["header_bottom_spacing"]))
        self.content_layout.addWidget(self._build_detected_stems_section())
        self.content_layout.addSpacing(int(self.ui_sizes["export_top_spacing"]))
        self.content_layout.addWidget(self._build_export_section())
        self.content_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        self.window_layout.addWidget(scroll_area, 1)

        self.footer_dock = QWidget()
        self.footer_dock.setObjectName("footerDock")
        self.footer_dock.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QVBoxLayout(self.footer_dock)
        footer_layout.setContentsMargins(*self.ui_sizes["footer_margins"])
        footer_layout.setSpacing(int(self.ui_sizes["footer_spacing"]))
        footer_layout.addWidget(self._build_progress_section())
        self.action_layout = self._build_action_row()
        footer_layout.addLayout(self.action_layout)
        self.window_layout.addWidget(self.footer_dock)

    def _build_export_range_banner(self) -> QWidget:
        banner = QWidget()
        banner.setObjectName("exportRangeBanner")
        banner.setAttribute(Qt.WA_StyledBackground, True)
        banner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.export_range_banner = banner

        layout = QVBoxLayout(banner)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(2)

        self.export_range_label = QLabel("Range Selected")
        self.export_range_label.setObjectName("exportRangeLabel")

        self.export_range_headline = QLabel()
        self.export_range_headline.setObjectName("exportRangeHeadline")
        self.export_range_headline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        left_col.addWidget(self.export_range_label)
        left_col.addWidget(self.export_range_headline)

        self.export_range_meta = QLabel()
        self.export_range_meta.setObjectName("exportRangeMeta")
        self.export_range_meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top_row.addLayout(left_col, 1)
        top_row.addWidget(self.export_range_meta, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.export_range_ruler = RangeRuler()

        layout.addLayout(top_row)
        layout.addWidget(self.export_range_ruler)
        self._update_export_range_banner(None)
        return banner

    def _update_export_range_banner(self, export_range: ExportRange | None) -> None:
        default_start, default_end = DEFAULT_RANGE_BARS
        if export_range is None or export_range.length_beats <= 0:
            start_bar, end_bar = default_start, default_end
            headline = f"Bars {default_start} to {default_end}"
            detail = f"{default_end - default_start + 1} bars"
        else:
            start_bar = export_range.start_bar
            end_bar = export_range.end_bar
            headline, detail = export_range.describe()

        self.export_range_headline.setText(headline)
        self.export_range_meta.setText(detail)
        self.export_range_ruler.set_range(start_bar, end_bar, _ruler_total_bars(end_bar))

    def _build_header_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("appHeader")
        layout = QHBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Keep hidden compatibility objects requested by design spec
        self.app_title = QLabel("Stems")
        self.app_title.setObjectName("appTitle")
        self.app_title.hide()
        self._app_mark = QLabel()
        self._app_mark.setPixmap(_app_icon().pixmap(QSize(28, 28)))
        self._app_mark.setFixedSize(28, 28)
        self._app_mark.hide()

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(4)

        self.song_value = QLabel("No set scanned")
        self.song_value.setObjectName("currentSetValue")
        self.song_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.song_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.song_value.setWordWrap(True)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(0)

        self.bpm_value = QLabel("Tempo unknown")
        self.bpm_value.setObjectName("currentSetBpm")
        self._meta_sep = QLabel(" · ")
        self._meta_sep.setObjectName("currentSetMetaSep")
        self.selection_count_label = QLabel("0 selected")
        self.selection_count_label.setObjectName("selectionCount")

        meta_row.addWidget(self.bpm_value)
        meta_row.addWidget(self._meta_sep)
        meta_row.addWidget(self.selection_count_label)
        meta_row.addStretch(1)

        left_col.addWidget(self.song_value)
        left_col.addLayout(meta_row)

        self.preferences_button = QPushButton()
        self.preferences_button.setObjectName("headerAction")
        self.preferences_button.setToolTip("Preferences")
        self.preferences_button.setAccessibleName(self.preferences_button.toolTip())
        self.preferences_button.setIcon(_gear_icon())
        self.preferences_button.setIconSize(QSize(16, 16))
        header_button = int(self.ui_sizes["header_button"])
        self.preferences_button.setFixedSize(QSize(header_button, header_button))
        self.preferences_button.clicked.connect(self.show_preferences)

        layout.addLayout(left_col, 1)
        layout.addWidget(self.preferences_button, 0, Qt.AlignTop | Qt.AlignRight)
        return section

    def _build_detected_stems_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("detectedStemsSection")
        self.stems_layout = QVBoxLayout(section)
        self.stems_layout.setContentsMargins(0, 0, 0, 0)
        self.stems_layout.setSpacing(0)

        self.track_list = QListWidget()
        self.track_list.setObjectName("stemTrackList")
        self.track_list.setFrameShape(QFrame.NoFrame)
        self.track_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.track_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.track_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.track_list.setFocusPolicy(Qt.NoFocus)

        self.empty_stems_label = QLabel(
            "Open a saved Ableton set to list stems.\nName exportable group tracks in ALL CAPS."
        )
        self.empty_stems_label.setObjectName("emptyStems")
        self.empty_stems_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.empty_stems_label.setWordWrap(True)

        self.stems_layout.addWidget(self.track_list)
        self.stems_layout.addWidget(self.empty_stems_label)
        self.track_list.hide()
        return section

    def _build_export_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("exportSection")
        self.export_section = section
        self.export_options_layout = QGridLayout(section)
        self.export_options_layout.setContentsMargins(0, 0, 0, 0)
        self.export_options_layout.setHorizontalSpacing(12)
        self.export_options_layout.setVerticalSpacing(16)

        self.project_name_input = QLineEdit()
        self.project_name_input.setObjectName("exportInput")
        self.project_name_input.setPlaceholderText("Song name override")
        self.project_name_input.setFixedHeight(int(self.ui_sizes["field_height"]))
        self._apply_placeholder_color(self.project_name_input)
        self.project_name_input.textChanged.connect(self.update_destination_preview)

        self.key_input = QLineEdit()
        self.key_input.setObjectName("exportInput")
        self.key_input.setPlaceholderText("Optional, e.g. F# minor")
        self.key_input.setFixedHeight(int(self.ui_sizes["field_height"]))
        self._apply_placeholder_color(self.key_input)
        self.key_input.textChanged.connect(self.update_destination_preview)

        self.artist_input = QLineEdit()
        self.artist_input.setObjectName("exportInput")
        self.artist_input.setPlaceholderText("Optional")
        self.artist_input.setFixedHeight(int(self.ui_sizes["field_height"]))
        self._apply_placeholder_color(self.artist_input)
        self.artist_input.textChanged.connect(self.update_destination_preview)

        self.destination_value = PathTrail()
        self.destination_value.clicked.connect(self.open_export_folder)

        project_label = self._build_field_label("Song name")
        key_label = self._build_field_label("Key")
        artist_label = self._build_field_label("Artist")
        dest_label = self._build_field_label("Saves to")

        self.export_labels = (project_label, key_label, artist_label, dest_label)
        self.destination_control = QWidget()
        self.destination_control.setObjectName("destinationControl")
        destination_layout = QHBoxLayout(self.destination_control)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        destination_layout.setSpacing(8)
        destination_layout.addWidget(self.destination_value, 1)

        self.export_field_pairs = (
            (project_label, self.project_name_input),
            (key_label, self.key_input),
            (artist_label, self.artist_input),
            (dest_label, self.destination_control),
        )
        self._export_pair_widgets = tuple(
            self._wrap_field_pair(label, control, spacing=6 if index < 3 else 4)
            for index, (label, control) in enumerate(self.export_field_pairs)
        )
        self._arrange_export_fields(compact=False)
        return section

    @staticmethod
    def _apply_placeholder_color(line_edit: QLineEdit) -> None:
        palette = line_edit.palette()
        palette.setColor(QPalette.PlaceholderText, QColor("#85858b"))
        line_edit.setPalette(palette)

    @staticmethod
    def _wrap_field_pair(label: QLabel, control: QWidget, *, spacing: int) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(spacing)
        layout.addWidget(label)
        layout.addWidget(control)
        return wrapper

    def _build_progress_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("progressCard")
        section.setAttribute(Qt.WA_StyledBackground, True)
        policy = section.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        section.setSizePolicy(policy)
        self.progress_card = section

        self._progress_opacity = QGraphicsOpacityEffect(section)
        self._progress_opacity.setOpacity(0.0)
        section.setGraphicsEffect(self._progress_opacity)
        self._progress_state = "idle"
        self._scan_complete_timer = QTimer(self)
        self._scan_complete_timer.setSingleShot(True)
        self._scan_complete_timer.setInterval(SCAN_COMPLETE_HOLD_MS)
        self._scan_complete_timer.timeout.connect(self._fade_out_scan_complete)

        self.progress_layout = QVBoxLayout(section)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(int(self.ui_sizes["progress_spacing"]))

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("progressStatus")
        self.progress_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.progress_status_row = QHBoxLayout()
        self.progress_status_row.setContentsMargins(0, 0, 0, 0)
        self.progress_status_row.setSpacing(int(self.ui_sizes["progress_header_spacing"]))

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setObjectName("progressPercent")
        self.progress_percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.progress_percent_label.setMinimumWidth(int(self.ui_sizes["progress_percent_width"]))

        self.progress_status_row.addWidget(self.progress_label)
        self.progress_status_row.addStretch(1)
        self.progress_status_row.addWidget(self.progress_percent_label)

        self.progress_bar = SmoothProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(int(self.ui_sizes["progress_bar_height"]))
        self.progress_bar.displayRatioChanged.connect(self._refresh_progress_percent)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("progressDetail")
        self.summary_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.progress_layout.addLayout(self.progress_status_row)
        self.progress_layout.addWidget(self.progress_bar)
        self.progress_layout.addWidget(self.summary_label)
        self._set_progress_state("idle")
        return section

    def _build_action_row(self) -> QGridLayout:
        actions = QGridLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(int(self.ui_sizes["action_spacing"]))

        self.retry_button = QPushButton("Try again")
        self.retry_button.setObjectName("primaryAction")
        self.retry_button.clicked.connect(self.scan_current_set)
        self.retry_button.hide()

        self.export_button = QPushButton("Export stems")
        self.export_button.setObjectName("secondary")
        self.export_button.setToolTip("Export selected stems and overwrite matching files.")
        self.export_button.clicked.connect(self.confirm_export)
        self.export_button.setEnabled(False)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.clicked.connect(self.cancel_export)
        self.cancel_button.setEnabled(False)
        self.cancel_button.hide()

        self.open_button = QPushButton("Open folder")
        self.open_button.setObjectName("secondary")
        self.open_button.clicked.connect(self.open_export_folder)
        self.open_button.setEnabled(False)
        self.open_button.hide()

        self._action_spacer = QWidget()
        self._action_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._action_spacer.setFixedHeight(1)

        self.action_buttons = (self.open_button, self.retry_button, self.cancel_button, self.export_button)
        for button in self.action_buttons:
            button.setProperty("actionBarButton", True)
            button.setMinimumHeight(int(self.ui_sizes["action_height"]))
            button.setMaximumHeight(int(self.ui_sizes["action_height"]))

        self._refresh_action_hierarchy()
        return actions

    def _arrange_action_buttons(self, compact: bool) -> None:
        for button in self.action_buttons:
            self.action_layout.removeWidget(button)
        self.action_layout.removeWidget(self._action_spacer)

        for col in range(5):
            self.action_layout.setColumnStretch(col, 0)

        if compact:
            self._action_spacer.hide()
            for button in self.action_buttons:
                button.setMinimumWidth(0)
            compact_order = (self.retry_button, self.open_button, self.cancel_button, self.export_button)
            visible_buttons = [button for button in compact_order if not button.isHidden()]
            for index, button in enumerate(visible_buttons):
                span = 2 if index == len(visible_buttons) - 1 and len(visible_buttons) % 2 else 1
                self.action_layout.addWidget(button, index // 2, index % 2, 1, span)
            self.action_layout.setColumnStretch(0, 1)
            self.action_layout.setColumnStretch(1, 1)
        else:
            min_w = int(self.ui_sizes["action_min_width"])
            for button in self.action_buttons:
                button.setMinimumWidth(min_w)
            self._action_spacer.show()
            self.action_layout.addWidget(self.open_button, 0, 0)
            self.action_layout.addWidget(self._action_spacer, 0, 1)
            self.action_layout.addWidget(self.retry_button, 0, 2)
            self.action_layout.addWidget(self.cancel_button, 0, 3)
            self.action_layout.addWidget(self.export_button, 0, 4)
            self.action_layout.setColumnStretch(1, 1)

    def _arrange_export_fields(self, compact: bool) -> None:
        for widget in self._export_pair_widgets:
            self.export_options_layout.removeWidget(widget)
        project_pair, key_pair, artist_pair, dest_pair = self._export_pair_widgets
        if compact:
            self.export_options_layout.addWidget(project_pair, 0, 0)
            self.export_options_layout.addWidget(key_pair, 1, 0)
            self.export_options_layout.addWidget(artist_pair, 2, 0)
            self.export_options_layout.addWidget(dest_pair, 3, 0)
            self.export_options_layout.setColumnStretch(0, 1)
            self.export_options_layout.setColumnStretch(1, 0)
            self.export_options_layout.setColumnStretch(2, 0)
        else:
            self.export_options_layout.addWidget(project_pair, 0, 0)
            self.export_options_layout.addWidget(key_pair, 0, 1)
            self.export_options_layout.addWidget(artist_pair, 0, 2)
            self.export_options_layout.addWidget(dest_pair, 1, 0, 1, 3)
            self.export_options_layout.setColumnStretch(0, 1)
            self.export_options_layout.setColumnStretch(1, 1)
            self.export_options_layout.setColumnStretch(2, 1)

    def _set_export_enabled(self, enabled: bool) -> None:
        self.export_button.setEnabled(enabled)
        count = len(self.current_job.selected_tracks) if self.current_job else 0
        self.export_button.setText(f"Export {count} stem{'s' if count != 1 else ''}" if count else "Export stems")
        self._refresh_action_hierarchy()

    def _set_open_available(self, available: bool) -> None:
        self.open_button.setEnabled(available)
        self.open_button.setVisible(available)
        if hasattr(self, "action_layout"):
            self._arrange_action_buttons(self.width() < COMPACT_LAYOUT_BREAKPOINT)

    def _set_cancel_available(self, available: bool) -> None:
        self.cancel_button.setEnabled(available)
        self.cancel_button.setVisible(available)
        if hasattr(self, "action_layout"):
            self._arrange_action_buttons(self.width() < COMPACT_LAYOUT_BREAKPOINT)

    def _refresh_action_hierarchy(self) -> None:
        export_is_primary = self.export_button.isEnabled()
        self.retry_button.setObjectName("secondary" if export_is_primary else "primaryAction")
        self.export_button.setObjectName("primaryAction" if export_is_primary else "secondary")
        for button in (self.retry_button, self.export_button):
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _build_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().resizeEvent(event)
        if not getattr(self, "_ui_ready", False):
            return
        compact = event.size().width() < COMPACT_LAYOUT_BREAKPOINT
        if compact != self._compact_layout:
            self._compact_layout = compact
            self._arrange_export_fields(compact)
            self._arrange_action_buttons(compact)

    def _apply_preferences_to_ui(self) -> None:
        width = self.preferences.panel_width
        height = self.preferences.panel_height
        if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
            available = self.screen().availableGeometry()
            self.resize(
                min(max(width, MINIMUM_WINDOW_SIZE[0]), available.width()),
                min(max(height, MINIMUM_WINDOW_SIZE[1]), available.height()),
            )
        else:
            self.resize(*REFERENCE_WINDOW_SIZE)
        compact = self.width() < COMPACT_LAYOUT_BREAKPOINT
        self._compact_layout = compact
        self._arrange_export_fields(compact)
        self._arrange_action_buttons(compact)
        if self.preferences.panel_x is not None and self.preferences.panel_y is not None:
            self.move(self.preferences.panel_x, self.preferences.panel_y)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if (event.type() == QEvent.ActivationChange and self.isActiveWindow()
                and getattr(self, "_ui_ready", False) and not self._closing
                and time.monotonic() - self._last_scan > 2):
            QTimer.singleShot(0, self._refresh_on_focus)

    def _refresh_on_focus(self) -> None:
        if self.isActiveWindow() and not self._closing and self.export_thread is None and self.scan_thread is None:
            self.scan_current_set()

    @staticmethod
    def _track_signature(tracks: list[StemTrack]) -> tuple[tuple[int, str], ...]:
        return tuple((track.index, track.name) for track in tracks)

    def _set_snapshot(self):
        if self.project is None:
            return None
        return (self.project.project_folder, self.project.song_name,
                self._track_signature(self.state.detected_tracks))

    def scan_current_set(self) -> None:
        if self.scan_thread is not None or self.export_thread is not None or self._closing:
            return
        self._last_scan = time.monotonic()
        self._scan_snapshot = self._set_snapshot()
        self._scan_selection = {(t.index, t.name) for t in self._selected_tracks()}
        self._tracks_shown_for_scan = None
        self._readiness_ok = False
        self.retry_button.hide()
        self._arrange_action_buttons(self.width() < COMPACT_LAYOUT_BREAKPOINT)
        self.retry_button.setEnabled(False)
        self._set_export_enabled(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("scanning")
        self.progress_label.setText("Scanning Ableton set")
        self._set_progress_detail("Reading song, tempo, folder, and stem groups")

        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(self.state)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.tracks_ready.connect(self._handle_tracks_ready)
        self.scan_worker.finished.connect(self._handle_scan_success)
        self.scan_worker.failed.connect(self._handle_scan_failure)
        self.scan_worker.finished.connect(self._cleanup_scan_thread)
        self.scan_worker.failed.connect(self._cleanup_scan_thread)
        self.scan_thread.start()

    def _restore_scan_selection(self, tracks: list[StemTrack]) -> None:
        """Restore checkbox selections captured at the start of a scan."""
        for track in tracks:
            row = self.track_list.itemWidget(self.item_by_track_name[track.name])
            selected = (track.index, track.name) in self._scan_selection
            if isinstance(row, StemTrackRow):
                row.set_checked_immediate(selected)
            else:
                row.checkbox.setChecked(selected)

    def _handle_tracks_ready(self, tracks: list[StemTrack]) -> None:
        """Display detected stem rows while project folder lookup continues."""
        track_tuple = self._track_signature(tracks)
        self._populate_tracks(tracks)
        if self._scan_snapshot is not None and self._scan_snapshot[2] == track_tuple:
            self._restore_scan_selection(tracks)
        self._tracks_shown_for_scan = track_tuple
        count = len(tracks)
        self._set_progress_detail(f"Found {count} stem{'s' if count != 1 else ''}, finding project folder")
        self._set_export_enabled(False)

    def _handle_scan_success(self, state, project) -> None:
        self.state = state
        previous_project = self.project
        self.project = project
        self._readiness_ok = True
        changed = self._scan_snapshot is not None and self._scan_snapshot != self._set_snapshot()
        if previous_project and (previous_project.project_folder, previous_project.song_name) != (project.project_folder, project.song_name):
            self.project_name_input.clear()
            self.key_input.clear()
            self.artist_input.clear()
        self.song_value.setText(project.song_name)
        self.project_name_input.setPlaceholderText(project.song_name)
        self.bpm_value.setText(f"{project.bpm} BPM" if project.bpm is not None else "Tempo unknown")
        self._update_export_range_banner(getattr(state, "export_range", None))
        track_tuple = self._track_signature(state.detected_tracks)
        if self._tracks_shown_for_scan != track_tuple:
            self._populate_tracks(state.detected_tracks)
            if self._scan_snapshot is not None and not changed:
                self._restore_scan_selection(state.detected_tracks)
        self.update_destination_preview()
        count = len(state.detected_tracks)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_label.setText("Scan complete")
        self._set_progress_detail(f"Detected {count} stem{'s' if count != 1 else ''}")
        if self._pending_export and changed:
            self._pending_export = False
            self._set_progress_state("scan-changed")
            self.progress_label.setText("Set changed")
            self._set_progress_detail("Tracks updated. Review selection, then click Export stems.")
        elif self.isVisible():
            self._set_progress_state("scan-complete")
            self._scan_complete_timer.start()
        else:
            self._set_progress_state("idle")
        self._set_export_enabled(bool(self._selected_tracks()))
        self._set_open_available(self.current_job is not None or self.project is not None)

    def _handle_scan_failure(self, message: str) -> None:
        self._update_export_range_banner(None)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("scan-failed")
        self.progress_label.setText("Scan failed")
        self._set_progress_detail(message)
        self._readiness_ok = False
        self._pending_export = False
        self.project = None
        self.current_job = None
        self.update_destination_preview()
        self._set_export_enabled(False)
        self.retry_button.show()
        self._arrange_action_buttons(self.width() < COMPACT_LAYOUT_BREAKPOINT)

    def _cleanup_scan_thread(self, *_args) -> None:
        if self.scan_thread is not None:
            self.scan_thread.quit()
            self.scan_thread.wait()
        self.scan_thread = None
        self.scan_worker = None
        if self._closing:
            QTimer.singleShot(0, self.close)
        self.retry_button.setEnabled(True)
        self.update_destination_preview()
        if self._pending_export and not self._closing:
            self._pending_export = False
            self.start_export()

    def _populate_tracks(self, tracks: list[StemTrack]) -> None:
        self.track_list.setVisible(bool(tracks))
        self.empty_stems_label.setVisible(not tracks)
        self.empty_stems_label.setText(
            "No stems found.\nName group tracks in ALL CAPS in Ableton, then switch back."
        )
        row_height = int(self.ui_sizes["stem_row_height"])
        new_names = {track.name for track in tracks}

        existing_widgets: dict[str, tuple[QListWidgetItem, StemTrackRow]] = {}
        for name, item in list(self.item_by_track_name.items()):
            row = self.track_list.itemWidget(item)
            idx = self.track_list.row(item)
            if idx < 0 or not isinstance(row, StemTrackRow):
                continue
            if name not in new_names:
                row.stop_animations()
                self.track_list.takeItem(idx)
                row.hide()
                row.setParent(None)
                row.deleteLater()
            else:
                existing_widgets[name] = (item, row)

        self.item_by_track_name.clear()
        self.status_by_track_name.clear()

        animate_new = self.isVisible() and self.track_list.isVisible()
        for target_idx, track in enumerate(tracks):
            display_index = target_idx + 1
            reused = existing_widgets.get(track.name)
            if reused is not None:
                item, row = reused
                current_idx = self.track_list.row(item)
                if current_idx != target_idx:
                    row.setParent(None)
                    taken = self.track_list.takeItem(current_idx)
                    self.track_list.insertItem(target_idx, taken)
                    self.track_list.setItemWidget(taken, row)
                    item = taken
                item.setSizeHint(QSize(0, row_height))
                row.update_track(track, display_index, sizes=self.ui_sizes)
            else:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, row_height))
                self.track_list.insertItem(target_idx, item)
                row = StemTrackRow(
                    track,
                    display_index,
                    sizes=self.ui_sizes,
                    show_separator=display_index < len(tracks),
                )
                row.checkbox.toggled.connect(self._handle_track_selection_changed)
                self.track_list.setItemWidget(item, row)
                if animate_new:
                    row.fade_in(DURATION_REBUILD)
            self.item_by_track_name[track.name] = item
            self.status_by_track_name[track.name] = row.status_label

        self.track_list.setFixedHeight(len(tracks) * row_height if tracks else 0)
        self._refresh_selection_count()

    def _handle_track_selection_changed(self, *_args) -> None:
        self._refresh_selection_count()
        self.update_destination_preview()

    def _refresh_selection_count(self) -> None:
        selected = len(self._selected_tracks())
        self.selection_count_label.setText(f"{selected} selected")

    def _selected_tracks(self) -> list[StemTrack]:
        if self.state is None:
            return []
        selected: list[StemTrack] = []
        for track in self.state.detected_tracks:
            item = self.item_by_track_name.get(track.name)
            if item is None:
                continue
            row = self.track_list.itemWidget(item)
            checkbox = row.findChild(QCheckBox)
            if checkbox is not None and checkbox.isChecked():
                selected.append(replace(track, selected=True))
        return selected

    def update_destination_preview(self) -> None:
        if self.state is None or self.project is None:
            self.destination_value.setText("-")
            self.destination_value.setToolTip("")
            self._export_pair_widgets[3].setVisible(False)
            self._set_open_available(False)
            return
        self._export_pair_widgets[3].setVisible(True)
        tracks = self._selected_tracks()
        custom_song_name = self.project_name_input.text().strip() or None
        key = self.key_input.text().strip() or None
        artist = self.artist_input.text().strip() or None
        replace_mode = self._chosen_replace_mode or self.preferences.replace_mode
        if replace_mode == "ask":
            replace_mode = "replace"  # Real choice is made in the confirm box.
        job = self.state.build_export_job(
            key=key,
            artist=artist,
            replace_mode=replace_mode,
            destination_root=None,
            custom_song_name=custom_song_name,
            stem_name_format=self.preferences.stem_name_format,
            folder_name_format=self.preferences.folder_name_format,
        )
        self.current_job = replace(job, tracks=tracks)
        self.destination_value.setPath(
            self.current_job.stems_dir,
            existing=self.current_job.stems_dir.is_dir(),
        )
        self.destination_value.setToolTip(str(self.current_job.stems_dir))
        self._set_export_enabled(
            self._readiness_ok
            and self.scan_thread is None
            and self.export_thread is None
            and bool(self.current_job.selected_tracks)
        )
        self._set_open_available(True)

    def show_preferences(self) -> None:
        dialog = PreferencesDialog(self.preferences, self)
        dialog.preferences_changed.connect(self._save_preferences_from_dialog)
        dialog.exec()

    def _save_preferences_from_dialog(self, updated: Preferences) -> None:
        self.preferences = updated
        self.preferences_store.save(self.preferences)
        self.update_destination_preview()

    def confirm_export(self) -> None:
        if self.scan_thread is not None or self.export_thread is not None:
            return
        self.update_destination_preview()
        if self.current_job is None or not self.current_job.selected_tracks:
            return
        export_range = getattr(self.state, "export_range", None)
        if export_range is not None:
            range_headline, range_detail = export_range.describe()
        else:
            default_start, default_end = DEFAULT_RANGE_BARS
            default_bars = default_end - default_start + 1
            range_headline = f"Bars {default_start} to {default_end}"
            range_detail = f"{default_bars} bars"
        conflicts = find_conflicts(self.current_job)
        confirm = ExportConfirmDialog(
            self.current_job,
            range_headline=range_headline,
            range_detail=range_detail,
            conflict_count=len(conflicts),
            replace_mode=self.preferences.replace_mode,
            parent=self,
        )
        confirm.exec()
        if confirm.chosen_mode is None:
            return
        self._chosen_replace_mode = confirm.chosen_mode
        self._pending_export = True
        self.scan_current_set()

    def _set_export_always_on_top(self, enabled: bool) -> None:
        is_on_top = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        if is_on_top == enabled:
            return
        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
        if was_visible:
            self.setGeometry(geometry)
            self.show()
            if enabled:
                self.raise_()

    def _bring_to_front(self) -> None:
        self._last_scan = time.monotonic()
        self.raise_()
        self.activateWindow()
        if self.isVisible():
            bring_process_to_front()

    def start_export(self) -> None:
        if self.current_job is None or not self.current_job.selected_tracks or self.export_thread is not None:
            return

        self._set_export_always_on_top(True)

        for item in self.item_by_track_name.values():
            row = self.track_list.itemWidget(item)
            if isinstance(row, StemTrackRow):
                row.reset_status()

        self.export_cancel_requested = False
        self.progress_bar.setRange(0, len(self.current_job.selected_tracks) or 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("export-starting")
        self.progress_label.setText("Preparing export")
        self._set_export_progress_detail(completed=0)
        self.retry_button.setEnabled(False)
        self._set_export_enabled(False)
        self._set_cancel_available(True)
        self.project_name_input.setEnabled(False)
        self.key_input.setEnabled(False)
        self.artist_input.setEnabled(False)
        self.track_list.setEnabled(False)
        self.preferences_button.setEnabled(False)

        self.export_thread = QThread(self)
        self.export_worker = ExportWorker(self.state, self.current_job)
        self.export_worker.moveToThread(self.export_thread)
        self.export_thread.started.connect(self.export_worker.run)
        self.export_worker.progress.connect(self._handle_export_progress)
        self.export_worker.finished.connect(self._handle_export_finished)
        self.export_worker.failed.connect(self._handle_export_failed)
        self.export_worker.finished.connect(self._cleanup_export_thread)
        self.export_worker.failed.connect(self._cleanup_export_thread)
        self.export_thread.start()

    def _handle_export_progress(self, event: str, message: str) -> None:
        if event == "preflight":
            self._set_progress_state("export-starting")
            self.progress_label.setText("Preparing export")
        elif event == "cancelled":
            self._set_progress_state("cancelled")
            self.progress_label.setText("Export cancelled")
        else:
            self._set_progress_state("export-in-progress")
        if event == "wait":
            self._bring_to_front()
        elif event == "stem":
            parts, _, track_name = message.partition(" ")
            current_index = int(parts.split("/")[0])
            self.progress_bar.setValue(current_index - 1)
            self.progress_label.setText(f"Exporting {track_name}")
            self._current_export_track = track_name
            label = self.status_by_track_name.get(track_name)
            if label is not None:
                self._set_track_status(label, "exporting")
        elif event == "retry":
            label = self.status_by_track_name.get(self._current_export_track or "")
            if label is not None:
                self._set_track_status(label, "retrying")
            self.progress_label.setText(message)
        elif event in {"success", "skipped", "failed"}:
            self.progress_bar.setValue(min(self.progress_bar.value() + 1, self.progress_bar.maximum()))
            if event == "success":
                track_name = message.replace("Exported ", "", 1)
            elif event == "skipped":
                track_name = message.replace("Skipped ", "", 1)
            else:
                track_name = message.split(":", 1)[0]
            label = self.status_by_track_name.get(track_name)
            if label is not None:
                reason = message.split(":", 1)[1].strip() if event == "failed" and ":" in message else ""
                self._set_track_status(label, event, reason=reason)
        self._set_export_progress_detail()

    def _set_track_status(self, label: QLabel, status: str, reason: str = "") -> None:
        was_hidden = label.isHidden()
        text = {
            "exporting": "Exporting",
            "retrying": "Retrying",
            "success": "Exported",
            "skipped": "Already there",
            "failed": "Failed",
        }.get(status, status.title())
        if reason:
            text = f"Failed · {reason}"
        label.setText(text)
        label.setToolTip(text)
        label.setProperty("statusState", status)
        label.show()
        label.style().unpolish(label)
        label.style().polish(label)
        parent = label.parentWidget()
        while parent is not None and not isinstance(parent, StemTrackRow):
            parent = parent.parentWidget()
        if parent is not None:
            parent.set_status_state(status, was_hidden=was_hidden)
            parent.update()

    def _fade_out_scan_complete(self) -> None:
        if self._progress_state == "scan-complete":
            self._set_progress_state("idle")

    def _set_progress_state(self, status: str) -> None:
        self._progress_state = status
        if hasattr(self, "_scan_complete_timer") and status != "scan-complete":
            self._scan_complete_timer.stop()
        for widget in (
            self.progress_card,
            self.progress_label,
            self.progress_percent_label,
            self.progress_bar,
            self.summary_label,
        ):
            widget.setProperty("progressState", status)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        show_meter = status in {"export-starting", "export-in-progress", "cancelling", "cancelled"}
        self.progress_bar.setVisible(show_meter)
        self.progress_percent_label.setVisible(show_meter)

        if status == "idle":
            if self.isVisible():
                if self.progress_card.height() > 0:
                    self.progress_card.setMinimumHeight(self.progress_card.height())
                self.progress_card.setVisible(True)
                if effective_duration(DURATION_BASE) > 0 and self._progress_opacity.opacity() > 0.0:
                    fade_widget(
                        self.progress_card,
                        0.0,
                        DURATION_BASE,
                        effect=self._progress_opacity,
                    )
                else:
                    stop_fade_widget(self.progress_card)
                    self._progress_opacity.setOpacity(0.0)
            else:
                stop_fade_widget(self.progress_card)
                self._progress_opacity.setOpacity(0.0)
                self.progress_card.setVisible(False)
        elif status in {"scanning", "scan-complete"}:
            self.progress_card.setMinimumHeight(0)
            self.progress_card.setVisible(True)
            fade_widget(
                self.progress_card,
                1.0,
                DURATION_FAST,
                effect=self._progress_opacity,
                animate=self.isVisible(),
            )
        else:
            self.progress_card.setMinimumHeight(0)
            stop_fade_widget(self.progress_card)
            self._progress_opacity.setOpacity(1.0)
            self.progress_card.setVisible(True)

        self._refresh_progress_percent()

    def _set_progress_detail(self, text: str) -> None:
        self.summary_label.setText(text)
        self.summary_label.setToolTip(text)

    def _set_export_progress_detail(self, *, completed: int | None = None) -> None:
        if self.current_job is None:
            return
        total = len(self.current_job.selected_tracks)
        completed_count = self.progress_bar.value() if completed is None else completed
        stem_word = "stem" if total == 1 else "stems"
        self._set_progress_detail(
            f"{completed_count} of {total} {stem_word} · Saving to {self.current_job.stems_dir}\n"
            "Keep the keyboard and mouse free. Move the pointer to a screen corner to stop."
        )

    def _refresh_progress_percent(self, *_args) -> None:
        if hasattr(self.progress_bar, "display_ratio"):
            percent = round(self.progress_bar.display_ratio * 100)
        else:
            maximum = self.progress_bar.maximum()
            minimum = self.progress_bar.minimum()
            span = maximum - minimum
            if span <= 0:
                percent = 0
            else:
                percent = round(((self.progress_bar.value() - minimum) / span) * 100)
        self.progress_percent_label.setText(f"{max(0, min(percent, 100))}%")

    def _handle_export_finished(self, result: ExportResult) -> None:
        self.current_result = result
        self._chosen_replace_mode = None
        failures = [
            f"{item.track.name} ({short_failure_reason(item.error or '')})"
            for item in result.items
            if item.status == "failed"
        ]
        total = len(result.job.selected_tracks)
        summary = f"Exported {result.success_count}/{total} stems to {result.job.stems_dir}."
        if failures:
            summary += f" Failed: {', '.join(failures)}."
        if self.export_cancel_requested:
            self._set_progress_state("cancelled")
            self.progress_label.setText("Export cancelled")
            summary = f"Cancelled after exporting {result.success_count}/{total} stems to {result.job.stems_dir}."
            if failures:
                summary += f" Failed before cancellation: {', '.join(failures)}."
        else:
            self.progress_bar.setValue(self.progress_bar.maximum())
            self._set_progress_state("export-complete")
            self.progress_label.setText("Export complete")
        self._set_progress_detail(summary)
        self._set_open_available(True)
        self._set_export_always_on_top(False)
        self._bring_to_front()
        if self.preferences.auto_open_folder:
            self.open_export_folder()

    def _handle_export_failed(self, message: str) -> None:
        self._chosen_replace_mode = None
        self._set_progress_state("export-failed")
        self.progress_label.setText("Export failed")
        self._set_progress_detail(message)
        self._set_export_always_on_top(False)
        self._bring_to_front()
        QMessageBox.warning(self, "Export failed", message)

    def _cleanup_export_thread(self, *_args) -> None:
        if self.export_thread is not None:
            self.export_thread.quit()
            self.export_thread.wait()
        self.export_thread = None
        self.export_worker = None
        self._set_export_always_on_top(False)
        self._last_scan = time.monotonic()
        if self._closing:
            QTimer.singleShot(0, self.close)
        self.retry_button.setEnabled(True)
        self._set_cancel_available(False)
        self.project_name_input.setEnabled(True)
        self.key_input.setEnabled(True)
        self.artist_input.setEnabled(True)
        self.track_list.setEnabled(True)
        self.preferences_button.setEnabled(True)
        self.update_destination_preview()

    def cancel_export(self) -> None:
        if self.export_worker is None:
            return
        self.export_cancel_requested = True
        self.export_worker.cancel()
        self._set_progress_state("cancelling")
        self.progress_label.setText("Stopping after current stem")
        self._set_export_progress_detail()

    def open_export_folder(self, *_args) -> None:
        if self.current_job is not None:
            path = self.current_job.stems_dir
        elif self.project is not None:
            path = self.project.project_folder
        else:
            return
        while not path.exists() and path != path.parent:
            path = path.parent
        subprocess.run(["open", str(path)], check=False)

    def _reserve_scan_progress_height(self) -> int:
        status_h = self.progress_label.sizeHint().height()
        detail_h = self.summary_label.sizeHint().height()
        return max(0, status_h + self.progress_layout.spacing() + detail_h)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().showEvent(event)
        if self._progress_state == "idle":
            reserved = self._reserve_scan_progress_height()
            if reserved > 0:
                self.progress_card.setMinimumHeight(reserved)
            self._progress_opacity.setOpacity(0.0)
            self.progress_card.setVisible(True)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if hasattr(self, "_scan_complete_timer"):
            self._scan_complete_timer.stop()
        stop_fade_widget(self.progress_card)
        if self._progress_state == "idle":
            self._progress_opacity.setOpacity(0.0)
            self.progress_card.setVisible(False)
        else:
            self._progress_opacity.setOpacity(1.0)
        stop_window_fade(self)
        self.setWindowOpacity(1.0)
        self.export_range_ruler.stop_animations()
        if hasattr(self.progress_bar, "stop_animations"):
            self.progress_bar.stop_animations()
        for idx in range(self.track_list.count()):
            row = self.track_list.itemWidget(self.track_list.item(idx))
            if isinstance(row, StemTrackRow):
                row.stop_animations()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        if self.export_thread is not None:
            event.ignore()
            self.cancel_export()
            self._closing = True
            return
        self._closing = True
        self.preferences.panel_x = self.x()
        self.preferences.panel_y = self.y()
        self.preferences.panel_width = self.width()
        self.preferences.panel_height = self.height()
        self.preferences_store.save(self.preferences)
        self.gateway.stop_listener()
        if self.scan_thread is not None:
            # A scan is mid-flight; don't make quitting wait for it.
            self.scan_thread.quit()
            if not self.scan_thread.wait(300):
                import os
                os._exit(0)
        super().closeEvent(event)
