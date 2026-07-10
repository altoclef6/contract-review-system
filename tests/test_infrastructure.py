from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from contract_review.core.config import Settings
from contract_review.database import models  # noqa: F401
from contract_review.database.base import Base
from contract_review.infrastructure.cache import CacheService


def test_enterprise_postgresql_schema_compiles() -> None:
    expected = {
        "users",
        "contracts",
        "contract_versions",
        "reviews",
        "model_configs",
        "prompt_templates",
        "workflows",
        "notifications",
        "audit_logs",
        "app_state",
    }
    assert expected.issubset(Base.metadata.tables)
    for table_name in expected:
        ddl = str(
            CreateTable(Base.metadata.tables[table_name]).compile(dialect=postgresql.dialect())
        )
        assert f"CREATE TABLE {table_name}" in ddl


def test_cache_is_optional_for_local_development() -> None:
    cache = CacheService(Settings(redis_enabled=False))
    assert cache.ping() is False
    assert cache.get_json("missing") is None
    assert cache.set_json("key", {"value": 1}) is False
