"""A fake AbletonOSC server for end-to-end scan tests.

It mirrors the real AbletonOSC remote script's timing model: incoming UDP
messages are only drained once per Live "tick" (100 ms by default), and every
reply is sent back over real UDP. Run standalone for a timing report:

    python3 -m tests.fake_ableton_osc
"""
from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field

from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder


@dataclass
class FakeTrack:
    name: str
    color: int = 0
    clips: list[tuple[float, float]] = field(default_factory=list)  # (start, length)


class FakeAbletonOSC:
    def __init__(
        self,
        tracks: list[FakeTrack],
        *,
        port: int,
        reply_port: int,
        tick: float = 0.1,
        tempo: float = 120.0,
        signature: tuple[int, int] = (4, 4),
        supports_track_data: bool = True,
    ) -> None:
        self.tracks = tracks
        self.reply_port = reply_port
        self.tick = tick
        self.tempo = tempo
        self.signature = signature
        self.supports_track_data = supports_track_data
        self.received: list[str] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", port))
        self._sock.setblocking(False)
        self._out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._stop.set()
        self._thread.join(timeout=1)
        self._sock.close()
        self._out.close()

    def _reply(self, address: str, values: tuple) -> None:
        builder = OscMessageBuilder(address=address)
        for value in values:
            builder.add_arg(value)
        self._out.sendto(builder.build().dgram, ("127.0.0.1", self.reply_port))

    def _loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(self.tick)
            while True:
                try:
                    data, _addr = self._sock.recvfrom(65536)
                except BlockingIOError:
                    break
                except OSError:
                    return
                message = OscMessage(data)
                self.received.append(message.address)
                result = self._handle(message.address, list(message.params))
                if result is not None:
                    self._reply(message.address, result)

    def _handle(self, address: str, params: list):
        song = {
            "/live/song/get/num_tracks": (len(self.tracks),),
            "/live/song/get/tempo": (self.tempo,),
            "/live/song/get/signature_numerator": (self.signature[0],),
            "/live/song/get/signature_denominator": (self.signature[1],),
        }
        if address in song:
            return song[address]
        if address == "/live/song/get/track_data":
            if not self.supports_track_data:
                return None
            start, end, *props = params
            values: list = []
            for track in self.tracks[int(start):int(end)]:
                for prop in props:
                    values.append(getattr(track, prop.split(".", 1)[1]))
            return tuple(values)
        if address.startswith("/live/track/get/"):
            index = int(params[0])
            track = self.tracks[index]
            prop = address.removeprefix("/live/track/get/")
            if prop == "name":
                return (index, track.name)
            if prop == "color":
                return (index, track.color)
            if prop == "arrangement_clips/start_time":
                return (index, *[float(start) for start, _ in track.clips])
            if prop == "arrangement_clips/length":
                return (index, *[float(length) for _, length in track.clips])
            if prop == "solo":
                return (index, 0)
        return None


def demo_tracks(count: int = 40) -> list[FakeTrack]:
    """A realistic set: every 5th track is an ALL-CAPS bus, the rest are sources."""
    tracks: list[FakeTrack] = []
    for index in range(count):
        if index % 5 == 0:
            name = f"BUS {index // 5}"
        else:
            name = f"source {index}"
        clips = [] if index % 3 == 0 else [(16.0 + index, 64.0), (128.0, 32.0 + index)]
        tracks.append(FakeTrack(name=name, color=1000 + index, clips=clips))
    return tracks


def _report() -> None:
    from pathlib import Path

    from stems.ableton import AbletonClient
    from stems.osc import OSCGateway
    from stems.state import AppState

    tracks = demo_tracks(40)
    with FakeAbletonOSC(tracks, port=11900, reply_port=11901):
        gateway = OSCGateway(port=11900, listen_port=11901)
        gateway.start_listener()
        try:
            state = AppState(AbletonClient(gateway), project_info_getter=lambda: (Path("/tmp"), "Demo"))
            started = time.monotonic()
            _project, stems = state.scan_current_set()
            elapsed = time.monotonic() - started
        finally:
            gateway.stop_listener()
    print(f"tracks={len(tracks)} stems={[s.name for s in stems]}")
    print(f"export_range={state.export_range}")
    print(f"scan_seconds={elapsed:.2f}")


if __name__ == "__main__":
    _report()
