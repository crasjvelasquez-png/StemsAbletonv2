from __future__ import annotations

from collections.abc import Iterable

from .models import ExportRange, normalize_track_color
from .osc import OSCGateway


COLOR_FETCH_TIMEOUT = 1.5
TRACK_DATA_TIMEOUT = 1.0
TRACK_DATA_CHUNK_SIZE = 64

_CLIP_START_ADDR = "/live/track/get/arrangement_clips/start_time"
_CLIP_LENGTH_ADDR = "/live/track/get/arrangement_clips/length"
_NUM_TRACKS_ADDR = "/live/song/get/num_tracks"
_SIG_NUM_ADDR = "/live/song/get/signature_numerator"
_SIG_DEN_ADDR = "/live/song/get/signature_denominator"
_TEMPO_ADDR = "/live/song/get/tempo"


def _parse_bpm(result: object) -> int | float | None:
    """Format a tempo OSC reply matching AbletonClient.get_bpm()."""
    if result and len(result) >= 1:
        bpm = float(result[0])
        return int(bpm) if bpm == int(bpm) else round(bpm, 1)
    return None


def _update_extent(
    min_start: float | None,
    max_end: float | None,
    starts: Iterable[object],
    lengths: Iterable[object],
) -> tuple[float | None, float | None]:
    """Fold valid (start, length) clip pairs into running arrangement bounds."""
    for start_raw, length_raw in zip(starts, lengths):
        try:
            start = float(start_raw)
            length = float(length_raw)
        except (TypeError, ValueError):
            continue
        if length <= 0:
            continue
        end = start + length
        if min_start is None or start < min_start:
            min_start = start
        if max_end is None or end > max_end:
            max_end = end
    return min_start, max_end


class AbletonClient:
    def __init__(self, gateway: OSCGateway) -> None:
        self.gateway = gateway
        self._track_data_supported = True

    def get_track_count(self) -> int:
        result = self.gateway.ask(_NUM_TRACKS_ADDR)
        return int(result[0]) if result else 0

    def get_bpm(self) -> int | float | None:
        return _parse_bpm(self.gateway.ask(_TEMPO_ADDR))

    def get_track_solo(self, track_index: int) -> bool:
        result = self.gateway.ask("/live/track/get/solo", track_index)
        if result and len(result) >= 2:
            return bool(result[1])
        return False

    def set_track_solo(self, track_index: int, soloed: bool) -> None:
        self.gateway.send("/live/track/set/solo", track_index, int(soloed))

    def _try_get_tracks_batched(self, count: int) -> list[dict[str, object]] | None:
        """Fetch track names and colors via /live/song/get/track_data, or None to fall back."""
        if not getattr(self, "_track_data_supported", True) or not hasattr(self.gateway, "ask"):
            return None
        tracks: list[dict[str, object]] = []
        try:
            for start in range(0, count, TRACK_DATA_CHUNK_SIZE):
                end = min(start + TRACK_DATA_CHUNK_SIZE, count)
                reply = self.gateway.ask(
                    "/live/song/get/track_data",
                    start,
                    end,
                    "track.name",
                    "track.color",
                    timeout=TRACK_DATA_TIMEOUT,
                )
                if reply is None:
                    # Cache lack of support so later scans avoid waiting for TRACK_DATA_TIMEOUT.
                    self._track_data_supported = False
                    return None
                if not isinstance(reply, (list, tuple)) or len(reply) != 2 * (end - start):
                    return None
                for offset, index in enumerate(range(start, end)):
                    tracks.append(
                        {
                            "index": index,
                            "name": str(reply[2 * offset]),
                            "color": normalize_track_color(reply[2 * offset + 1]),
                        }
                    )
        except Exception:
            return None
        return tracks

    def get_all_tracks(self, count: int) -> list[dict[str, object]]:
        batched = self._try_get_tracks_batched(count)
        if batched is not None:
            return batched
        names = self.gateway.fetch_all_parallel("/live/track/get/name", count)
        try:
            colors = self.gateway.fetch_all_parallel(
                "/live/track/get/color",
                count,
                timeout=COLOR_FETCH_TIMEOUT,
            )
        except Exception:
            colors = {}
        if not isinstance(colors, dict):
            colors = {}
        return [
            {
                "index": index,
                "name": str(names.get(index, "")),
                "color": normalize_track_color(colors.get(index)),
            }
            for index in range(count)
        ]

    def get_song_tempo(self):
        return self.gateway.ask(_TEMPO_ADDR)

    def get_signature_numerator(self):
        return self.gateway.ask(_SIG_NUM_ADDR)

    def get_signature_denominator(self):
        return self.gateway.ask(_SIG_DEN_ADDR)

    def get_song_length(self):
        return self.gateway.ask("/live/song/get/song_length")

    def get_arrangement_extent(self, count: int) -> tuple[float, float] | None:
        if count <= 0:
            return None
        min_start: float | None = None
        max_end: float | None = None
        if hasattr(self.gateway, "fetch_many_parallel"):
            replies = self.gateway.fetch_many_parallel(
                [_CLIP_START_ADDR, _CLIP_LENGTH_ADDR],
                count,
                timeout=2.0,
            )
            starts_by_index = replies.get(_CLIP_START_ADDR, {})
            lengths_by_index = replies.get(_CLIP_LENGTH_ADDR, {})
            for index in range(count):
                starts = starts_by_index.get(index)
                lengths = lengths_by_index.get(index)
                if not starts or not lengths:
                    continue
                min_start, max_end = _update_extent(min_start, max_end, starts, lengths)
        else:
            for index in range(count):
                starts_reply = self.gateway.ask(_CLIP_START_ADDR, index, timeout=0.5)
                if not starts_reply or len(starts_reply) <= 1:
                    continue
                lengths_reply = self.gateway.ask(_CLIP_LENGTH_ADDR, index, timeout=0.5)
                if not lengths_reply or len(lengths_reply) <= 1:
                    continue
                min_start, max_end = _update_extent(
                    min_start,
                    max_end,
                    starts_reply[1:],
                    lengths_reply[1:],
                )
        if min_start is None or max_end is None or max_end <= min_start:
            return None
        return min_start, max_end

    def get_export_range(self, count: int | None = None) -> ExportRange | None:
        if count is not None and count <= 0:
            return None
        use_ask_many = hasattr(self.gateway, "ask_many")
        if use_ask_many:
            requests: list[tuple[str, tuple]] = [
                (_SIG_NUM_ADDR, ()),
                (_SIG_DEN_ADDR, ()),
                (_TEMPO_ADDR, ()),
            ]
            if count is None:
                requests.insert(0, (_NUM_TRACKS_ADDR, ()))
            replies = self.gateway.ask_many(requests)
            if count is None:
                num_tracks_reply = replies.get(_NUM_TRACKS_ADDR)
                count = int(num_tracks_reply[0]) if num_tracks_reply else 0
            extent = self.get_arrangement_extent(count)
            if extent is None:
                return None
            num_reply = replies.get(_SIG_NUM_ADDR)
            den_reply = replies.get(_SIG_DEN_ADDR)
            bpm_reply = replies.get(_TEMPO_ADDR)
        else:
            if count is None:
                count = self.get_track_count()
            extent = self.get_arrangement_extent(count)
            if extent is None:
                return None
            num_reply = self.get_signature_numerator()
            den_reply = self.get_signature_denominator()
            bpm_reply = None

        min_start, max_end = extent
        length_beats = max_end - min_start
        if length_beats <= 0:
            return None
        if not num_reply or not den_reply:
            return None
        try:
            numerator = int(num_reply[0])
            denominator = int(den_reply[0])
        except (TypeError, ValueError):
            return None
        if denominator <= 0 or numerator <= 0:
            return None
        bpm = _parse_bpm(bpm_reply) if use_ask_many else self.get_bpm()
        return ExportRange(
            start_beats=min_start,
            length_beats=length_beats,
            numerator=numerator,
            denominator=denominator,
            bpm=float(bpm) if bpm is not None else None,
        )
