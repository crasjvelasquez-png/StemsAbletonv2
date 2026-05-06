from pathlib import Path

from stems.naming import stems_folder_name
from stems.state import AppState


class FakeAbletonClient:
    def get_track_count(self):
        return 3

    def get_bpm(self):
        return 120

    def get_all_tracks(self, count):
        assert count == 3
        return [
            {"index": 0, "name": "DRUMS"},
            {"index": 1, "name": "lead"},
            {"index": 2, "name": "BASS"},
        ]


def test_app_state_scans_and_builds_export_job(tmp_path):
    state = AppState(
        FakeAbletonClient(),
        project_info_getter=lambda: (tmp_path, "Song"),
        stems_folder_getter=lambda folder, song, key, bpm, **kw: folder / f"{song}_{key}_{bpm}",
    )
    project, tracks = state.scan_current_set()
    assert project.song_name == "Song"
    assert [track.name for track in tracks] == ["DRUMS", "BASS"]

    job = state.build_export_job(key="C Major", replace_mode="keep")
    assert job.stems_dir == Path(tmp_path / "Song_C Major_120")
    assert job.replace_mode == "keep"


def test_app_state_builds_export_job_with_destination_root(tmp_path):
    state = AppState(
        FakeAbletonClient(),
        project_info_getter=lambda: (tmp_path / "Project", "Song"),
    )
    state.scan_current_set()

    destination_root = tmp_path / "Exports"
    job = state.build_export_job(key="C Major", replace_mode="replace", destination_root=destination_root)

    assert job.stems_dir == destination_root / stems_folder_name("Song", "C Major", 120)
    assert job.stems_dir.exists()
    assert job.replace_mode == "replace"
