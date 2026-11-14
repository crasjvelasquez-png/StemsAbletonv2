from __future__ import annotations

from .models import ExportRange, normalize_track_color
from .osc import OSCGateway


COLOR_FETCH_TIMEOUT = 1.5


class AbletonClient:
    def __init__(self, gateway: OSCGateway) -> None:
        self.gateway = gateway

    def get_track_count(self) -> int:
        result = self.gateway.ask("/live/song/get/num_tracks")
        return int(result[0]) if result else 0

    def get_bpm(self) -> int | float | None:
        result = self.gateway.ask("/live/song/get/tempo")
        if result and len(result) >= 1:
            bpm = float(result[0])
            return int(bpm) if bpm == int(bpm) else round(bpm, 1)
        return None

    def get_track_solo(self, track_index: int) -> bool:
        result = self.gateway.ask("/live/track/get/solo", track_index)
        if result and len(result) >= 2:
            return bool(result[1])
        return False

    def set_track_solo(self, track_index: int, soloed: bool) -> None:
        self.gateway.send("/live/track/set/solo", track_index, int(soloed))

    def get_all_tracks(self, count: int) -> list[dict[str, object]]:
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
        return self.gateway.ask("/live/song/get/tempo")

    def get_signature_numerator(self):
        return self.gateway.ask("/live/song/get/signature_numerator")

    def get_signature_denominator(self):
        return self.gateway.ask("/live/song/get/signature_denominator")

    def get_song_length(self):
        return self.gateway.ask("/live/song/get/song_length")

    def get_arrangement_extent(self, count: int) -> tuple[float, float] | None:
        if count <= 0:
            return None
        min_start: float | None = None
        max_end: float | None = None
        for index in range(count):
            starts_reply = self.gateway.ask(
                "/live/track/get/arrangement_clips/start_time",
                index,
                timeout=0.5,
            )
            if not starts_reply or len(starts_reply) <= 1:
                continue
            lengths_reply = self.gateway.ask(
                "/live/track/get/arrangement_clips/length",
                index,
                timeout=0.5,
            )
            if not lengths_reply or len(lengths_reply) <= 1:
                continue
            for start_raw, length_raw in zip(starts_reply[1:], lengths_reply[1:]):
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
        if min_start is None or max_end is None or max_end <= min_start:
            return None
        return min_start, max_end

    def get_export_range(self) -> ExportRange | None:
        count = self.get_track_count()
        extent = self.get_arrangement_extent(count)
        if extent is None:
            return None
        min_start, max_end = extent
        length_beats = max_end - min_start
        if length_beats <= 0:
            return None
        num_reply = self.get_signature_numerator()
        den_reply = self.get_signature_denominator()
        if not num_reply or not den_reply:
            return None
        try:
            numerator = int(num_reply[0])
            denominator = int(den_reply[0])
        except (TypeError, ValueError):
            return None
        if denominator <= 0 or numerator <= 0:
            return None
        bpm = self.get_bpm()
        return ExportRange(
            start_beats=min_start,
            length_beats=length_beats,
            numerator=numerator,
            denominator=denominator,
            bpm=float(bpm) if bpm is not None else None,
        )
