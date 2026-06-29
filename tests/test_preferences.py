from stems.preferences import Preferences, PreferencesStore, RecentExport, append_recent_export


def test_preferences_store_round_trip(tmp_path):
    store = PreferencesStore(tmp_path / "prefs.json")
    prefs = Preferences(
        replace_mode="keep",
        export_destination_root="/tmp/Exports",
        stem_name_format="{song}_{track} - {key}.wav",
        folder_name_format="{song} - {date} - Stems",
    )
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
    assert loaded.replace_mode == "keep"
    assert loaded.export_destination_root == "/tmp/Exports"
    assert loaded.stem_name_format == "{song}_{track} - {key}.wav"
    assert loaded.folder_name_format == "{song} - {date} - Stems"
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


def test_save_preserves_project_locations_from_a_newer_disk_copy(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.save(Preferences(project_locations={"Song": "/Volumes/SSD/Project"}))

    stale_ui_preferences = Preferences(replace_mode="keep")
    store.save(stale_ui_preferences)

    loaded = store.load()
    assert loaded.replace_mode == "keep"
    assert loaded.project_locations == {"Song": "/Volumes/SSD/Project"}


def test_set_project_location_can_remove_stale_entry(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.save(Preferences(project_locations={"Song": "/Volumes/SSD/Project"}))

    store.set_project_location("Song", None)

    assert store.load().project_locations == {}
