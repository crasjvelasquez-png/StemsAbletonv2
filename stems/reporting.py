from __future__ import annotations

from .models import ExportResult


def build_export_summary(result: ExportResult) -> str:
    bpm = result.job.bpm if result.job.bpm is not None else "Unknown"
    key = result.job.key or "Unknown"
    exported = [item.track.name for item in result.items if item.status in {"success", "skipped"}]
    failed = [item.track.name for item in result.items if item.status == "failed"]
    lines = [
        f"Song: {result.job.song_name}",
        f"BPM: {bpm}",
        f"Key: {key}",
        f"Destination: {result.job.stems_dir}",
        f"Exported stems: {', '.join(exported) if exported else 'None'}",
        f"Failures: {', '.join(failed) if failed else 'None'}",
    ]
    return "\n".join(lines)
