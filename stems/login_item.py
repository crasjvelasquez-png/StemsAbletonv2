from __future__ import annotations

import plistlib
import sys
from pathlib import Path


LAUNCH_AGENT_ID = "com.c4milo.stems"


def launch_agent_path(home: Path | None = None) -> Path:
    root = home or Path.home()
    return root / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_ID}.plist"


def install_launch_agent(script_path: Path, home: Path | None = None) -> Path:
    agent_path = launch_agent_path(home)
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": LAUNCH_AGENT_ID,
        "ProgramArguments": [sys.executable, str(script_path)],
        "RunAtLoad": True,
        "KeepAlive": False,
    }
    with agent_path.open("wb") as handle:
        plistlib.dump(payload, handle)
    return agent_path


def remove_launch_agent(home: Path | None = None) -> None:
    agent_path = launch_agent_path(home)
    if agent_path.exists():
        agent_path.unlink()


def is_launch_agent_installed(home: Path | None = None) -> bool:
    return launch_agent_path(home).exists()
