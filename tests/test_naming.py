from stems.naming import (
    NEW_STEMS_PATTERN,
    escape_applescript,
    render_name,
    stem_file_name,
    stems_folder_name,
    validate_name_format,
)


def test_render_name_all_tokens():
    result = render_name(
        "{song}_{track} - {key} {bpm} BPM.wav",
        song="MySong",
        track="DRUMS",
        key="F# Minor",
        bpm="128",
        index=1,
    )
    assert result == "MySong_DRUMS - F# Minor 128 BPM.wav"


def test_render_name_missing_tokens_removed():
    result = render_name(
        "{song}_{track} - {key} {bpm} BPM.wav",
        song="MySong",
        track="DRUMS",
        key=None,
        bpm="",
    )
    assert result == "MySong_DRUMS -   BPM.wav"


def test_render_name_index_padded():
    result = render_name("{index}_{track}.wav", index=3, track="BASS")
    assert result == "03_BASS.wav"


def test_render_name_date():
    result = render_name(
        "{song} - {date} - Stems",
        song="Track",
        date="May 05 2026",
    )
    assert result == "Track - May 05 2026 - Stems"


def test_stems_folder_name_includes_key_and_bpm():
    folder_name = stems_folder_name("Song", "C Major", 120)
    assert folder_name.startswith("Song - ")
    assert folder_name.endswith(" - Stems - C Major 120 BPM")
    assert NEW_STEMS_PATTERN.match(folder_name)


def test_stems_folder_name_custom_format():
    folder_name = stems_folder_name(
        "Song",
        "C Major",
        120,
        format_string="{song} - {key} - {bpm}",
    )
    assert folder_name == "Song - C Major - 120"


def test_stem_file_name_default():
    assert stem_file_name("Song", "DRUMS") == "Song_DRUMS -   BPM.wav"


def test_stem_file_name_with_key_bpm():
    name = stem_file_name("Song", "DRUMS", key="F# Minor", bpm=128)
    assert name == "Song_DRUMS - F# Minor 128 BPM.wav"


def test_stem_file_name_with_index():
    name = stem_file_name("Song", "DRUMS", index=5)
    assert name == "Song_DRUMS -   BPM.wav"


def test_stem_file_name_custom_format():
    name = stem_file_name(
        "Song",
        "DRUMS",
        key="C Major",
        bpm=120,
        index=3,
        format_string="{index} - {track} ({song}) {key}",
    )
    assert name == "03 - DRUMS (Song) C Major"


def test_stem_file_name_supports_date_token(monkeypatch):
    class FixedDate:
        @classmethod
        def today(cls):
            return cls()

        def strftime(self, _format):
            return "July 15 2026"

    monkeypatch.setattr("stems.naming.date", FixedDate)
    assert stem_file_name("Song", "DRUMS", format_string="{date}_{track}.wav") == "July 15 2026_DRUMS.wav"


def test_validate_stem_format_requires_wav_and_unique_token():
    assert validate_name_format("{song}_{track}", "stem") == "Stem file formats must end in .wav."
    assert validate_name_format("{song}.wav", "stem") == "Add {track} or {index} so each stem gets a unique name."
    assert validate_name_format("{song}_{track}.wav", "stem") is None


def test_validate_formats_reject_unknown_tokens_and_paths():
    assert validate_name_format("{song}/{track}.wav", "stem").startswith("Remove path separators")
    assert validate_name_format("{song} - {track}", "folder") == "Unsupported token: {track}."
    assert validate_name_format("{song} - {date}", "folder") is None


def test_escape_applescript():
    assert escape_applescript('a"b\\c') == 'a\\"b\\\\c'
