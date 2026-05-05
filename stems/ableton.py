from __future__ import annotations

from .osc import OSCGateway


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
        return [{"index": index, "name": str(names.get(index, ""))} for index in range(count)]

    def get_song_tempo(self):
        return self.gateway.ask("/live/song/get/tempo")

    def get_signature_numerator(self):
        return self.gateway.ask("/live/song/get/signature_numerator")

    def get_signature_denominator(self):
        return self.gateway.ask("/live/song/get/signature_denominator")

    def get_song_length(self):
        return self.gateway.ask("/live/song/get/song_length")
