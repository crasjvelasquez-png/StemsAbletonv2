from stems.detection import find_bus_tracks, is_stem_candidate


def test_is_stem_candidate_accepts_all_caps_bus_names():
    assert is_stem_candidate("DRUMS")
    assert is_stem_candidate("LOW END")
    assert is_stem_candidate("FX 2")


def test_is_stem_candidate_rejects_excluded_or_short_names():
    assert not is_stem_candidate("MASTER")
    assert not is_stem_candidate("A")
    assert not is_stem_candidate("lead")


def test_find_bus_tracks_returns_stem_tracks():
    tracks = find_bus_tracks(
        [
            {"index": 0, "name": "DRUMS"},
            {"index": 1, "name": "lead vox"},
            {"index": 2, "name": "LOW END"},
        ]
    )
    assert [track.name for track in tracks] == ["DRUMS", "LOW END"]
