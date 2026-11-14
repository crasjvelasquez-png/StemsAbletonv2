from pathlib import Path
from types import SimpleNamespace

import stems.project as project
from stems.errors import ProjectDetectionError


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
        assert "not authorized for assistive access" in str(exc)
    else:
        raise AssertionError("Expected ProjectDetectionError")


def test_get_stems_folder_creates_directory(tmp_path):
    stems_dir = project.get_stems_folder(tmp_path, "Song", None, 120)
    assert stems_dir.exists()
    assert stems_dir.parent == tmp_path


def test_stems_folder_path_does_not_create_directory(tmp_path):
    stems_dir = project.stems_folder_path(tmp_path, "Song", "C Major", 120)
    assert stems_dir.parent == tmp_path
    assert not stems_dir.exists()


def _spotlight_runner(tmp_path, spotlight_replies):
    """Fake osascript plus a Spotlight that answers from a scripted list.

    An item that is an Exception is raised; anything else is the stdout text.
    """
    calls = {"mdfind": 0}

    def runner(command, **_kwargs):
        if command[0] == "osascript":
            return SimpleNamespace(stdout="Song.als\n", returncode=0, stderr="")
        if command[0] == "mdfind":
            reply = spotlight_replies[min(calls["mdfind"], len(spotlight_replies) - 1)]
            calls["mdfind"] += 1
            if isinstance(reply, Exception):
                raise reply
            return SimpleNamespace(stdout=reply, returncode=0, stderr="")
        raise AssertionError(command)

    return runner, calls


def test_spotlight_miss_right_after_a_save_is_retried_before_the_slow_search(tmp_path):
    project_file = tmp_path / "Song Project" / "Song.als"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("x")
    runner, calls = _spotlight_runner(tmp_path, ["", f"{project_file}\n"])

    def finder(_name):
        raise AssertionError("slow disk search must not run when Spotlight answers on retry")

    folder, song_name = project.get_project_info(runner=runner, finder=finder, sleep=lambda _s: None)
    assert (folder, song_name) == (project_file.parent, "Song")
    assert calls["mdfind"] == 2


def test_spotlight_timeout_is_retried(tmp_path):
    project_file = tmp_path / "Song.als"
    project_file.write_text("x")
    import subprocess

    runner, calls = _spotlight_runner(
        tmp_path, [subprocess.TimeoutExpired("mdfind", 5), f"{project_file}\n"],
    )
    folder, _ = project.get_project_info(
        runner=runner, finder=lambda _n: [], sleep=lambda _s: None,
    )
    assert folder == project_file.parent
    assert calls["mdfind"] == 2


def test_spotlight_that_never_answers_falls_back_to_disk_search_after_bounded_retries(tmp_path):
    project_file = tmp_path / "Song.als"
    project_file.write_text("x")
    runner, calls = _spotlight_runner(tmp_path, [""])
    sleeps = []
    finder_calls = []

    def finder(name):
        finder_calls.append(name)
        return [project_file]

    folder, _ = project.get_project_info(runner=runner, finder=finder, sleep=sleeps.append)
    assert folder == project_file.parent
    assert calls["mdfind"] == 3
    assert finder_calls == ["Song"]
    assert sum(sleeps) <= 2.0


def test_first_spotlight_hit_does_not_retry_or_sleep(tmp_path):
    project_file = tmp_path / "Song.als"
    project_file.write_text("x")
    runner, calls = _spotlight_runner(tmp_path, [f"{project_file}\n"])
    sleeps = []
    project.get_project_info(runner=runner, finder=lambda _n: [], sleep=sleeps.append)
    assert calls["mdfind"] == 1
    assert sleeps == []


def test_missing_project_error_still_raised_when_nothing_finds_it(tmp_path):
    runner, _ = _spotlight_runner(tmp_path, [""])
    try:
        project.get_project_info(runner=runner, finder=lambda _n: [], sleep=lambda _s: None)
    except ProjectDetectionError as exc:
        assert "Song.als" in str(exc)
    else:
        raise AssertionError("Expected ProjectDetectionError")
