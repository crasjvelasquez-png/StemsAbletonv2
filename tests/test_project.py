from pathlib import Path
from types import SimpleNamespace

import stems.project as project


def test_get_project_info_uses_latest_candidate(tmp_path):
    first = tmp_path / "older" / "Song.als"
    second = tmp_path / "newer" / "Song.als"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("x")
    second.write_text("y")

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Song.als*\n", returncode=0, stderr="")
        if command[0] == "mdfind":
            return SimpleNamespace(stdout=f"{first}\n{second}\n", returncode=0, stderr="")
        raise AssertionError(command)

    second.touch()
    folder, song_name = project.get_project_info(runner=runner)
    assert folder == second.parent
    assert song_name == "Song"


def test_get_project_info_falls_back_to_ableton_live_process_name(tmp_path):
    candidate = tmp_path / "Song.als"
    candidate.write_text("x")

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            script = command[2]
            if 'name starts with "Ableton Live"' in script:
                return SimpleNamespace(stdout="Song.als\n", returncode=0, stderr="")
            if 'name is "Live"' in script:
                return SimpleNamespace(stdout="", returncode=1, stderr="process not found")
        if command[0] == "mdfind":
            return SimpleNamespace(stdout=f"{candidate}\n", returncode=0, stderr="")
        raise AssertionError(command)

    folder, song_name = project.get_project_info(runner=runner)
    assert folder == candidate.parent
    assert song_name == "Song"


def test_rename_old_stems_folders_renames_legacy_folder(tmp_path):
    legacy = tmp_path / "Stems"
    legacy.mkdir()
    new_name = "Song - January 01 2026 - Stems - 120 BPM"
    project.rename_old_stems_folders(tmp_path, new_name)
    assert (tmp_path / new_name).exists()


def test_get_stems_folder_creates_directory(tmp_path):
    stems_dir = project.get_stems_folder(tmp_path, "Song", None, 120)
    assert stems_dir.exists()
    assert stems_dir.parent == tmp_path
