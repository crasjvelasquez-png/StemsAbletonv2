import time

import pytest

from stems.errors import ExportAutomationError, PreflightCheckError
from stems.export import ExportAutomation, execute_export_job, verify_exported_file, wait_for_new_wav
from stems.models import ExportJob, StemTrack


def test_wait_for_new_wav_returns_settled_file(tmp_path):
    export_start = time.time() - 1
    output = tmp_path / "Song_DRUMS.wav"
    output.write_bytes(b"1234")
    found = wait_for_new_wav(tmp_path, export_start, timeout=1)
    assert found == output


class FakeAbletonClient:
    def __init__(self):
        self.solo = {}

    def get_track_count(self):
        return 2

    def get_track_solo(self, track_index):
        return self.solo.get(track_index, False)

    def set_track_solo(self, track_index, soloed):
        self.solo[track_index] = soloed


class FakeExportAutomation:
    def __init__(self):
        self.app_path_finder = lambda: "/Applications/Ableton Live.app"
        self.script_runner = lambda _script, timeout=5: "1"

    def trigger_export(self, output_path, project_folder, navigate_folder=True, progress=None):
        del project_folder, navigate_folder
        output_path.write_bytes(b"wav")
        if progress is not None:
            progress("success", f"Exported {output_path.stem.split('_', 1)[1]}")
        return True


def test_execute_export_job_exports_selected_tracks(tmp_path):
    job = ExportJob(
        song_name="Song",
        project_folder=tmp_path,
        stems_dir=tmp_path,
        tracks=[StemTrack(index=0, name="DRUMS"), StemTrack(index=1, name="BASS")],
        replace_mode="replace",
    )
    result = execute_export_job(job, FakeAbletonClient(), FakeExportAutomation())
    assert result.success_count == 2
    assert (tmp_path / "Song_DRUMS.wav").exists()
    assert (tmp_path / "Song_BASS.wav").exists()


def test_verify_exported_file_rejects_empty_files(tmp_path):
    output = tmp_path / "Song_DRUMS.wav"
    output.write_bytes(b"")
    with pytest.raises(ExportAutomationError):
        verify_exported_file(output)


def test_execute_export_job_fails_preflight_when_ableton_missing(tmp_path):
    job = ExportJob(
        song_name="Song",
        project_folder=tmp_path,
        stems_dir=tmp_path,
        tracks=[StemTrack(index=0, name="DRUMS")],
    )
    automation = FakeExportAutomation()
    automation.app_path_finder = lambda: None
    with pytest.raises(PreflightCheckError):
        execute_export_job(job, FakeAbletonClient(), automation)


def test_trigger_export_retries_before_succeeding(tmp_path):
    class FakePyAutoGUI:
        FAILSAFE = False
        PAUSE = 0.0

        def __init__(self):
            self.keys = []

        def hotkey(self, *keys):
            self.keys.append(("hotkey", keys))

        def press(self, key):
            self.keys.append(("press", key))

    calls = {"count": 0}

    def fake_script_runner(_script, timeout=20):
        del timeout
        calls["count"] += 1
        if calls["count"] == 1:
            return "ERROR: transient"
        return "ok"

    automation = ExportAutomation(
        pyautogui_module=FakePyAutoGUI(),
        runner=lambda *_args, **_kwargs: None,
        sleep=lambda _seconds: None,
        script_runner=fake_script_runner,
        app_path_finder=lambda: "/Applications/Ableton Live.app",
        window_waiter=lambda _name, timeout=8.0: True,
    )

    output = tmp_path / "Song_DRUMS.wav"

    def fake_wait_for_new_wav(_stems_dir, _export_start, timeout=120, sleep=None, clock=None):
        del timeout, sleep, clock
        output.write_bytes(b"wav")
        return output

    import stems.export as export_module

    original = export_module.wait_for_new_wav
    export_module.wait_for_new_wav = fake_wait_for_new_wav
    try:
        assert automation.trigger_export(output, tmp_path)
    finally:
        export_module.wait_for_new_wav = original

    assert calls["count"] == 2
