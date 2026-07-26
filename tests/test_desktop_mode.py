from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from contract_review.core.config import Settings, get_settings
from contract_review.main import create_app
from contract_review.services.local_task_executor import LocalTaskExecutor


def test_desktop_mode_requires_strong_startup_token() -> None:
    with pytest.raises(ValidationError, match="DESKTOP_STARTUP_TOKEN is required"):
        Settings(app_mode="desktop", desktop_startup_token=None)

    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(app_mode="desktop", desktop_startup_token="short")


def test_desktop_mode_rejects_redis() -> None:
    with pytest.raises(ValidationError, match="REDIS_ENABLED must be false"):
        Settings(
            app_mode="desktop",
            desktop_startup_token="a" * 32,
            redis_enabled=True,
        )


def test_desktop_startup_token_protects_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    token = "desktop-test-startup-token-0123456789"
    monkeypatch.setenv("APP_MODE", "desktop")
    monkeypatch.setenv("DESKTOP_STARTUP_TOKEN", token)
    monkeypatch.setenv("DESKTOP_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        public = client.get("/api/v1/health/live")
        missing = client.get("/api/v1/health")
        invalid = client.get(
            "/api/v1/health",
            headers={"X-Desktop-Startup-Token": f"{token}-invalid"},
        )
        accepted = client.get(
            "/api/v1/health",
            headers={"X-Desktop-Startup-Token": token},
        )

    assert public.status_code == 200
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert accepted.status_code == 200
    assert (tmp_path / "database" / "contract-review.db").is_file()
    assert {
        "database",
        "uploads",
        "reports",
        "logs",
        "config",
        "backups",
    }.issubset({item.name for item in tmp_path.iterdir()})


def test_desktop_paths_and_sqlite_are_derived_from_data_dir(tmp_path: Path) -> None:
    settings = Settings(
        app_mode="desktop",
        desktop_startup_token="a" * 32,
        desktop_data_dir=tmp_path,
    )

    assert settings.database_enabled is True
    assert settings.redis_enabled is False
    assert settings.database_url.get_secret_value().startswith("sqlite+pysqlite:///")
    assert settings.upload_dir == tmp_path / "uploads"
    assert settings.report_dir == tmp_path / "reports"
    managed_paths = (
        settings.contract_data_dir,
        settings.model_config_data_dir,
        settings.security_data_dir,
        settings.review_task_data_dir,
    )
    assert all(path.is_relative_to(tmp_path) for path in managed_paths)


@pytest.mark.asyncio
async def test_local_executor_retains_and_cancels_tasks() -> None:
    executor = LocalTaskExecutor()
    started = asyncio.Event()

    async def work() -> None:
        started.set()
        await asyncio.Event().wait()

    executor.submit(work(), max_concurrent=1)
    await asyncio.wait_for(started.wait(), timeout=1)
    assert executor._tasks
    await executor.shutdown()
    assert not executor._tasks
