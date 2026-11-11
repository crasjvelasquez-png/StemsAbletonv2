import json
from stems.preferences import Preferences, PreferencesStore, BUILTIN_STEM_NAMING_PRESETS


def test_preferences_round_trip_and_legacy_migration(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"copy_summary_to_clipboard": True, "replace_mode": "keep",
        "recent_exports": [None], "stem_name_presets": [None],
        "stem_name_format": "custom.wav", "panel_width": 620}))
    store = PreferencesStore(path)
    prefs = store.load()
    assert prefs.panel_width == 620
    assert prefs.stem_name_format == Preferences().stem_name_format
    prefs.stem_name_format = BUILTIN_STEM_NAMING_PRESETS[1].format_string
    store.save(prefs)
    assert store.load() == prefs
    payload = json.loads(path.read_text())
    assert "recent_exports" not in payload
    assert "copy_summary_to_clipboard" not in payload
