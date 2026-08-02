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
    # configure_environment intentionally writes directly to os.environ because
    # the desktop backend process needs these values after this function returns.
    # Register the keys with monkeypatch first so pytest restores them after the
    # test instead of leaking desktop mode into the rest of the API suite.
    for key in (
        "APP_MODE",
        "ENVIRONMENT",
        "DESKTOP_STARTUP_TOKEN",
        "REDIS_ENABLED",
        "DESKTOP_DATA_DIR",
        "ENABLE_LLM",
        "JWT_SECRET_KEY",
        "BOOTSTRAP_ADMIN_EMAIL",
        "BOOTSTRAP_ADMIN_PASSWORD",
        "BOOTSTRAP_ADMIN_NAME",
        "MODEL_CREDENTIAL_ENCRYPTION_KEY",
        "TRUSTED_HOSTS",
        "ALLOWED_ORIGINS",
    ):
        # setenv records the original state even when the key was initially
        # absent; direct writes performed below are then undone by the fixture.
        monkeypatch.setenv(key, "__pytest_restore__")

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
    assert os.environ["BOOTSTRAP_ADMIN_EMAIL"] == "admin@example.com"
    assert os.environ["BOOTSTRAP_ADMIN_PASSWORD"] == "Admin12345!"
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

