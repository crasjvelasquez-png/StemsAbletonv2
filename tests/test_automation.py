from stems.automation import wait_for_live_window


def test_wait_for_live_window_returns_true_when_window_appears():
    snapshots = iter(["", "WIN:[Export Audio/Video] sheets=0"])
    times = iter([0.0, 0.1, 0.2])

    assert wait_for_live_window(
        "Export Audio/Video",
        timeout=1.0,
        snapshotter=lambda: next(snapshots),
        clock=lambda: next(times),
        sleep=lambda _seconds: None,
    )
