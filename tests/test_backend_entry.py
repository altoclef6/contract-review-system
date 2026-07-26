from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from desktop.backend_entry import configure_environment


def test_backend_entry_configures_desktop_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    token = "entry-test-startup-token-0123456789"
    args = argparse.Namespace(
        port=43123,
        data_dir=tmp_path,
        startup_token=token,
        log_dir=tmp_path / "logs",
    )
    configure_environment(args)

    assert os.environ["APP_MODE"] == "desktop"
    assert os.environ["DESKTOP_STARTUP_TOKEN"] == token
    assert os.environ["REDIS_ENABLED"] == "false"
    assert os.environ["DESKTOP_DATA_DIR"] == str(tmp_path.resolve())
    assert (tmp_path / "logs").is_dir()


def test_backend_entry_rejects_log_directory_outside_data(tmp_path: Path) -> None:
    args = argparse.Namespace(
        port=43123,
        data_dir=tmp_path / "data",
        startup_token="a" * 32,
        log_dir=tmp_path / "outside",
    )
    with pytest.raises(SystemExit, match="below --data-dir"):
        configure_environment(args)

