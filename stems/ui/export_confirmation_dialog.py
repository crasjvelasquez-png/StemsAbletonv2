from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)

from ..models import ExportJob
from .theme import stylesheet_for_scale


class ExportConfirmationDialog(QDialog):
    """Compact, explicit confirmation for the final export action."""

    def __init__(self, job: ExportJob, parent=None, *, scale: float = 1.0) -> None:
        super().__init__(parent)
        self.job = job
        self.scale = max(0.5, min(2.0, float(scale)))
        self.selected_tracks = job.selected_tracks
        self.track_count = len(self.selected_tracks)
        self.destination_path = Path(job.stems_dir).expanduser().resolve()

        self.setObjectName("exportConfirmationDialog")
        self.setWindowTitle("Confirm Export")
        self.setModal(True)
        self.setStyleSheet(stylesheet_for_scale(self.scale))
        self.setAccessibleDescription(f"Export confirmation for {self.destination_path}")

        self._build_ui()
        self._size_to_content()

    def _scaled(self, value: int, *, minimum: int = 1) -> int:
        return max(minimum, round(value * self.scale))

    def _build_ui(self) -> None:
        outer_margin = max(16, self._scaled(20))
        section_spacing = self._scaled(15)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(outer_margin, outer_margin, outer_margin, outer_margin)
        layout.setSpacing(0)

        heading = QLabel(self._heading_text())
        heading.setObjectName("exportConfirmationHeading")
        heading.setWordWrap(True)
        self.heading_label = heading
        layout.addWidget(heading)

        supporting = QLabel("Ableton will export each selected stem to this folder.")
        supporting.setObjectName("exportConfirmationSupporting")
        supporting.setWordWrap(True)
        self.supporting_label = supporting
        layout.addSpacing(self._scaled(6))
        layout.addWidget(supporting)

        layout.addSpacing(section_spacing)
        layout.addWidget(self._separator())
        layout.addSpacing(section_spacing)

        destination_section = QVBoxLayout()
        destination_section.setContentsMargins(0, 0, 0, 0)
        destination_section.setSpacing(self._scaled(4))

        destination_label = QLabel("Destination")
        destination_label.setObjectName("exportConfirmationMetadataLabel")
        destination_section.addWidget(destination_label)

        destination_value = QLabel(self.destination_path.name or str(self.destination_path))
        destination_value.setObjectName("exportConfirmationDestination")
        destination_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        destination_value.setToolTip(str(self.destination_path))
        destination_value.setAccessibleName("Destination folder")
        destination_value.setAccessibleDescription(str(self.destination_path))
        destination_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.destination_label = destination_value
        self.destination_value = destination_value
        destination_section.addWidget(destination_value)

        parent_name = self.destination_path.parent.name or str(self.destination_path.parent)
        destination_parent = QLabel(parent_name)
        destination_parent.setObjectName("exportConfirmationDestinationParent")
        destination_parent.setToolTip(str(self.destination_path.parent))
        destination_parent.setAccessibleName("Destination parent folder")
        destination_parent.setAccessibleDescription(str(self.destination_path.parent))
        self.destination_parent_label = destination_parent
        destination_section.addWidget(destination_parent)
        layout.addLayout(destination_section)

        layout.addSpacing(section_spacing)
        layout.addWidget(self._separator())
        layout.addSpacing(section_spacing)

        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(self._scaled(12))
        mode_label = QLabel("Existing files")
        mode_label.setObjectName("exportConfirmationMetadataLabel")
        mode_value = QLabel(self._mode_text())
        mode_value.setObjectName("exportConfirmationMode")
        mode_value.setProperty("modeState", self.job.replace_mode)
        mode_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mode_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(mode_value, 1)
        self.mode_label = mode_value
        layout.addLayout(mode_row)

        layout.addSpacing(section_spacing)
        layout.addWidget(self._separator())
        layout.addSpacing(section_spacing)

        tracks_heading = QLabel(f"Tracks ({self.track_count})")
        tracks_heading.setObjectName("exportConfirmationMetadataLabel")
        self.tracks_heading = tracks_heading
        layout.addWidget(tracks_heading)
        layout.addSpacing(self._scaled(6))

        track_names = " · ".join(track.name for track in self.selected_tracks)
        tracks_label = self._track_label(track_names)
        track_scroll = QScrollArea()
        track_scroll.setObjectName("exportConfirmationTrackScroll")
        track_scroll.setFrameShape(QFrame.NoFrame)
        track_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        track_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        track_scroll.setWidgetResizable(True)
        track_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        track_scroll.setMaximumHeight(max(self._scaled(112), 88))
        track_scroll.setWidget(self._track_label(track_names))

        self.tracks_label = tracks_label
        self.track_scroll_area = track_scroll
        if self.track_count <= 8:
            layout.addWidget(tracks_label)
            track_scroll.hide()
        else:
            tracks_label.hide()
            layout.addWidget(track_scroll)

        layout.addSpacing(section_spacing)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(self._scaled(8))
        button_row.addStretch(1)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondary")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setAutoDefault(False)
        self.cancel_button = cancel_button

        export_button = QPushButton(self._export_button_text())
        export_button.setObjectName("primaryAction")
        export_button.setDefault(True)
        export_button.setAutoDefault(True)
        export_button.clicked.connect(self.accept)
        self.export_button = export_button

        button_row.addWidget(cancel_button)
        button_row.addWidget(export_button)
        layout.addLayout(button_row)

        self.setTabOrder(cancel_button, export_button)
        export_button.setFocus()

    def _track_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("exportConfirmationTrackList")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        label.setAccessibleName(f"Selected tracks ({self.track_count})")
        label.setAccessibleDescription(text)
        return label

    def _separator(self) -> QFrame:
        separator = QFrame()
        separator.setObjectName("exportConfirmationSeparator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedHeight(1)
        return separator

    def _heading_text(self) -> str:
        noun = "stem" if self.track_count == 1 else "stems"
        return f"Ready to export {self.track_count} {noun}"

    def _export_button_text(self) -> str:
        noun = "Stem" if self.track_count == 1 else "Stems"
        return f"Export {self.track_count} {noun}"

    def _mode_text(self) -> str:
        return "Replace matching files" if self.job.replace_mode == "replace" else "Skip matching files"

    def _size_to_content(self) -> None:
        self.layout().activate()
        width = max(380, self._scaled(480))
        self.setFixedWidth(width)
        self.adjustSize()
        self.layout().activate()
        self.adjustSize()
