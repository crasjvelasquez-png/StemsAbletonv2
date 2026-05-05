from stems.preferences import Preferences, PreferencesStore, RecentExport, append_recent_export


def test_preferences_store_round_trip(tmp_path):
    store = PreferencesStore(tmp_path / "prefs.json")
    prefs = Preferences(default_key="C Major", replace_mode="keep")
    prefs.recent_exports.append(
        RecentExport(
            song_name="Song",
            stems_dir="/tmp/Stems",
            exported_count=4,
            failed_count=1,
            summary="summary",
        )
    )
    store.save(prefs)
    loaded = store.load()
    assert loaded.default_key == "C Major"
    assert loaded.replace_mode == "keep"
    assert loaded.recent_exports[0].song_name == "Song"


def test_append_recent_export_deduplicates_and_limits():
    prefs = Preferences()
    for index in range(7):
        append_recent_export(
            prefs,
            RecentExport(
                song_name=f"Song {index}",
                stems_dir=f"/tmp/{index}",
                exported_count=1,
                failed_count=0,
                summary="ok",
            ),
        )
    append_recent_export(
        prefs,
        RecentExport(
            song_name="Song 6",
            stems_dir="/tmp/6",
            exported_count=2,
            failed_count=0,
            summary="updated",
        ),
    )
    assert len(prefs.recent_exports) == 6
    assert prefs.recent_exports[0].summary == "updated"
