from pathlib import Path


def test_spec_file_targets_run_ui():
    spec_path = Path("Stems.spec")
    content = spec_path.read_text()
    assert "run_ui.py" in content
    assert 'name="Stems.app"' in content


def test_build_script_invokes_pyinstaller():
    script = Path("build_app.sh").read_text()
    assert "PyInstaller" in script
    assert "Stems.spec" in script
