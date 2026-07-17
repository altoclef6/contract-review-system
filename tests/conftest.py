from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Application modules create a module-level ASGI app during test collection.
# Force test mode before importing application settings so Pydantic never reads a local .env.
_collection_root = Path(tempfile.mkdtemp(prefix="contract-review-tests-"))
atexit.register(shutil.rmtree, _collection_root, ignore_errors=True)
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_ENABLED"] = "false"
os.environ["REDIS_ENABLED"] = "false"
os.environ["ENABLE_LLM"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "Admin12345!"
os.environ["MODEL_CREDENTIAL_ENCRYPTION_KEY"] = "test-secret"
for _env_name, _directory in {
    "UPLOAD_DIR": "uploads",
    "REPORT_DIR": "reports",
    "CONTRACT_DATA_DIR": "contracts",
    "MODEL_CONFIG_DATA_DIR": "model-configs",
    "PROMPT_TEMPLATE_DATA_DIR": "prompt-templates",
    "CHAT_DATA_DIR": "chats",
    "WORKFLOW_DATA_DIR": "workflows",
    "NOTIFICATION_DATA_DIR": "notifications",
    "SECURITY_DATA_DIR": "security",
    "REVIEW_TASK_DATA_DIR": "review-tasks",
    "RULE_CENTER_DATA_DIR": "rule-center",
    "KNOWLEDGE_CENTER_DATA_DIR": "knowledge-center",
    "RISK_FEEDBACK_DATA_DIR": "risk-feedback",
}.items():
    os.environ[_env_name] = str(_collection_root / _directory)

from contract_review.core.config import get_settings  # noqa: E402
from contract_review.database.session import get_engine, get_session_factory  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Keep every test away from developer .env files and persistent runtime data."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DATABASE_ENABLED", "false")
    monkeypatch.setenv("REDIS_ENABLED", "false")
    monkeypatch.setenv("ENABLE_LLM", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin12345!")
    monkeypatch.setenv("MODEL_CREDENTIAL_ENCRYPTION_KEY", "test-secret")
    for env_name, directory in {
        "UPLOAD_DIR": "uploads",
        "REPORT_DIR": "reports",
        "CONTRACT_DATA_DIR": "contracts",
        "MODEL_CONFIG_DATA_DIR": "model-configs",
        "PROMPT_TEMPLATE_DATA_DIR": "prompt-templates",
        "CHAT_DATA_DIR": "chats",
        "WORKFLOW_DATA_DIR": "workflows",
        "NOTIFICATION_DATA_DIR": "notifications",
        "SECURITY_DATA_DIR": "security",
        "REVIEW_TASK_DATA_DIR": "review-tasks",
        "RULE_CENTER_DATA_DIR": "rule-center",
        "KNOWLEDGE_CENTER_DATA_DIR": "knowledge-center",
        "RISK_FEEDBACK_DATA_DIR": "risk-feedback",
    }.items():
        monkeypatch.setenv(env_name, str(tmp_path / directory))
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
