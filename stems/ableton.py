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

    def get_export_range(self) -> ExportRange | None:
        loop_reply = self.gateway.ask("/live/song/get/loop")
        start_reply = self.gateway.ask("/live/song/get/loop_start")
        length_reply = self.gateway.ask("/live/song/get/loop_length")
        num_reply = self.get_signature_numerator()
        den_reply = self.get_signature_denominator()
        if not loop_reply or not start_reply or not length_reply or not num_reply or not den_reply:
            return None
        try:
            loop_val = loop_reply[0]
            loop_enabled = loop_val if isinstance(loop_val, bool) else bool(int(loop_val))
            start_beats = float(start_reply[0])
            length_beats = float(length_reply[0])
            numerator = int(num_reply[0])
            denominator = int(den_reply[0])
        except (TypeError, ValueError):
            return None
        if denominator <= 0 or numerator <= 0:
            return None
        bpm = self.get_bpm()
        return ExportRange(
            loop_enabled=loop_enabled,
            start_beats=start_beats,
            length_beats=length_beats,
            numerator=numerator,
            denominator=denominator,
            bpm=float(bpm) if bpm is not None else None,
        )
