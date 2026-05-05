from __future__ import annotations

import sys
from pathlib import Path

from .ableton import AbletonClient
from .detection import BUS_NAME_PATTERN
from .errors import AbletonConnectionError, ProjectDetectionError, StemsError
from .export import ExportAutomation, execute_export_job
from .logging_setup import configure_logging
from .models import ExportResult, StemTrack
from .naming import stems_folder_name
from .osc import OSCGateway
from .project import get_stems_folder, rename_old_stems_folders
from .state import AppState


logger = configure_logging()


def ask_key() -> str | None:
    while True:
        raw = input("Key (press Enter to skip): ").strip()
        if not raw:
            return None
        import re

        match = re.match(r"^([A-Ga-g])([#b]?)\s*(m|min|minor|maj|major|M)?$", raw)
        if match:
            note = match.group(1).upper()
            accidental = match.group(2)
            quality_raw = (match.group(3) or "").lower()
            quality = "Minor" if quality_raw in ("m", "min", "minor") else "Major"
            return f"{note}{accidental} {quality}"
        logger.info("  '%s' doesn't look like a key. Try again or press Enter to skip.", raw)


def preview_export_settings(ableton: AbletonClient) -> bool:
    logger.info("\n-- Render preview ---------------------")
    tempo = ableton.get_song_tempo()
    if tempo:
        logger.info("  Tempo:       %s BPM", f"{float(tempo[0]):g}")

    sig_num = ableton.get_signature_numerator()
    sig_den = ableton.get_signature_denominator()
    if sig_num and sig_den:
        logger.info("  Time sig:    %s/%s", int(sig_num[0]), int(sig_den[0]))

    song_length = ableton.get_song_length()
    if song_length and sig_num:
        try:
            total_bars = int(float(song_length[0]) // float(sig_num[0]))
        except (ValueError, TypeError, ZeroDivisionError):
            total_bars = None
        if total_bars is not None:
            logger.info("  Song length: %s measures", total_bars)

    logger.info("---------------------------------------")
    logger.info("Reminder: confirm Ableton export settings before continuing.")
    try:
        choice = input("\nProceed? [y/n]: ").strip().lower()
    except KeyboardInterrupt:
        logger.info("\nCancelled.")
        return False
    return choice in ("y", "yes", "")


def ask_replace_preference(stems_dir: Path, tracks: list[StemTrack], song_name: str) -> str:
    existing = [stems_dir / stem_file_name(song_name, track.name) for track in tracks if (stems_dir / stem_file_name(song_name, track.name)).exists()]
    if not existing:
        return "replace"

    logger.info("\n%s stem(s) already exist in: %s", len(existing), stems_dir)
    for file_path in existing:
        logger.info("  - %s", file_path.name)
    logger.info("\n  [r] Replace existing files")
    logger.info("  [k] Keep existing files (skip already exported stems)")
    while True:
        choice = input("\nChoice [r/k]: ").strip().lower()
        if choice in ("r", "k"):
            return "replace" if choice == "r" else "keep"
        logger.info("  Please enter 'r' or 'k'.")


def _scan_and_prepare():
    gateway = OSCGateway()
    gateway.start_listener()
    ableton = AbletonClient(gateway)
    state = AppState(ableton)

    logger.info("Connecting to Ableton via AbletonOSC...")
    count = ableton.get_track_count()
    if count == 0:
        raise AbletonConnectionError(
            "No response from AbletonOSC. Make sure Ableton is open and AbletonOSC is enabled."
        )

    project, tracks = state.scan_current_set()
    logger.info("Connected. Scanning %s tracks... done\n", count)
    logger.info("-- Track scan -------------------------")
    for track in state.all_tracks:
        matched = "✓ STEM" if BUS_NAME_PATTERN.match(str(track["name"]).strip()) else ""
        logger.info("  [%02d]  %-30s %s", int(track["index"]), str(track["name"]), matched)
    logger.info("---------------------------------------\n")
    if not tracks:
        raise StemsError("No ALL-CAPS tracks found. Name stem tracks like DRUMS, BASS, LOW END.")
    return ableton, state, project, tracks


def export_stems() -> ExportResult:
    logger.info("\n########################################")
    logger.info("#        c4milo_stems backend          #")
    logger.info("########################################\n")

    ableton, state, project, tracks = _scan_and_prepare()
    logger.info("Song:    %s", project.song_name)
    logger.info("BPM:     %s", f"{project.bpm} BPM" if project.bpm is not None else "BPM unknown")
    logger.info("Stems:   %s\n", ", ".join(track.name for track in tracks))

    key = ask_key()
    new_folder_name = stems_folder_name(project.song_name, key, project.bpm)
    rename_old_stems_folders(project.project_folder, new_folder_name)
    stems_dir = get_stems_folder(project.project_folder, project.song_name, key, project.bpm)
    logger.info("\nOutput dir: %s\n", stems_dir)

    replace_mode = ask_replace_preference(stems_dir, tracks, project.song_name)
    job = state.build_export_job(key=key, replace_mode=replace_mode)

    if not preview_export_settings(ableton):
        raise SystemExit(0)

    export_automation = ExportAutomation()
    result = execute_export_job(
        job,
        ableton,
        export_automation,
        progress=lambda _event, message: logger.info("    %s", message),
    )
    logger.info("\nDone: %s/%s stems exported", result.success_count, len(job.selected_tracks))
    logger.info("Location: %s\n", stems_dir)
    return result


def main() -> int:
    try:
        export_stems()
    except SystemExit as exc:
        return int(exc.code or 0)
    except (StemsError, ProjectDetectionError) as exc:
        logger.info("ERROR: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
