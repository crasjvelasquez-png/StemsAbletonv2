from __future__ import annotations

import threading
import time

from .errors import AbletonConnectionError
from .errors import DependencyError


ABLETON_OSC_HOST = "127.0.0.1"
ABLETON_OSC_PORT = 11000
LISTEN_PORT = 11001


class OSCGateway:
    def __init__(
        self,
        host: str = ABLETON_OSC_HOST,
        port: int = ABLETON_OSC_PORT,
        listen_port: int = LISTEN_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self.listen_port = listen_port
        self.osc_responses: dict[object, tuple[object, ...]] = {}
        self.response_events: dict[object, threading.Event] = {}
        self.osc_lock = threading.Lock()
        self._server = None
        self._server_thread: threading.Thread | None = None

        try:
            from pythonosc import dispatcher, osc_server, udp_client
        except ImportError as exc:
            raise DependencyError("python-osc not installed. Run: pip install python-osc") from exc

        self._dispatcher = dispatcher
        self._osc_server = osc_server
        self._client = udp_client.SimpleUDPClient(self.host, self.port)

    def osc_handler(self, address: str, *args: object) -> None:
        with self.osc_lock:
            self.osc_responses[address] = args
            if address in self.response_events:
                self.response_events[address].set()
            if len(args) >= 2:
                try:
                    key = (address, int(args[0]))
                except (ValueError, TypeError):
                    return
                self.osc_responses[key] = args
                if key in self.response_events:
                    self.response_events[key].set()

    def make_event(self, key: object) -> threading.Event:
        with self.osc_lock:
            event = threading.Event()
            self.response_events[key] = event
            self.osc_responses.pop(key, None)
        return event

    def start_listener(self):
        if self._server is not None:
            return self._server
        dispatcher = self._dispatcher.Dispatcher()
        dispatcher.set_default_handler(self.osc_handler)
        try:
            server = self._osc_server.ThreadingOSCUDPServer((self.host, self.listen_port), dispatcher)
        except OSError as exc:
            raise AbletonConnectionError(
                f"Could not bind AbletonOSC listener on {self.host}:{self.listen_port}. "
                "Another Stems instance may already be running."
            ) from exc
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._server = server
        self._server_thread = thread
        return server

    def stop_listener(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._server_thread is not None:
            self._server_thread.join(timeout=1)
        self._server = None
        self._server_thread = None

    def send(self, address: str, *args: object) -> None:
        self._client.send_message(address, list(args) if args else [])

    def ask(self, address: str, *args: object, timeout: float = 3.0):
        event = self.make_event(address)
        self.send(address, *args)
        event.wait(timeout=timeout)
        with self.osc_lock:
            return self.osc_responses.get(address)

    def fetch_all_parallel(self, address: str, count: int, timeout: float = 6.0) -> dict[int, object]:
        events = {index: self.make_event((address, index)) for index in range(count)}
        for index in range(count):
            self.send(address, index)
            time.sleep(0.002)
        deadline = time.time() + timeout
        for index in range(count):
            remaining = max(0.0, deadline - time.time())
            events[index].wait(timeout=remaining)

        results: dict[int, object] = {}
        with self.osc_lock:
            for index in range(count):
                value = self.osc_responses.get((address, index))
                if value and len(value) >= 2:
                    if int(value[0]) != index:
                        raise ValueError(f"{address}: expected index {index}, got {value[0]}")
                    results[index] = value[1]
        return results
