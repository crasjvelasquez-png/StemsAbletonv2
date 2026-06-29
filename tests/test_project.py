from types import SimpleNamespace

import pytest

import stems.project as project
from stems.errors import ProjectDetectionError
from stems.preferences import Preferences, PreferencesStore


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "stems.preferences.default_preferences_path",
        lambda: tmp_path / "preferences.json",
    )


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


def test_get_project_info_retries_spotlight_for_newly_indexed_set(tmp_path):
    candidate = tmp_path / "Different Root Folder" / "Alternate Version.als"
    candidate.parent.mkdir()
    candidate.write_text("x")
    mdfind_calls = {"count": 0}
    sleeps = []

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Alternate Version\n", returncode=0, stderr="")
        if command[0] == "mdfind":
            mdfind_calls["count"] += 1
            stdout = str(candidate) if mdfind_calls["count"] == 2 else ""
            return SimpleNamespace(stdout=stdout, returncode=0, stderr="")
        raise AssertionError(command)

    folder, song_name = project.get_project_info(runner=runner, sleeper=sleeps.append)

    assert folder == candidate.parent
    assert song_name == "Alternate Version"
    assert mdfind_calls["count"] == 2
    assert sleeps == [0.4]


def test_get_project_info_uses_and_validates_cached_project_folder(tmp_path):
    candidate = tmp_path / "Unrelated Project Name" / "Song.als"
    candidate.parent.mkdir()
    candidate.write_text("x")
    store = PreferencesStore(tmp_path / "preferences.json")
    store.save(Preferences(project_locations={"Song": str(candidate.parent)}))

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Song\n", returncode=0, stderr="")
        raise AssertionError("Cache hit should bypass disk lookup")

    folder, song_name = project.get_project_info(runner=runner, preferences_store=store)

    assert (folder, song_name) == (candidate.parent, "Song")


def test_get_project_info_replaces_stale_cache_after_set_moves(tmp_path):
    old_folder = tmp_path / "Old"
    new_candidate = tmp_path / "New" / "Song.als"
    new_candidate.parent.mkdir()
    new_candidate.write_text("x")
    store = PreferencesStore(tmp_path / "preferences.json")
    store.save(Preferences(project_locations={"Song": str(old_folder)}))

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Song\n", returncode=0, stderr="")
        if command[0] == "mdfind":
            return SimpleNamespace(stdout=str(new_candidate), returncode=0, stderr="")
        raise AssertionError(command)

    folder, _song_name = project.get_project_info(runner=runner, preferences_store=store)

    assert folder == new_candidate.parent
    assert store.load().project_locations["Song"] == str(new_candidate.parent)


def test_get_project_info_reports_unmounted_cached_volume(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.save(Preferences(project_locations={"Song": "/Volumes/Missing SSD/Project"}))

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Song\n", returncode=0, stderr="")
        if command[0] == "mdfind":
            return SimpleNamespace(stdout="", returncode=0, stderr="")
        raise AssertionError(command)

    with pytest.raises(ProjectDetectionError, match="Missing SSD.*not mounted"):
        project.get_project_info(
            runner=runner,
            finder=lambda _name: [],
            preferences_store=store,
            sleeper=lambda _delay: None,
        )
    assert "Song" not in store.load().project_locations


def test_get_project_info_reports_disk_search_timeout(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Song\n", returncode=0, stderr="")
        if command[0] == "mdfind":
            return SimpleNamespace(stdout="", returncode=0, stderr="")
        raise AssertionError(command)

    with pytest.raises(ProjectDetectionError, match="timed out"):
        project.get_project_info(
            runner=runner,
            finder=lambda _name: project.DiskSearchResult([], timed_out=True),
            preferences_store=store,
            sleeper=lambda _delay: None,
        )


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


def test_get_project_info_uses_backup_candidate_to_find_project(tmp_path):
    project_file = tmp_path / "Song Project" / "Song.als"
    backup_file = tmp_path / "Song Project" / "Backup" / "Song [2026-05-05 200637].als"
    project_file.parent.mkdir(parents=True)
    backup_file.parent.mkdir(parents=True)
    project_file.write_text("x")
    backup_file.write_text("backup")

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Song.als\n", returncode=0, stderr="")
        if command[0] == "mdfind":
            return SimpleNamespace(stdout=f"{backup_file}\n", returncode=0, stderr="")
        raise AssertionError(command)

    folder, song_name = project.get_project_info(runner=runner)
    assert folder == project_file.parent
    assert song_name == "Song"


def test_get_project_info_includes_window_title_error_detail():
    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="", returncode=1, stderr="not authorized for assistive access")
        raise AssertionError(command)

    try:
        project.get_project_info(runner=runner)
    except ProjectDetectionError as exc:
        assert "Accessibility permission" in str(exc)
        assert "System Settings" in str(exc)
    else:
        raise AssertionError("Expected ProjectDetectionError")


def test_get_project_info_reports_ableton_not_open_for_missing_live_process():
    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(
                stdout="",
                returncode=1,
                stderr='40:44: execution error: System Events got an error: Can’t get process 1 whose name = "Live". Invalid index. (-1719)',
            )
        raise AssertionError(command)

    try:
        project.get_project_info(runner=runner)
    except ProjectDetectionError as exc:
        assert str(exc) == "Ableton is not open"
    else:
        raise AssertionError("Expected ProjectDetectionError")


def test_get_project_info_prioritizes_accessibility_error_over_missing_fallback_process():
    calls = {"count": 0}

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            calls["count"] += 1
            if calls["count"] == 1:
                return SimpleNamespace(
                    stdout="",
                    returncode=1,
                    stderr="System Events got an error: osascript is not allowed assistive access. (-1719)",
                )
            return SimpleNamespace(
                stdout="",
                returncode=1,
                stderr='System Events got an error: Can’t get process 1 whose name = "Live". Invalid index. (-1719)',
            )
        raise AssertionError(command)

    try:
        project.get_project_info(runner=runner)
    except ProjectDetectionError as exc:
        assert "Accessibility permission" in str(exc)
    else:
        raise AssertionError("Expected ProjectDetectionError")


def test_rename_old_stems_folders_renames_legacy_folder(tmp_path):
    legacy = tmp_path / "Stems"
    legacy.mkdir()
    new_name = "Song - January 01 2026 - Stems - 120 BPM"
    project.rename_old_stems_folders(tmp_path, new_name)
    assert (tmp_path / new_name).exists()


def test_get_stems_folder_returns_path_without_creating_directory(tmp_path):
    stems_dir = project.get_stems_folder(tmp_path, "Song", None, 120)
    assert not stems_dir.exists()
    assert stems_dir.parent == tmp_path
