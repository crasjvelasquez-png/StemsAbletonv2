from stems.naming import NEW_STEMS_PATTERN, escape_applescript, stem_file_name, stems_folder_name


def test_stems_folder_name_includes_key_and_bpm():
    folder_name = stems_folder_name("Song", "C Major", 120)
    assert folder_name.startswith("Song - ")
    assert folder_name.endswith(" - Stems - C Major 120 BPM")
    assert NEW_STEMS_PATTERN.match(folder_name)


def test_stem_file_name_and_escape_applescript():
    assert stem_file_name("Song", "DRUMS") == "Song_DRUMS.wav"
    assert escape_applescript('a"b\\c') == 'a\\"b\\\\c'
