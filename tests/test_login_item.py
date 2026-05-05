from stems.login_item import install_launch_agent, is_launch_agent_installed, launch_agent_path, remove_launch_agent


def test_launch_agent_install_and_remove(tmp_path):
    script_path = tmp_path / "run_ui.py"
    script_path.write_text("print('hi')")
    agent_path = install_launch_agent(script_path, home=tmp_path)
    assert agent_path == launch_agent_path(tmp_path)
    assert is_launch_agent_installed(tmp_path)
    remove_launch_agent(tmp_path)
    assert not is_launch_agent_installed(tmp_path)
