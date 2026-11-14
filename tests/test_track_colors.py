from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from stems.ableton import AbletonClient
from stems.detection import find_bus_tracks
from stems.models import StemTrack
from stems.state import AppState


class FakeGateway:
    def __init__(
        self,
        names: dict[int, object],
        colors: dict[int, object] | Exception | None = None,
    ) -> None:
        self.names = names
        self.colors = {} if colors is None else colors
        self.calls: list[tuple[str, int, float | None]] = []

    def fetch_all_parallel(
        self,
        address: str,
        count: int,
        timeout: float | None = None,
    ) -> dict[int, object]:
        self.calls.append((address, count, timeout))
        if address == "/live/track/get/name":
            return dict(self.names)
        if address == "/live/track/get/color":
            if isinstance(self.colors, Exception):
                raise self.colors
            return dict(self.colors)
        raise AssertionError(f"Unexpected OSC address: {address}")


def test_stem_track_defaults_color_to_none_and_replace_preserves_color():
    plain = StemTrack(0, "DRUMS")
    assert plain.color is None

    colored = StemTrack(index=1, name="BASS", color=49071)
    updated = replace(colored, selected=False)
    assert updated.color == 49071
    assert updated.selected is False


def test_scan_carries_valid_colors_from_gateway_to_stem_tracks(tmp_path: Path):
    gateway = FakeGateway(
        names={0: "DRUMS", 1: "lead", 2: "BASS"},
        colors={0: 49071, 1: 16725558, 2: 16777215},
    )
    client = AbletonClient(gateway)

    class WiredClient:
        def get_track_count(self) -> int:
            return 3

        def get_bpm(self) -> int:
            return 120

        def get_all_tracks(self, count: int) -> list[dict[str, object]]:
            return client.get_all_tracks(count)

    state = AppState(
        WiredClient(),
        project_info_getter=lambda: (tmp_path, "Song"),
    )
    _, tracks = state.scan_current_set()

    assert tracks == [
        StemTrack(index=0, name="DRUMS", color=49071),
        StemTrack(index=2, name="BASS", color=16777215),
    ]


def test_failure_a_color_handler_missing_empty_reply_falls_back_to_none():
    gateway = FakeGateway(
        names={0: "DRUMS", 1: "BASS"},
        colors={},
    )
    client = AbletonClient(gateway)

    all_tracks = client.get_all_tracks(2)
    assert all_tracks == [
        {"index": 0, "name": "DRUMS", "color": None},
        {"index": 1, "name": "BASS", "color": None},
    ]
    assert find_bus_tracks(all_tracks) == [
        StemTrack(index=0, name="DRUMS", color=None),
        StemTrack(index=1, name="BASS", color=None),
    ]


def test_failure_b_color_fetch_uses_short_dedicated_timeout():
    gateway = FakeGateway(names={0: "DRUMS"}, colors={0: 49071})
    client = AbletonClient(gateway)

    client.get_all_tracks(1)

    name_calls = [call for call in gateway.calls if call[0] == "/live/track/get/name"]
    color_calls = [call for call in gateway.calls if call[0] == "/live/track/get/color"]
    assert len(name_calls) == 1
    assert len(color_calls) == 1
    _, count, color_timeout = color_calls[0]
    assert count == 1
    assert color_timeout is not None
    assert 0 < color_timeout <= 1.5


def test_failure_c_non_int_and_none_color_values_become_none():
    gateway = FakeGateway(
        names={0: "DRUMS", 1: "BASS", 2: "SYNTH", 3: "KEYS", 4: "VOX", 5: "FX"},
        colors={0: None, 1: "49071", 2: 49071.0, 3: True, 4: False, 5: object()},
    )
    client = AbletonClient(gateway)

    all_tracks = client.get_all_tracks(6)
    assert [track["color"] for track in all_tracks] == [None] * 6

    detected = find_bus_tracks(
        [
            {"index": 0, "name": "DRUMS", "color": None},
            {"index": 1, "name": "BASS", "color": "0xff0000"},
            {"index": 2, "name": "SYNTH", "color": 12.5},
            {"index": 3, "name": "KEYS", "color": True},
            {"index": 4, "name": "VOX", "color": False},
        ]
    )
    assert [track.color for track in detected] == [None] * 5


def test_failure_d_index_mismatch_value_error_does_not_break_scan():
    gateway = FakeGateway(
        names={0: "DRUMS", 1: "BASS"},
        colors=ValueError("/live/track/get/color: expected index 0, got 1"),
    )
    client = AbletonClient(gateway)

    all_tracks = client.get_all_tracks(2)
    assert all_tracks == [
        {"index": 0, "name": "DRUMS", "color": None},
        {"index": 1, "name": "BASS", "color": None},
    ]
    assert find_bus_tracks(all_tracks) == [
        StemTrack(index=0, name="DRUMS", color=None),
        StemTrack(index=1, name="BASS", color=None),
    ]


def test_failure_e_partial_color_reply_sets_missing_tracks_to_none():
    gateway = FakeGateway(
        names={0: "DRUMS", 1: "BASS", 2: "SYNTH"},
        colors={0: 49071, 2: 3947580},
    )
    client = AbletonClient(gateway)

    all_tracks = client.get_all_tracks(3)
    assert all_tracks == [
        {"index": 0, "name": "DRUMS", "color": 49071},
        {"index": 1, "name": "BASS", "color": None},
        {"index": 2, "name": "SYNTH", "color": 3947580},
    ]


def test_failure_f_dicts_without_color_key_and_fake_clients_keep_working(tmp_path: Path):
    detected = find_bus_tracks(
        [
            {"index": 0, "name": "DRUMS"},
            {"index": 1, "name": "BASS", "color": 49071},
        ]
    )
    assert detected == [
        StemTrack(index=0, name="DRUMS", color=None),
        StemTrack(index=1, name="BASS", color=49071),
    ]

    class LegacyFakeClient:
        def get_track_count(self) -> int:
            return 2

        def get_bpm(self) -> int:
            return 128

        def get_all_tracks(self, count: int) -> list[dict[str, object]]:
            return [{"index": 0, "name": "DRUMS"}, {"index": 1, "name": "lead"}]

    state = AppState(
        LegacyFakeClient(),
        project_info_getter=lambda: (tmp_path, "LegacySong"),
    )
    _, tracks = state.scan_current_set()
    assert tracks == [StemTrack(index=0, name="DRUMS", color=None)]


def test_failure_g_out_of_range_colors_rejected_and_bounds_accepted():
    gateway = FakeGateway(
        names={0: "BLACK", 1: "WHITE", 2: "NEG", 3: "OVER", 4: "HUGE"},
        colors={0: 0, 1: 0xFFFFFF, 2: -1, 3: 0x1000000, 4: 0xFFFFFFFF},
    )
    client = AbletonClient(gateway)

    all_tracks = client.get_all_tracks(5)
    assert [track["color"] for track in all_tracks] == [0, 0xFFFFFF, None, None, None]

    detected = find_bus_tracks(
        [
            {"index": 0, "name": "BLACK", "color": 0},
            {"index": 1, "name": "WHITE", "color": 0xFFFFFF},
            {"index": 2, "name": "NEG", "color": -5},
            {"index": 3, "name": "OVER", "color": 0x1000000},
        ]
    )
    assert [track.color for track in detected] == [0, 0xFFFFFF, None, None]


def test_failure_h_color_fetch_exception_never_breaks_name_scanning_or_detection(tmp_path: Path):
    for exc in (RuntimeError("osc failure"), OSError("network down"), TimeoutError("timed out")):
        gateway = FakeGateway(
            names={0: "DRUMS", 1: "lead", 2: "BASS"},
            colors=exc,
        )
        client = AbletonClient(gateway)

        class ResilientClient:
            def get_track_count(self) -> int:
                return 3

            def get_bpm(self) -> int:
                return 120

            def get_all_tracks(self, count: int) -> list[dict[str, object]]:
                return client.get_all_tracks(count)

        state = AppState(
            ResilientClient(),
            project_info_getter=lambda: (tmp_path, "Song"),
        )
        _, tracks = state.scan_current_set()
        assert tracks == [
            StemTrack(index=0, name="DRUMS", color=None),
            StemTrack(index=2, name="BASS", color=None),
        ]
