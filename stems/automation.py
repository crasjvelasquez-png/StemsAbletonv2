from __future__ import annotations

import subprocess
import time


def osascript(script: str, timeout: int = 5, runner=subprocess.run) -> str:
    result = runner(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        error = result.stderr.strip()
        return f"ERROR: osascript failed: {error}" if error else "ERROR: osascript failed"
    return result.stdout.strip()


def find_ableton_app_path(runner=subprocess.run) -> str | None:
    queries = [
        'first process whose name starts with "Ableton"',
        'first process whose name is "Live"',
    ]
    for query in queries:
        try:
            result = runner(
                [
                    "osascript",
                    "-e",
                    f'tell application "System Events" to POSIX path of (application file of ({query}))',
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            continue
        path = result.stdout.strip()
        if path:
            return path
    return None


def live_window_snapshot(script_runner=osascript) -> str:
    raw = script_runner(
        '''
tell application "System Events"
    tell process "Live"
        set out to ""
        try
            repeat with w in every window
                set out to out & "WIN:[" & name of w & "] sheets=" & (count of sheets of w) & "\n"
                repeat with s in every sheet of w
                    set out to out & "  SHEET:[" & name of s & "]\n"
                    try
                        repeat with tf in every text field of s
                            set out to out & "    FIELD:[" & value of tf & "]\n"
                        end repeat
                    end try
                end repeat
            end repeat
        end try
        return out
    end tell
end tell''',
        timeout=8,
    )
    return raw or ""


def wait_for_live_window(
    name: str,
    timeout: float = 8.0,
    snapshotter=live_window_snapshot,
    clock=time.time,
    sleep=time.sleep,
) -> bool:
    deadline = clock() + timeout
    while clock() < deadline:
        if f"WIN:[{name}]" in snapshotter():
            return True
        sleep(0.2)
    return False
