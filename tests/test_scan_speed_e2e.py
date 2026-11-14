"""End-to-end scan test over real UDP against a fake AbletonOSC (100 ms ticks).

Writes tests/artifacts/scan_speed.json so timings can be compared run to run.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from stems.ableton import AbletonClient
from stems.osc import OSCGateway
from stems.state import AppState

from .fake_ableton_osc import FakeAbletonOSC, demo_tracks

ARTIFACT = Path(__file__).parent / "artifacts" / "scan_speed.json"
TRACK_COUNT = 40
# Real AbletonOSC answers once per 100 ms tick. A scan that batches its
# questions needs only a handful of ticks; one question per track needs ~100.
MAX_SCAN_SECONDS = 1.0


def _scan(port: int, supports_track_data: bool, project_delay: float = 0.0):
    tracks = demo_tracks(TRACK_COUNT)

    def project_info():
        time.sleep(project_delay)
        return Path("/tmp"), "Demo"

    with FakeAbletonOSC(tracks, port=port, reply_port=port + 1, supports_track_data=supports_track_data) as fake:
        gateway = OSCGateway(port=port, listen_port=port + 1)
        gateway.start_listener()
        try:
            state = AppState(AbletonClient(gateway), project_info_getter=project_info)
            started = time.monotonic()
            project, stems = state.scan_current_set()
            elapsed = time.monotonic() - started
        finally:
            gateway.stop_listener()
    return tracks, state, project, stems, elapsed, list(fake.received)


def _record(name: str, elapsed: float, messages: int) -> None:
    ARTIFACT.parent.mkdir(exist_ok=True)
    data = json.loads(ARTIFACT.read_text()) if ARTIFACT.exists() else {}
    data[name] = {"tracks": TRACK_COUNT, "scan_seconds": round(elapsed, 3), "osc_messages": messages}
    ARTIFACT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _assert_correct(tracks, state, project, stems):
    expected = [(i, t.name, t.color) for i, t in enumerate(tracks) if t.name.isupper()]
    assert [(s.index, s.name, s.color) for s in stems] == expected
    assert project.song_name == "Demo"
    assert project.bpm == 120
    assert state.export_range is not None
    assert state.export_range.start_beats == 17.0
    assert state.export_range.length_beats == 181.0
    assert (state.export_range.numerator, state.export_range.denominator) == (4, 4)


@pytest.mark.parametrize("supports_track_data", [True, False], ids=["batched", "fallback"])
def test_scan_is_correct_and_fast(supports_track_data):
    port = 11910 if supports_track_data else 11920
    tracks, state, project, stems, elapsed, received = _scan(port, supports_track_data)
    _record("batched" if supports_track_data else "fallback", elapsed, len(received))
    _assert_correct(tracks, state, project, stems)
    limit = MAX_SCAN_SECONDS if supports_track_data else MAX_SCAN_SECONDS * 2.5
    assert elapsed < limit, f"scan took {elapsed:.2f}s for {TRACK_COUNT} tracks"


def test_project_lookup_overlaps_ableton_queries():
    # A 0.6 s project lookup should hide behind the Ableton queries, not add to them.
    tracks, state, project, stems, elapsed, received = _scan(11930, True, project_delay=0.6)
    _record("slow_project_lookup", elapsed, len(received))
    _assert_correct(tracks, state, project, stems)
    assert elapsed < MAX_SCAN_SECONDS


def test_scan_reports_tracks_before_project_lookup_finishes():
    tracks = demo_tracks(10)
    seen: list[tuple[float, list[str]]] = []
    with FakeAbletonOSC(tracks, port=11940, reply_port=11941):
        gateway = OSCGateway(port=11940, listen_port=11941)
        gateway.start_listener()
        try:
            def project_info():
                time.sleep(1.0)
                return Path("/tmp"), "Demo"

            state = AppState(AbletonClient(gateway), project_info_getter=project_info)
            started = time.monotonic()
            state.scan_current_set(
                on_tracks=lambda stems: seen.append((time.monotonic() - started, [s.name for s in stems]))
            )
        finally:
            gateway.stop_listener()
    assert len(seen) == 1
    at, names = seen[0]
    assert names == ["BUS 0", "BUS 1"]
    assert at < 0.9, f"tracks reported only after {at:.2f}s"
