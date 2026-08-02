from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ContractClause(BaseModel):
    id: str
    contract_id: str
    contract_version_id: str | None = None
    clause_no: str | None = None
    clause_title: str | None = None
    clause_type: str = "其他"
    clause_content: str
    page_number: int | None = None
    start_position: int
    end_position: int
    created_at: datetime
