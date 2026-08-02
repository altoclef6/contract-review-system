from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.contract_clause import ContractClause


class ContractClauseService:
    """Small deterministic clause splitter used by both JSON demo mode and SQL deployments."""

    _lock = threading.Lock()
    _heading = re.compile(
        r"(?m)^\s*(?P<no>第[一二三四五六七八九十百千万零〇两\d]+[章节条]|"
        r"[一二三四五六七八九十百]+、|\d+(?:\.\d+)+(?:[、.]|\s))\s*"
        r"(?P<title>[^\n]{0,80})"
    )
    _types = {
        "付款条件": ("付款", "支付", "价款", "结算"),
        "验收标准": ("验收", "测试", "验收标准"),
        "知识产权": ("知识产权", "著作权", "专利", "源代码"),
        "违约责任": ("违约", "赔偿", "违约金"),
        "合同解除": ("解除", "终止", "提前解约"),
        "保密义务": ("保密", "商业秘密"),
        "争议解决": ("争议", "仲裁", "管辖", "人民法院"),
        "交付履行": ("交付", "履行期限", "项目进度"),
    }

    def __init__(self, contract_data_dir: Path) -> None:
        self.store = JsonDocumentStore(
            contract_data_dir / "contract-clauses.json", "contract_clauses"
        )

    def split_and_save(
        self, *, contract_id: str, contract_version_id: str, text: str
    ) -> list[ContractClause]:
        clauses = self.split(
            contract_id=contract_id,
            contract_version_id=contract_version_id,
            text=text,
        )
        with self._lock:
            current = self._load()
            retained = [
                item for item in current if item.contract_version_id != contract_version_id
            ]
            self._save([*retained, *clauses])
        return clauses

    def list_for_contract(
        self, contract_id: str, contract_version_id: str | None = None
    ) -> list[ContractClause]:
        items = [item for item in self._load() if item.contract_id == contract_id]
        if contract_version_id:
            items = [item for item in items if item.contract_version_id == contract_version_id]
        return sorted(items, key=lambda item: (item.start_position, item.created_at))

    def split(
        self, *, contract_id: str, contract_version_id: str, text: str
    ) -> list[ContractClause]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []
        matches = list(self._heading.finditer(normalized))
        ranges: list[tuple[int, int, str | None, str | None]] = []
        if matches:
            if matches[0].start() > 0 and normalized[: matches[0].start()].strip():
                ranges.append((0, matches[0].start(), "前言", "合同前言"))
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
                ranges.append(
                    (
                        match.start(),
                        end,
                        match.group("no").strip(),
                        (match.group("title") or "").strip(" ：:") or None,
                    )
                )
        else:
            paragraphs = [item for item in re.finditer(r"(?ms)\S.*?(?=\n\s*\n|\Z)", normalized)]
            if len(paragraphs) > 1:
                for index, match in enumerate(paragraphs, start=1):
                    first_line = match.group().splitlines()[0].strip()
                    ranges.append(
                        (match.start(), match.end(), str(index), first_line[:80] or f"第{index}段")
                    )
            else:
                ranges.append((0, len(normalized), "全文", "合同全文"))

        now = datetime.now(timezone.utc)
        clauses: list[ContractClause] = []
        for start, end, clause_no, title in ranges:
            content = normalized[start:end].strip()
            if not content:
                continue
            actual_start = normalized.find(content, start, end)
            actual_end = actual_start + len(content)
            clauses.append(
                ContractClause(
                    id=f"clause_{uuid4().hex}",
                    contract_id=contract_id,
                    contract_version_id=contract_version_id,
                    clause_no=clause_no,
                    clause_title=title,
                    clause_type=self._classify(content),
                    clause_content=content,
                    page_number=normalized.count("\f", 0, actual_start) + 1,
                    start_position=actual_start,
                    end_position=actual_end,
                    created_at=now,
                )
            )
        if clauses:
            return clauses
        return [
            ContractClause(
                id=f"clause_{uuid4().hex}",
                contract_id=contract_id,
                contract_version_id=contract_version_id,
                clause_no="全文",
                clause_title="合同全文",
                clause_type="其他",
                clause_content=normalized,
                page_number=1,
                start_position=0,
                end_position=len(normalized),
                created_at=now,
            )
        ]

    def _classify(self, content: str) -> str:
        for clause_type, keywords in self._types.items():
            if any(keyword in content for keyword in keywords):
                return clause_type
        return "其他"

    def _load(self) -> list[ContractClause]:
        data = self.store.read([])
        if not isinstance(data, list):
            return []
        return [ContractClause.model_validate(item) for item in data]

    def _save(self, clauses: list[ContractClause]) -> None:
        self.store.write([item.model_dump(mode="json") for item in clauses])
