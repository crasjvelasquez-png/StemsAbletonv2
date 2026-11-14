"""End-to-end tests for Ableton export range detection and UI display.

Failure modes considered before implementation:
1. Loop off (/live/song/get/loop returns [0]):
   Must report "Whole song" with guidance to turn on the loop brace, not Bars 1 to N.
2. Zero or negative loop length (/live/song/get/loop_length returns [0] or < 0):
   Must behave as whole song ("Whole song") rather than producing inverted bars (e.g. Bars 5 to 4).
3. Non-4/4 time signatures (e.g. 6/8, 3/4, 7/8):
   AbletonOSC reports loop_start and loop_length in quarter-note beats, so 6/8 has
   numerator * 4 / denominator = 3.0 beats per bar, not 6.0 or 4.0.
4. Fractional start or end beats (e.g. loop starts on beat 2.0 of bar 1):
   start_bar = floor(start_beats / beats_per_bar) + 1 and
   end_bar = ceil((start_beats + length_beats) / beats_per_bar) must include both partial bars.
5. Missing or empty OSC reply (gateway.ask returns None or []):
   AbletonClient.get_export_range() must return None and AppState.scan_current_set() must still succeed.
6. Invalid time signature denominator 0 (or <= 0):
   Must defend against ZeroDivisionError and return None instead of crashing the scan.
7. Missing BPM (get_bpm() returns None or 0):
   ExportRange must still produce the bar headline and omit the duration segment rather than failing or dividing by zero.
8. MainWindow state fakes lacking `export_range` or scan failures:
   UI must tolerate fakes without `export_range`, show "Range unknown" when None, and clear stale range on scan failure.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from stems.ableton import AbletonClient
from stems.models import ProjectContext, StemTrack
from stems.preferences import Preferences
from stems.state import AppState
from stems.ui import main_window as main_window_module


class FakeOSCGateway:
    def __init__(self, responses: dict[str, list[object] | None], tracks: dict[int, str] | None = None) -> None:
        self.responses = responses
        self.tracks = tracks if tracks is not None else {0: "DRUMS", 1: "lead", 2: "BASS"}

    def ask(self, address: str, *args):  # noqa: ARG002
        if address == "/live/song/get/num_tracks":
            return [len(self.tracks)]
        return self.responses.get(address)

    def fetch_all_parallel(self, address: str, count: int, timeout: float = 0.0):  # noqa: ARG002
        if address == "/live/track/get/name":
            return {index: self.tracks.get(index, "") for index in range(count)}
        if address == "/live/track/get/color":
            return {}
        return {}


class RaisingRangeClient:
    def get_track_count(self) -> int:
        return 2

    def get_bpm(self) -> int:
        return 120

    def get_all_tracks(self, count: int) -> list[dict[str, object]]:
        assert count == 2
        return [
            {"index": 0, "name": "DRUMS", "color": None},
            {"index": 1, "name": "BASS", "color": None},
        ]

    def get_export_range(self):
        raise RuntimeError("OSC timeout")


def _make_state(responses: dict[str, list[object] | None], project_dir: Path) -> AppState:
    client = AbletonClient(FakeOSCGateway(responses))
    return AppState(
        client,
        project_info_getter=lambda: (project_dir, "Test Song"),
    )


def test_scan_reads_loop_range_in_4_4(tmp_path):
    state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/loop": [1],
            "/live/song/get/loop_start": [64.0],
            "/live/song/get/loop_length": [128.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
    )

    project, tracks = state.scan_current_set()

    assert project.song_name == "Test Song"
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert state.export_range is not None
    headline, detail = state.export_range.describe()
    assert headline == "Bars 17 to 48"
    assert detail == "32 bars, 1:04 long. Set by the loop brace in Ableton."


def test_scan_reports_whole_song_when_loop_disabled_or_zero_length(tmp_path):
    for loop_flag, length in ((0, 128.0), (1, 0.0)):
        state = _make_state(
            {
                "/live/song/get/tempo": [120.0],
                "/live/song/get/loop": [loop_flag],
                "/live/song/get/loop_start": [64.0],
                "/live/song/get/loop_length": [length],
                "/live/song/get/signature_numerator": [4],
                "/live/song/get/signature_denominator": [4],
            },
            tmp_path,
        )
        state.scan_current_set()
        assert state.export_range is not None
        headline, detail = state.export_range.describe()
        assert headline == "Whole song"
        assert detail == "Loop is off in Ableton. Turn on the loop brace around a section to export only that part."


def test_scan_reads_loop_range_in_6_8_signature(tmp_path):
    # 6/8 has 6 * 4 / 8 = 3.0 quarter-note beats per bar.
    # Start 12 beats -> bar 5; length 24 beats (end 36) -> bar 12 (8 bars, 12s at 120 BPM).
    state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/loop": [1],
            "/live/song/get/loop_start": [12.0],
            "/live/song/get/loop_length": [24.0],
            "/live/song/get/signature_numerator": [6],
            "/live/song/get/signature_denominator": [8],
        },
        tmp_path,
    )

    state.scan_current_set()

    assert state.export_range is not None
    assert state.export_range.beats_per_bar == pytest.approx(3.0)
    headline, detail = state.export_range.describe()
    assert headline == "Bars 5 to 12"
    assert detail == "8 bars, 0:12 long. Set by the loop brace in Ableton."


def test_scan_handles_fractional_start_single_bar_and_missing_bpm(tmp_path):
    # 4/4, start at beat 2.0 (bar 1), length 2.0 (ends at beat 4.0 -> bar 1), no BPM.
    state = _make_state(
        {
            "/live/song/get/tempo": None,
            "/live/song/get/loop": [1],
            "/live/song/get/loop_start": [2.0],
            "/live/song/get/loop_length": [2.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
    )

    state.scan_current_set()

    assert state.export_range is not None
    headline, detail = state.export_range.describe()
    assert headline == "Bars 1 to 1"
    assert detail == "1 bar. Set by the loop brace in Ableton."


def test_scan_still_succeeds_when_range_missing_invalid_or_client_fails(tmp_path):
    # Missing OSC reply
    missing_state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/loop": [1],
            "/live/song/get/loop_start": None,
            "/live/song/get/loop_length": [16.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
    )
    project, tracks = missing_state.scan_current_set()
    assert project.song_name == "Test Song"
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert missing_state.export_range is None

    # Denominator 0
    zero_den_state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/loop": [1],
            "/live/song/get/loop_start": [0.0],
            "/live/song/get/loop_length": [16.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [0],
        },
        tmp_path,
    )
    project, tracks = zero_den_state.scan_current_set()
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert zero_den_state.export_range is None

    # Client raising during get_export_range
    failing_state = AppState(
        RaisingRangeClient(),
        project_info_getter=lambda: (tmp_path, "Test Song"),
    )
    project, tracks = failing_state.scan_current_set()
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert failing_state.export_range is None


@pytest.fixture(scope="module")
def qt_app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def test_main_window_displays_range_banner_handles_failure_and_confirms_range(qt_app, monkeypatch, tmp_path):
    class DummyGateway:
        def start_listener(self) -> None:
            pass

        def stop_listener(self) -> None:
            pass

    class DummyPreferencesStore:
        def load(self) -> Preferences:
            return Preferences()

        def save(self, _preferences: Preferences) -> None:
            pass

    monkeypatch.setattr(main_window_module, "PreferencesStore", DummyPreferencesStore)
    monkeypatch.setattr(main_window_module, "OSCGateway", DummyGateway)
    monkeypatch.setattr(main_window_module, "AbletonClient", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(main_window_module.QTimer, "singleShot", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(main_window_module, "is_launch_agent_installed", lambda: False)

    window = main_window_module.MainWindow()
    try:
        state = _make_state(
            {
                "/live/song/get/tempo": [120.0],
                "/live/song/get/loop": [1],
                "/live/song/get/loop_start": [64.0],
                "/live/song/get/loop_length": [128.0],
                "/live/song/get/signature_numerator": [4],
                "/live/song/get/signature_denominator": [4],
            },
            tmp_path,
        )
        project, _tracks = state.scan_current_set()
        window._handle_scan_success(state, project)
        qt_app.processEvents()

        assert window.export_range_banner.objectName() == "exportRangeBanner"
        assert window.export_range_banner.property("rangeMode") == "loop"
        assert window.export_range_caption.text() == "EXPORT RANGE"
        assert window.export_range_headline.text() == "Bars 17 to 48"
        assert window.export_range_detail.text() == "32 bars, 1:04 long. Set by the loop brace in Ableton."
        assert window.export_range_detail.wordWrap() is True

        # confirm_export must include the range headline in the dialog text
        seen_texts: list[str] = []
        scan_called = []
        monkeypatch.setattr(window, "scan_current_set", lambda: scan_called.append(True))

        def fake_exec(self):
            seen_texts.append(f"{self.text()}\n{self.informativeText()}")
            for button in self.buttons():
                if self.buttonRole(button) == QMessageBox.RejectRole:
                    button.click()
                    break
            return 0

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        window.confirm_export()
        assert len(seen_texts) == 1
        assert "Bars 17 to 48" in seen_texts[0]
        assert scan_called == []

        # Scan with None export_range shows Range unknown
        no_range_state = SimpleNamespace(
            detected_tracks=[StemTrack(index=0, name="DRUMS")],
            project=ProjectContext(song_name="Test Song", project_folder=tmp_path, bpm=120),
            build_export_job=state.build_export_job,
        )
        window._handle_scan_success(no_range_state, no_range_state.project)
        assert window.export_range_banner.property("rangeMode") == "unknown"
        assert window.export_range_headline.text() == "Range unknown"
        assert window.export_range_detail.text() == "Could not read the loop from Ableton."

        # Whole song mode
        whole_state = _make_state(
            {
                "/live/song/get/tempo": [120.0],
                "/live/song/get/loop": [0],
                "/live/song/get/loop_start": [0.0],
                "/live/song/get/loop_length": [32.0],
                "/live/song/get/signature_numerator": [4],
                "/live/song/get/signature_denominator": [4],
            },
            tmp_path,
        )
        project, _ = whole_state.scan_current_set()
        window._handle_scan_success(whole_state, project)
        assert window.export_range_banner.property("rangeMode") == "whole"
        assert window.export_range_headline.text() == "Whole song"

        # Scan failure clears/resets banner
        window._handle_scan_failure("Ableton Live is not reachable.")
        assert window.export_range_banner.property("rangeMode") == "unknown"
        assert window.export_range_headline.text() != "Whole song"
    finally:
        window.close()
