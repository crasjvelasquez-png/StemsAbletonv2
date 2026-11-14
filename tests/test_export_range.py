"""End-to-end tests for Ableton arrangement export range detection and ruler UI display.

Failure modes considered before implementation:
1. Multi-track arrangement extent:
   Ableton's Export dialog defaults (with no time selection) to the span from the start of
   the first arrangement clip to the end of the last arrangement clip across all tracks.
   get_arrangement_extent() must compute min(start) to max(start + length) across all tracks.
2. Loop-brace values present in Live:
   /live/song/get/loop, /live/song/get/loop_start, and /live/song/get/loop_length must be
   ignored so an unrelated loop brace never overrides the arrangement clip extent.
3. All tracks empty or zero track count:
   Tracks with no arrangement clips reply (i,) (len <= 1). When no clips exist on any track
   (or track count is 0), get_export_range() must return None and the UI must fall back to
   "Bars 1 to 200" ("200 bars") with ruler 1..200.
4. Non-responding tracks (e.g. group tracks returning None) or empty replies:
   Tracks where ask() returns None or (i,) must be skipped without aborting, while clips on
   other tracks still determine the overall arrangement extent.
5. Non-4/4 time signatures (e.g. 6/8, 3/4, 7/8):
   AbletonOSC reports clip start_time and length in quarter-note beats, so 6/8 has
   numerator * 4 / denominator = 3.0 beats per bar, not 6.0 or 4.0.
6. Fractional start or end beats:
   start_bar = floor(start_beats / beats_per_bar) + 1 and
   end_bar = ceil((start_beats + length_beats) / beats_per_bar) must include both partial bars.
7. Missing or invalid time signature (reply is None or numerator/denominator <= 0):
   Must defend against ZeroDivisionError / ValueError and return None instead of crashing.
8. Missing BPM (get_bpm() returns None or 0):
   ExportRange must still produce the bar headline and omit " · m:ss" rather than failing or
   dividing by zero.
9. Client raising during get_export_range():
   AppState.scan_current_set() must still succeed and leave export_range as None.
10. Ruler scale exceeding 200 bars:
    Ruler total must be max(200, end_bar) rounded up to a multiple of 8 (e.g. bar 230 -> 232).
11. MainWindow banner label, confirm dialog text, and state fakes:
    Banner label must read "Range Selected", confirm_export() must open ExportConfirmDialog
    with non-verbose title ("Export N stems?") and concise range ("Bars X to Y · N bars"),
    and UI must tolerate fakes lacking `export_range`, default to "Bars 1 to 200" when None,
    and reset stale range on scan failure.
12. ExportConfirmDialog verbosity, long paths, and conflict modes:
    - Range must not be repeated in both the dialog title and body.
    - Destination must show only the target folder name (with full path in tooltip) so long
      external volume paths do not wrap awkwardly across 4 lines.
    - Conflict notice must stay hidden when no conflicts exist, and show concise status or
      explicit action buttons ("Keep both", "Skip", "Replace") when conflicts exist.
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
    def __init__(
        self,
        responses: dict[str, list[object] | None],
        clips: dict[int, list[tuple[float, float]]] | None = None,
        tracks: dict[int, str] | None = None,
    ) -> None:
        self.responses = responses
        self.clips = clips if clips is not None else {}
        self.tracks = tracks if tracks is not None else {0: "DRUMS", 1: "lead", 2: "BASS"}

    def ask(self, address: str, *args, timeout: float = 3.0):  # noqa: ARG002
        if address == "/live/song/get/num_tracks":
            return [len(self.tracks)]
        if address == "/live/track/get/arrangement_clips/start_time":
            track_index = int(args[0])
            if track_index not in self.clips:
                return None
            return (track_index, *[start for start, _ in self.clips[track_index]])
        if address == "/live/track/get/arrangement_clips/length":
            track_index = int(args[0])
            if track_index not in self.clips:
                return None
            return (track_index, *[length for _, length in self.clips[track_index]])
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


def _make_state(
    responses: dict[str, list[object] | None],
    project_dir: Path,
    clips: dict[int, list[tuple[float, float]]] | None = None,
    tracks: dict[int, str] | None = None,
) -> AppState:
    client = AbletonClient(FakeOSCGateway(responses, clips=clips, tracks=tracks))
    return AppState(
        client,
        project_info_getter=lambda: (project_dir, "Test Song"),
    )


def test_scan_reads_arrangement_extent_across_tracks_in_4_4(tmp_path):
    # Track 0: [64..96), [160..192); Track 1: empty; Track 2: [80..144)
    # Overall extent: min(start)=64.0, max(end)=192.0 (length=128.0 beats -> Bars 17 to 48, 1:04)
    state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={
            0: [(64.0, 32.0), (160.0, 32.0)],
            1: [],
            2: [(80.0, 64.0)],
        },
    )

    project, tracks = state.scan_current_set()

    assert project.song_name == "Test Song"
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert state.export_range is not None
    headline, detail = state.export_range.describe()
    assert headline == "Bars 17 to 48"
    assert detail == "32 bars · 1:04"


def test_scan_ignores_loop_brace_values(tmp_path):
    # Loop brace is bars 1..4 (0..16 beats), but arrangement clips are bars 17..48 (64..192 beats).
    state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/loop": [1],
            "/live/song/get/loop_start": [0.0],
            "/live/song/get/loop_length": [16.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={
            0: [(64.0, 128.0)],
            1: [],
            2: [],
        },
    )

    state.scan_current_set()

    assert state.export_range is not None
    assert state.export_range.describe() == ("Bars 17 to 48", "32 bars · 1:04")


def test_scan_reads_arrangement_extent_in_6_8_signature(tmp_path):
    # 6/8 has 6 * 4 / 8 = 3.0 quarter-note beats per bar.
    # Start 12 beats -> bar 5; end 36 beats -> bar 12 (8 bars, length 24 beats = 12s at 120 BPM).
    state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/signature_numerator": [6],
            "/live/song/get/signature_denominator": [8],
        },
        tmp_path,
        clips={
            0: [(12.0, 12.0)],
            1: [],
            2: [(24.0, 12.0)],
        },
    )

    state.scan_current_set()

    assert state.export_range is not None
    assert state.export_range.beats_per_bar == pytest.approx(3.0)
    headline, detail = state.export_range.describe()
    assert headline == "Bars 5 to 12"
    assert detail == "8 bars · 0:12"


def test_scan_handles_fractional_bounds_single_bar_and_missing_bpm(tmp_path):
    # 4/4, clip starts at beat 2.0 (bar 1), length 2.0 (ends at beat 4.0 -> bar 1), no BPM.
    single_bar_state = _make_state(
        {
            "/live/song/get/tempo": None,
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={0: [(2.0, 2.0)], 1: [], 2: []},
    )

    single_bar_state.scan_current_set()

    assert single_bar_state.export_range is not None
    assert single_bar_state.export_range.describe() == ("Bars 1 to 1", "1 bar")

    # Fractional start (1.5 -> bar 1) and fractional end (6.5 -> bar 2) across tracks.
    fractional_state = _make_state(
        {
            "/live/song/get/tempo": None,
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={0: [(1.5, 1.5)], 1: [], 2: [(3.0, 3.5)]},
    )

    fractional_state.scan_current_set()

    assert fractional_state.export_range is not None
    assert fractional_state.export_range.describe() == ("Bars 1 to 2", "2 bars")


def test_scan_returns_none_when_all_tracks_empty(tmp_path):
    empty_state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={0: [], 1: [], 2: []},
    )

    project, tracks = empty_state.scan_current_set()

    assert project.song_name == "Test Song"
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert empty_state.export_range is None

    no_tracks_state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={},
        tracks={},
    )
    no_tracks_state.scan_current_set()
    assert no_tracks_state.export_range is None


def test_scan_skips_tracks_with_no_reply(tmp_path):
    # Track 1 is absent from clips dict so ask() returns None (simulating a group track).
    state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={
            0: [(64.0, 32.0)],
            2: [(96.0, 96.0)],
        },
    )

    project, tracks = state.scan_current_set()

    assert project.song_name == "Test Song"
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert state.export_range is not None
    assert state.export_range.describe() == ("Bars 17 to 48", "32 bars · 1:04")


def test_scan_still_succeeds_when_signature_missing_invalid_or_client_fails(tmp_path):
    # Missing time signature OSC reply
    missing_sig_state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/signature_numerator": None,
            "/live/song/get/signature_denominator": [4],
        },
        tmp_path,
        clips={0: [(0.0, 16.0)], 1: [], 2: []},
    )
    project, tracks = missing_sig_state.scan_current_set()
    assert project.song_name == "Test Song"
    assert [t.name for t in tracks] == ["DRUMS", "BASS"]
    assert missing_sig_state.export_range is None

    # Denominator 0
    zero_den_state = _make_state(
        {
            "/live/song/get/tempo": [120.0],
            "/live/song/get/signature_numerator": [4],
            "/live/song/get/signature_denominator": [0],
        },
        tmp_path,
        clips={0: [(0.0, 16.0)], 1: [], 2: []},
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
                "/live/song/get/loop_start": [0.0],
                "/live/song/get/loop_length": [16.0],
                "/live/song/get/signature_numerator": [4],
                "/live/song/get/signature_denominator": [4],
            },
            tmp_path,
            clips={
                0: [(64.0, 64.0)],
                1: [],
                2: [(128.0, 64.0)],
            },
        )
        project, _tracks = state.scan_current_set()
        window._handle_scan_success(state, project)
        window.show()
        qt_app.processEvents()

        assert window.export_range_banner.objectName() == "exportRangeBanner"
        assert window.export_range_banner.property("rangeMode") is None
        assert window.export_range_label.text() == "Range Selected"
        assert window.export_range_headline.objectName() == "exportRangeHeadline"
        assert window.export_range_headline.text() == "Bars 17 to 48"
        assert window.export_range_meta.text() == "32 bars · 1:04"
        assert window.export_range_ruler.start_bar == 17
        assert window.export_range_ruler.end_bar == 48
        assert window.export_range_ruler.total_bars == 200

        # confirm_export opens ExportConfirmDialog with non-verbose title, range, and folder name
        seen_dialogs: list[object] = []
        scan_called = []
        monkeypatch.setattr(window, "scan_current_set", lambda: scan_called.append(True))

        def fake_exec(self):
            seen_dialogs.append(self)
            self.cancel_button.click()
            return self.result()

        monkeypatch.setattr(main_window_module.ExportConfirmDialog, "exec", fake_exec)
        window.confirm_export()
        assert len(seen_dialogs) == 1
        dialog = seen_dialogs[0]
        assert dialog.title_label.text() == "Export 2 stems?"
        assert "Bars 17 to 48" not in dialog.title_label.text()
        assert dialog.range_value.text() == "Bars 17 to 48 · 32 bars · 1:04"
        assert window.current_job.stems_dir.name.replace(" ", "&nbsp;") in dialog.folder_value.text()
        assert "\U0001F4C1" in dialog.folder_value.text()
        assert "/" not in dialog.folder_value.text().replace("</span>", "").replace("<span", "")
        assert dialog.folder_value.toolTip() == str(window.current_job.stems_dir)
        assert dialog.conflict_label.isHidden() is True
        assert scan_called == []

        # All tracks empty -> export_range is None -> falls back to default 1..200
        empty_state = _make_state(
            {
                "/live/song/get/tempo": [120.0],
                "/live/song/get/signature_numerator": [4],
                "/live/song/get/signature_denominator": [4],
            },
            tmp_path,
            clips={0: [], 1: [], 2: []},
        )
        project, _ = empty_state.scan_current_set()
        window._handle_scan_success(empty_state, project)
        assert window.export_range_headline.text() == "Bars 1 to 200"
        assert window.export_range_meta.text() == "200 bars"
        assert window.export_range_ruler.start_bar == 1
        assert window.export_range_ruler.end_bar == 200
        assert window.export_range_ruler.total_bars == 200

        # Arrangement ending at bar 230 expands ruler total to 232 (multiple of 8)
        long_state = _make_state(
            {
                "/live/song/get/tempo": [120.0],
                "/live/song/get/signature_numerator": [4],
                "/live/song/get/signature_denominator": [4],
            },
            tmp_path,
            clips={0: [(0.0, 920.0)], 1: [], 2: []},
        )
        project, _ = long_state.scan_current_set()
        window._handle_scan_success(long_state, project)
        assert window.export_range_headline.text() == "Bars 1 to 230"
        assert window.export_range_ruler.start_bar == 1
        assert window.export_range_ruler.end_bar == 230
        assert window.export_range_ruler.total_bars == 232

        # Scan with None export_range shows default Bars 1 to 200
        no_range_state = SimpleNamespace(
            detected_tracks=[StemTrack(index=0, name="DRUMS")],
            project=ProjectContext(song_name="Test Song", project_folder=tmp_path, bpm=120),
            build_export_job=state.build_export_job,
        )
        window._handle_scan_success(no_range_state, no_range_state.project)
        assert window.export_range_headline.text() == "Bars 1 to 200"
        assert window.export_range_meta.text() == "200 bars"
        assert window.export_range_ruler.start_bar == 1
        assert window.export_range_ruler.end_bar == 200
        assert window.export_range_ruler.total_bars == 200

        seen_dialogs.clear()
        window.state = no_range_state
        window.confirm_export()
        assert len(seen_dialogs) == 1
        assert seen_dialogs[0].title_label.text() == "Export 1 stem?"
        assert seen_dialogs[0].range_value.text() == "Bars 1 to 200 · 200 bars"

        # Scan failure resets banner to default Bars 1 to 200
        window._handle_scan_success(long_state, long_state.project)
        window._handle_scan_failure("Ableton Live is not reachable.")
        assert window.export_range_headline.text() == "Bars 1 to 200"
        assert window.export_range_meta.text() == "200 bars"
        assert window.export_range_ruler.start_bar == 1
        assert window.export_range_ruler.end_bar == 200
        assert window.export_range_ruler.total_bars == 200
    finally:
        window.close()


def test_export_confirm_dialog_conflict_modes_and_artifact_e2e(tmp_path, monkeypatch):
    """Verify ExportConfirmDialog aesthetic, simplified copy, and conflict resolution modes E2E."""
    import json

    qt_app = QApplication.instance() or QApplication([])

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
                "/live/song/get/tempo": [93.0],
                "/live/song/get/signature_numerator": [4],
                "/live/song/get/signature_denominator": [4],
            },
            tmp_path,
            clips={
                0: [(28.0, 256.0)],
                1: [(28.0, 256.0)],
            },
            tracks={0: "DRUMS", 1: "BASS"},
        )
        project, _ = state.scan_current_set()
        window._handle_scan_success(state, project)
        window.update_destination_preview()
        qt_app.processEvents()

        scans: list[bool] = []
        monkeypatch.setattr(window, "scan_current_set", lambda: scans.append(True))

        report: dict[str, object] = {}

        # 1. Clean export (no conflicts) -> simple card with Range + Folder, no conflict notice
        captured: list[object] = []

        def accept_clean(self):
            captured.append(
                {
                    "title": self.title_label.text(),
                    "range": self.range_value.text(),
                    "folder": self.folder_value.text(),
                    "folder_tooltip_has_parent": str(tmp_path) in self.folder_value.toolTip(),
                    "conflict_hidden": self.conflict_label.isHidden(),
                    "buttons": [b.text() for b in self.action_buttons],
                    "card_name": self.summary_card.objectName(),
                    "footer_name": self.footer.objectName(),
                }
            )
            self.default_action_button.click()
            return self.result()

        monkeypatch.setattr(main_window_module.ExportConfirmDialog, "exec", accept_clean)
        window.confirm_export()
        assert len(captured) == 1
        assert captured[0]["title"] == "Export 2 stems?"
        assert captured[0]["range"] == "Bars 8 to 71 · 64 bars · 2:45"
        assert window.current_job.stems_dir.name.replace(" ", "&nbsp;") in captured[0]["folder"]
        assert captured[0]["folder_tooltip_has_parent"] is True
        assert captured[0]["conflict_hidden"] is True
        assert captured[0]["buttons"] == ["Cancel", "Export"]
        assert window._chosen_replace_mode == "replace"
        assert window._pending_export is True
        assert len(scans) == 1
        report["clean_export"] = captured[0]

        # 2. Conflicts exist with mode == "ask" -> shows conflict note + Keep both / Skip / Replace
        window._pending_export = False
        stems_dir = window.current_job.stems_dir
        stems_dir.mkdir(parents=True, exist_ok=True)
        from stems.export import planned_stem_paths

        existing_stem = planned_stem_paths(window.current_job)[0][1].with_suffix(".wav")
        existing_stem.write_bytes(b"RIFF")

        window.preferences.replace_mode = "ask"
        captured_ask: list[object] = []

        def choose_keep_both(self):
            captured_ask.append(
                {
                    "title": self.title_label.text(),
                    "conflict": self.conflict_label.text(),
                    "conflict_hidden": self.conflict_label.isHidden(),
                    "buttons": [b.text() for b in self.action_buttons],
                    "default_button": self.default_action_button.text(),
                }
            )
            for btn in self.action_buttons:
                if btn.text() == "Keep both":
                    btn.click()
                    break
            return self.result()

        monkeypatch.setattr(main_window_module.ExportConfirmDialog, "exec", choose_keep_both)
        window.confirm_export()
        assert len(captured_ask) == 1
        assert captured_ask[0]["conflict_hidden"] is False
        assert captured_ask[0]["conflict"] == "1 of 2 already exist"
        assert captured_ask[0]["buttons"] == ["Cancel", "Keep both", "Skip", "Replace"]
        assert captured_ask[0]["default_button"] == "Replace"
        assert window._chosen_replace_mode == "keep_both"
        report["conflict_ask_mode"] = captured_ask[0]

        # 3. Conflicts exist with preset mode (e.g. "keep") -> concise note + Cancel / Export
        window._pending_export = False
        window.preferences.replace_mode = "keep"
        captured_preset: list[object] = []

        def accept_preset(self):
            captured_preset.append(
                {
                    "conflict": self.conflict_label.text(),
                    "buttons": [b.text() for b in self.action_buttons],
                }
            )
            self.default_action_button.click()
            return self.result()

        monkeypatch.setattr(main_window_module.ExportConfirmDialog, "exec", accept_preset)
        window.confirm_export()
        assert captured_preset[0]["conflict"] == "1 of 2 already exist · will be skipped"
        assert captured_preset[0]["buttons"] == ["Cancel", "Export"]
        assert window._chosen_replace_mode == "keep"
        report["conflict_preset_keep"] = captured_preset[0]

        artifact_path = Path(__file__).parent / "artifacts" / "export_confirm_dialog.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(report, indent=2) + "\n")
        assert artifact_path.exists()
    finally:
        window.close()

