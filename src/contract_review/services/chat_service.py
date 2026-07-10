from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.llm.json_client import call_llm_text
from contract_review.schemas.chat import ChatAskResponse, ChatMessage, ChatRole, ChatSessionPublic
from contract_review.services.history_service import HistoryService


class ChatServiceError(ValueError):
    pass


class ChatService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path, review_data_dir: Path) -> None:
        self.path = data_dir / "sessions.json"
        self.store = JsonDocumentStore(self.path, "chat_sessions")
        self.history = HistoryService(review_data_dir)

    def create(self, owner_id: str, review_id: str | None, title: str | None) -> ChatSessionPublic:
        if review_id and self.history.get(review_id) is None:
            raise ChatServiceError("审查记录不存在")
        with self._lock:
            records = self._load()
            now = self._now()
            record = {
                "id": f"chat_{uuid4().hex}",
                "owner_id": owner_id,
                "review_id": review_id,
                "title": title or ("合同审查对话" if review_id else "法务 AI 对话"),
                "messages": [],
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
            self._save(records)
            return self._to_public(record)

    def list_for_user(self, owner_id: str) -> list[ChatSessionPublic]:
        records = [item for item in self._load() if item["owner_id"] == owner_id]
        records.sort(key=lambda item: item["updated_at"], reverse=True)
        return [self._to_public(item) for item in records]

    def get(self, session_id: str, owner_id: str) -> ChatSessionPublic:
        return self._to_public(self._owned(self._load(), session_id, owner_id))

    def delete(self, session_id: str, owner_id: str) -> ChatSessionPublic:
        with self._lock:
            records = self._load()
            target = self._owned(records, session_id, owner_id)
            self._save([item for item in records if item["id"] != session_id])
            return self._to_public(target)

    async def ask(self, session_id: str, owner_id: str, message: str) -> ChatAskResponse:
        with self._lock:
            records = self._load()
            session = self._owned(records, session_id, owner_id)
            user_message = self._message(ChatRole.user, message)
            session["messages"].append(user_message)
            session["updated_at"] = self._now()
            self._save(records)

        context = self._review_context(session.get("review_id"))
        history_messages = [(item["role"], item["content"]) for item in session["messages"][-12:]]
        answer_text = await call_llm_text(
            "你是企业法务合同助手。回答必须使用中文，结合给定审查报告解释风险、法律术语、修改意见或补充条款；不得编造具体法律条文。"
            f"\n\n当前合同审查上下文：\n{context}",
            history_messages,
        )
        ai_available = answer_text is not None
        if answer_text is None:
            answer_text = (
                "当前未连接可用的大语言模型。请由管理员在模型配置中心填写并启用"
                "有效 API Key 后重试。"
            )

        with self._lock:
            records = self._load()
            session = self._owned(records, session_id, owner_id)
            assistant_message = self._message(ChatRole.assistant, answer_text)
            session["messages"].append(assistant_message)
            session["updated_at"] = self._now()
            self._save(records)
            public = self._to_public(session)
        return ChatAskResponse(
            session=public,
            answer=ChatMessage.model_validate(assistant_message),
            ai_available=ai_available,
        )

    def _review_context(self, review_id: str | None) -> str:
        if not review_id:
            return "未绑定具体合同。"
        record = self.history.get(review_id)
        if not record:
            return "绑定的审查记录已不存在。"
        report_path = record.get("exports", {}).get("json") or record.get("report_path")
        if not report_path or not Path(report_path).exists():
            return json.dumps(record, ensure_ascii=False)
        return Path(report_path).read_text(encoding="utf-8")[:18000]

    def _owned(
        self, records: list[dict[str, Any]], session_id: str, owner_id: str
    ) -> dict[str, Any]:
        for record in records:
            if record["id"] == session_id and record["owner_id"] == owner_id:
                return record
        raise ChatServiceError("对话不存在或无权访问")

    def _message(self, role: ChatRole, content: str) -> dict[str, str]:
        return {
            "id": f"msg_{uuid4().hex}",
            "role": role.value,
            "content": content,
            "created_at": self._now(),
        }

    def _load(self) -> list[dict[str, Any]]:
        data = self.store.read([])
        return data if isinstance(data, list) else []

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.store.write(records)

    def _to_public(self, record: dict[str, Any]) -> ChatSessionPublic:
        return ChatSessionPublic.model_validate(record)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
