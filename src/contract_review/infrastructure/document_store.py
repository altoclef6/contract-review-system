from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from sqlalchemy import select

from contract_review.core.config import get_settings
from contract_review.database.models import AppStateModel
from contract_review.database.session import get_session_factory


class JsonDocumentStore:
    """JSON compatibility adapter backed by PostgreSQL in production."""

    def __init__(self, path: Path, namespace: str | None = None) -> None:
        self.path = path
        self.namespace = namespace or path.stem

    def read(self, default: Any) -> Any:
        if get_settings().database_enabled:
            with get_session_factory()() as session:
                record = session.scalar(
                    select(AppStateModel).where(AppStateModel.key == self.namespace)
                )
                return deepcopy(record.value) if record is not None else deepcopy(default)
        if not self.path.exists():
            return deepcopy(default)
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return deepcopy(default)

    def write(self, value: Any) -> None:
        if get_settings().database_enabled:
            with get_session_factory()() as session:
                record = session.get(AppStateModel, self.namespace)
                if record is None:
                    session.add(AppStateModel(key=self.namespace, value=deepcopy(value)))
                else:
                    record.value = deepcopy(value)
                session.commit()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
