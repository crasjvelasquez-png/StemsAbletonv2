from stems.naming import (
    escape_applescript,
    validate_name_format,
)


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
