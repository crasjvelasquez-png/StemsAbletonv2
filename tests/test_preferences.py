import json

from stems.preferences import (
    NamingPreset,
    Preferences,
    PreferencesStore,
    RecentExport,
    append_recent_export,
)


def test_preferences_store_round_trip(tmp_path):
    store = PreferencesStore(tmp_path / "prefs.json")
    prefs = Preferences(
        replace_mode="keep",
        export_destination_root="/tmp/Exports",
        panel_width=620,
        panel_height=760,
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
    assert loaded.panel_width == 620
    assert loaded.panel_height == 760
    assert loaded.stem_name_format == "{song}_{track} - {key}.wav"
    assert loaded.folder_name_format == "{song} - {date} - Stems"
    assert loaded.recent_exports[0].song_name == "Song"


def test_preferences_store_round_trips_independent_naming_presets(tmp_path):
    store = PreferencesStore(tmp_path / "prefs.json")
    prefs = Preferences(
        stem_name_format="{song}_{track}_mix.wav",
        folder_name_format="{song} Mixes",
        stem_name_presets=[NamingPreset("custom-stem-mix", "Mix", "{song}_{track}_mix.wav")],
        folder_name_presets=[NamingPreset("custom-folder-mixes", "Mixes", "{song} Mixes")],
        default_stem_name_preset_id="custom-stem-mix",
        default_folder_name_preset_id="custom-folder-mixes",
    )

    store.save(prefs)
    loaded = store.load()

    assert loaded.stem_name_presets == prefs.stem_name_presets
    assert loaded.folder_name_presets == prefs.folder_name_presets
    assert loaded.default_stem_name_preset_id == "custom-stem-mix"
    assert loaded.default_folder_name_preset_id == "custom-folder-mixes"


def test_preferences_store_migrates_legacy_custom_formats_without_rewriting(tmp_path):
    path = tmp_path / "prefs.json"
    payload = {
        "stem_name_format": "{track}_{song}_archive.wav",
        "folder_name_format": "Archive - {song}",
    }
    path.write_text(json.dumps(payload, indent=2))

    loaded = PreferencesStore(path).load()

    assert loaded.default_stem_name_preset_id == "custom-stem-current"
    assert loaded.stem_name_presets[0].format_string == "{track}_{song}_archive.wav"
    assert loaded.default_folder_name_preset_id == "custom-folder-current"
    assert loaded.folder_name_presets[0].format_string == "Archive - {song}"
    assert json.loads(path.read_text()) == payload


def test_preferences_store_ignores_malformed_custom_presets(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"stem_name_presets": [{"name": "Missing fields"}, None]}))

    loaded = PreferencesStore(path).load()

    assert loaded.stem_name_presets == []


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
