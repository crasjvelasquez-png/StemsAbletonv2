from pathlib import Path

from stems.models import ExportItemResult, ExportJob, ExportResult, StemTrack
from stems.reporting import build_export_summary


def test_build_export_summary_includes_counts_and_failures(tmp_path):
    job = ExportJob(
        song_name="Song",
        project_folder=tmp_path,
        stems_dir=tmp_path / "Stems",
        tracks=[StemTrack(index=0, name="DRUMS")],
        bpm=120,
        key="A Minor",
    )
    result = ExportResult(
        job=job,
        items=[
            ExportItemResult(track=StemTrack(index=0, name="DRUMS"), output_path=tmp_path / "Song_DRUMS.wav", status="success"),
            ExportItemResult(track=StemTrack(index=1, name="BASS"), output_path=tmp_path / "Song_BASS.wav", status="failed", error="timeout"),
        ],
    )
    summary = build_export_summary(result)
    assert "Song: Song" in summary
    assert "BPM: 120" in summary
    assert "Failures: BASS" in summary
