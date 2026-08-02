from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from contract_review.core.config import Settings
from contract_review.database.models import (
    ContractRiskRuleModel,
    LegalArticleModel,
    LegalDocumentModel,
    LegalDocumentVersionModel,
    ReviewIssueLegalArticleModel,
    RiskFindingModel,
    RiskRuleLegalArticleModel,
)
from contract_review.database.session import get_session_factory
from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.legal_knowledge import (
    ContractRiskRuleCreate,
    ContractRiskRuleRecord,
    ContractRiskRuleUpdate,
    ContractRiskRuleWrite,
    DemoSeedResponse,
    LegalArticleCreate,
    LegalArticleRecord,
    LegalArticleUpdate,
    LegalArticleWrite,
    LegalBasisReference,
    LegalDocumentCreate,
    LegalDocumentRecord,
    LegalDocumentUpdate,
    LegalDocumentVersionRecord,
    LegalDocumentWrite,
    LegalEffectStatus,
    VerificationStatus,
)


class LegalKnowledgeError(ValueError):
    pass


class LegalKnowledgeConflictError(LegalKnowledgeError):
    pass


class LegalKnowledgeService:
    """Versioned legal knowledge repository using the project's safe document-store adapter.

    In local acceptance mode the adapter writes JSON files. When DATABASE_ENABLED is true,
    the compatibility document store remains the read path while every write is mirrored into
    the normalized legal tables created by the accompanying Alembic migration.
    """

    _lock = threading.RLock()

    def __init__(self, settings: Settings) -> None:
        root = settings.legal_knowledge_data_dir
        self.settings = settings
        self.documents = JsonDocumentStore(root / "documents.json", "legal_documents_v1")
        self.versions = JsonDocumentStore(root / "versions.json", "legal_document_versions_v1")
        self.articles = JsonDocumentStore(root / "articles.json", "legal_articles_v1")
        self.rules = JsonDocumentStore(root / "risk-rules.json", "contract_risk_rules_v1")
        self.review_links = JsonDocumentStore(
            root / "review-issue-links.json", "review_issue_legal_articles_v1"
        )

    def _list(self, store: JsonDocumentStore) -> list[dict[str, Any]]:
        value = store.read([])
        return value if isinstance(value, list) else []

    def list_documents(
        self,
        *,
        name: str | None = None,
        document_type: str | None = None,
        effect_status: LegalEffectStatus | None = None,
        include_disabled: bool = False,
        public_only: bool = False,
    ) -> list[LegalDocumentRecord]:
        items = [LegalDocumentRecord.model_validate(item) for item in self._list(self.documents)]
        if not include_disabled:
            items = [item for item in items if item.is_enabled]
        if public_only:
            items = [item for item in items if self._document_is_usable(item)]
        if name:
            term = name.casefold().strip()
            items = [item for item in items if term in item.name.casefold()]
        if document_type:
            items = [item for item in items if item.document_type == document_type]
        if effect_status:
            items = [item for item in items if item.effect_status == effect_status]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def get_document(self, document_id: str) -> LegalDocumentRecord:
        item = next(
            (item for item in self._list(self.documents) if item.get("id") == document_id),
            None,
        )
        if item is None:
            raise LegalKnowledgeError("法律文件不存在")
        return LegalDocumentRecord.model_validate(item)

    def create_document(
        self, payload: LegalDocumentCreate, actor_id: str
    ) -> LegalDocumentRecord:
        with self._lock:
            documents = self._list(self.documents)
            duplicate = any(
                item.get("name") == payload.name
                and item.get("version_number") == payload.version_number
                for item in documents
            )
            if duplicate:
                raise LegalKnowledgeConflictError("同名同版本法律文件已存在")
            now = self._now()
            document_id = f"law_{uuid4().hex}"
            record = {
                "id": document_id,
                **payload.model_dump(mode="json", exclude={"change_summary"}),
                "official_source_url": (
                    str(payload.official_source_url) if payload.official_source_url else None
                ),
                "created_by": actor_id,
                "created_at": now,
                "updated_at": now,
            }
            version = self._build_version(
                document_id,
                payload,
                actor_id,
                payload.change_summary or "创建首个版本",
                now,
            )
            documents.append(record)
            versions = self._list(self.versions)
            versions.append(version)
            self.documents.write(documents)
            self.versions.write(versions)
            self._sync_structured_database()
        return LegalDocumentRecord.model_validate(record)

    def update_document(
        self, document_id: str, payload: LegalDocumentUpdate, actor_id: str
    ) -> LegalDocumentRecord:
        current = self.get_document(document_id)
        merged = current.model_dump(
            exclude={"id", "created_by", "created_at", "updated_at"}
        )
        changes = payload.model_dump(exclude_unset=True)
        change_summary = changes.pop("change_summary", None)
        merged.update(changes)
        write = LegalDocumentWrite.model_validate({**merged, "change_summary": change_summary})
        with self._lock:
            documents = self._list(self.documents)
            index = next(
                (i for i, item in enumerate(documents) if item.get("id") == document_id),
                None,
            )
            if index is None:
                raise LegalKnowledgeError("法律文件不存在")
            if set(changes) == {"is_enabled"}:
                record = {
                    **documents[index],
                    "is_enabled": write.is_enabled,
                    "updated_at": self._now(),
                }
                documents[index] = record
                self.documents.write(documents)
                self._sync_structured_database()
                return LegalDocumentRecord.model_validate(record)
            versions = self._list(self.versions)
            if any(
                item.get("legal_document_id") == document_id
                and item.get("version_number") == write.version_number
                for item in versions
            ):
                raise LegalKnowledgeConflictError("该法律版本号已存在，旧版本不会被覆盖")
            now = self._now()
            record = {
                "id": document_id,
                **write.model_dump(mode="json", exclude={"change_summary"}),
                "official_source_url": (
                    str(write.official_source_url) if write.official_source_url else None
                ),
                "created_by": current.created_by,
                "created_at": current.created_at.isoformat(),
                "updated_at": now,
            }
            documents[index] = record
            versions.append(
                self._build_version(
                    document_id,
                    write,
                    actor_id,
                    change_summary or "管理员创建新版本",
                    now,
                )
            )
            self.documents.write(documents)
            self.versions.write(versions)
            self._sync_structured_database()
        return LegalDocumentRecord.model_validate(record)

    def list_versions(self, document_id: str | None = None) -> list[LegalDocumentVersionRecord]:
        items = [
            LegalDocumentVersionRecord.model_validate(item) for item in self._list(self.versions)
        ]
        if document_id:
            self.get_document(document_id)
            items = [item for item in items if item.legal_document_id == document_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get_version(self, version_id: str) -> LegalDocumentVersionRecord:
        item = next(
            (item for item in self._list(self.versions) if item.get("id") == version_id),
            None,
        )
        if item is None:
            raise LegalKnowledgeError("法律版本不存在")
        return LegalDocumentVersionRecord.model_validate(item)

    def create_article(
        self, payload: LegalArticleCreate, actor_id: str
    ) -> LegalArticleRecord:
        document = self.get_document(payload.legal_document_id)
        version = self.get_version(payload.legal_document_version_id)
        if version.legal_document_id != document.id:
            raise LegalKnowledgeError("法律条文必须关联该法律文件的具体版本")
        with self._lock:
            articles = self._list(self.articles)
            if any(
                item.get("legal_document_version_id") == version.id
                and item.get("article_no") == payload.article_no
                for item in articles
            ):
                raise LegalKnowledgeConflictError("该版本下的条号已存在")
            now = self._now()
            record = {
                "id": f"article_{uuid4().hex}",
                **payload.model_dump(mode="json"),
                "created_by": actor_id,
                "created_at": now,
                "updated_at": now,
            }
            articles.append(record)
            self.articles.write(articles)
            self._sync_structured_database()
        return self._enrich_article(record)

    def update_article(
        self, article_id: str, payload: LegalArticleUpdate, actor_id: str
    ) -> LegalArticleRecord:
        current = self.get_article(article_id, public_only=False)
        merged = current.model_dump(
            exclude={
                "id",
                "law_name",
                "law_version",
                "effect_status",
                "source_name",
                "source_url",
                "created_by",
                "created_at",
                "updated_at",
            }
        )
        merged.update(payload.model_dump(exclude_unset=True))
        write = LegalArticleWrite.model_validate(merged)
        with self._lock:
            articles = self._list(self.articles)
            index = next(
                (i for i, item in enumerate(articles) if item.get("id") == article_id),
                None,
            )
            if index is None:
                raise LegalKnowledgeError("法律条文不存在")
            record = {
                "id": article_id,
                **write.model_dump(mode="json"),
                "created_by": current.created_by,
                "created_at": current.created_at.isoformat(),
                "updated_at": self._now(),
            }
            articles[index] = record
            self.articles.write(articles)
            self._sync_structured_database()
        return self._enrich_article(record)

    def deactivate_article(self, article_id: str, actor_id: str) -> LegalArticleRecord:
        return self.update_article(
            article_id,
            LegalArticleUpdate(is_effective=False),
            actor_id,
        )

    def get_article(self, article_id: str, *, public_only: bool = True) -> LegalArticleRecord:
        item = next(
            (item for item in self._list(self.articles) if item.get("id") == article_id),
            None,
        )
        if item is None:
            raise LegalKnowledgeError("法律条文不存在")
        record = self._enrich_article(item)
        if public_only and not self._article_is_usable(record):
            raise LegalKnowledgeError("法律条文未核验、未生效或已停用")
        return record

    def search_articles(
        self,
        *,
        law_name: str | None = None,
        article_no: str | None = None,
        keyword: str | None = None,
        legal_topic: str | None = None,
        contract_type: str | None = None,
        clause_type: str | None = None,
        effect_status: LegalEffectStatus | None = None,
        include_unverified: bool = False,
        limit: int = 100,
    ) -> list[LegalArticleRecord]:
        items = [self._enrich_article(item) for item in self._list(self.articles)]
        if not include_unverified:
            items = [item for item in items if self._article_is_usable(item)]
        if law_name:
            term = law_name.casefold().strip()
            items = [item for item in items if term in item.law_name.casefold()]
        if article_no:
            term = article_no.casefold().strip()
            items = [item for item in items if term in item.article_no.casefold()]
        if legal_topic:
            items = [item for item in items if legal_topic in item.legal_topics]
        if contract_type:
            items = [
                item
                for item in items
                if not item.contract_types
                or "all" in item.contract_types
                or contract_type in item.contract_types
            ]
        if clause_type:
            items = [
                item
                for item in items
                if clause_type in item.legal_topics
                or clause_type in item.keywords
                or clause_type in (item.title or "")
            ]
        if effect_status:
            items = [item for item in items if item.effect_status == effect_status]
        if keyword:
            term = keyword.casefold().strip()
            items = [
                item
                for item in items
                if term
                in " ".join(
                    [
                        item.law_name,
                        item.article_no,
                        item.title or "",
                        item.content,
                        *item.keywords,
                        *item.legal_topics,
                    ]
                ).casefold()
            ]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)[:limit]

    def list_rules(
        self,
        *,
        enabled: bool | None = None,
        contract_type: str | None = None,
        clause_type: str | None = None,
    ) -> list[ContractRiskRuleRecord]:
        items = [self._enrich_rule(item) for item in self._list(self.rules)]
        if enabled is not None:
            items = [item for item in items if item.is_enabled is enabled]
        if contract_type:
            items = [
                item
                for item in items
                if "all" in item.contract_types or contract_type in item.contract_types
            ]
        if clause_type:
            items = [item for item in items if item.clause_type == clause_type]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def get_rule(self, rule_id: str) -> ContractRiskRuleRecord:
        item = next(
            (item for item in self._list(self.rules) if item.get("id") == rule_id),
            None,
        )
        if item is None:
            raise LegalKnowledgeError("风险规则不存在")
        return self._enrich_rule(item)

    def create_rule(
        self, payload: ContractRiskRuleCreate, actor_id: str
    ) -> ContractRiskRuleRecord:
        self._validate_article_ids(payload.legal_article_ids)
        with self._lock:
            rules = self._list(self.rules)
            if any(item.get("rule_code") == payload.rule_code for item in rules):
                raise LegalKnowledgeConflictError("规则编码已存在")
            now = self._now()
            record = {
                "id": f"legalrule_{uuid4().hex}",
                **payload.model_dump(mode="json"),
                "created_by": actor_id,
                "created_at": now,
                "updated_at": now,
            }
            rules.append(record)
            self.rules.write(rules)
            self._sync_structured_database()
        return self._enrich_rule(record)

    def update_rule(
        self, rule_id: str, payload: ContractRiskRuleUpdate, actor_id: str
    ) -> ContractRiskRuleRecord:
        current = self.get_rule(rule_id)
        merged = current.model_dump(
            exclude={"id", "created_by", "created_at", "updated_at"}
        )
        merged.update(payload.model_dump(exclude_unset=True))
        write = ContractRiskRuleWrite.model_validate(merged)
        self._validate_article_ids(write.legal_article_ids)
        with self._lock:
            rules = self._list(self.rules)
            index = next((i for i, item in enumerate(rules) if item.get("id") == rule_id), None)
            if index is None:
                raise LegalKnowledgeError("风险规则不存在")
            record = {
                "id": rule_id,
                **write.model_dump(mode="json"),
                "created_by": current.created_by,
                "created_at": current.created_at.isoformat(),
                "updated_at": self._now(),
            }
            rules[index] = record
            self.rules.write(rules)
            self._sync_structured_database()
        return self._enrich_rule(record)

    def standard_clauses(self) -> list[dict[str, str]]:
        return [
            {
                "rule_id": item.id,
                "rule_code": item.rule_code,
                "rule_name": item.rule_name,
                "contract_types": "、".join(item.contract_types),
                "clause_type": item.clause_type,
                "recommended_clause": item.recommended_clause,
            }
            for item in self.list_rules(enabled=True)
            if item.recommended_clause.strip()
        ]

    def seed_demo_data(self, actor_id: str) -> DemoSeedResponse:
        seed_path = Path(__file__).resolve().parents[1] / "knowledge" / "legal_demo_seed.json"
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        existing = next(
            (
                item
                for item in self.list_documents(include_disabled=True)
                if item.document_number == raw["document"]["document_number"]
            ),
            None,
        )
        if existing:
            return DemoSeedResponse(
                documents=0,
                articles=0,
                rules=0,
                message="演示占位数据已存在，未重复导入",
            )
        document = self.create_document(LegalDocumentCreate.model_validate(raw["document"]), actor_id)
        version = self.list_versions(document.id)[0]
        article_count = rule_count = 0
        for index, topic in enumerate(raw["topics"], start=1):
            article = self.create_article(
                LegalArticleCreate(
                    legal_document_id=document.id,
                    legal_document_version_id=version.id,
                    article_no=f"待核验-{index:02d}",
                    article_no_numeric=index,
                    title=f"{topic['topic']}主题占位",
                    content="待管理员从官方来源录入准确条文正文并完成核验。",
                    keywords=topic["keywords"],
                    legal_topics=[topic["topic"]],
                    contract_types=["all"],
                    is_effective=False,
                    verification_status=VerificationStatus.pending_verification,
                ),
                actor_id,
            )
            article_count += 1
            self.create_rule(
                ContractRiskRuleCreate(
                    rule_code=topic["code"],
                    rule_name=f"{topic['topic']}风险检查",
                    contract_types=["all"],
                    clause_type=topic["clause_type"],
                    risk_level=topic["risk_level"],
                    trigger_condition="合同文本包含任一配置关键词时触发验收演示规则",
                    keywords=topic["keywords"],
                    model_prompt="仅依据系统提供的已核验法律条文判断，不得补造法条。",
                    risk_description=topic["risk"],
                    possible_consequence="可能引发履约、结算或争议处理风险，需结合交易背景人工复核。",
                    modification_advice="补充明确、可执行、可验收且权责对等的约定。",
                    recommended_clause=f"请由法务结合实际交易条件完善{topic['topic']}条款。",
                    is_enabled=True,
                    legal_article_ids=[article.id],
                ),
                actor_id,
            )
            rule_count += 1
        return DemoSeedResponse(
            documents=1,
            articles=article_count,
            rules=rule_count,
            message="已导入待核验演示结构；占位条文不会用于正式审查引用",
        )

    def save_review_issue_links(
        self,
        *,
        review_id: str,
        issue_id: str,
        legal_article_ids: list[str],
        actor_id: str | None,
    ) -> list[dict[str, Any]]:
        valid_ids = [
            article_id
            for article_id in dict.fromkeys(legal_article_ids)
            if self._is_valid_article_id(article_id)
        ]
        with self._lock:
            links = self._list(self.review_links)
            existing = {
                (item.get("review_issue_id"), item.get("legal_article_id")) for item in links
            }
            now = self._now()
            additions = []
            for article_id in valid_ids:
                key = (issue_id, article_id)
                if key in existing:
                    continue
                item = {
                    "id": f"issuearticle_{uuid4().hex}",
                    "review_id": review_id,
                    "review_issue_id": issue_id,
                    "legal_article_id": article_id,
                    "created_by": actor_id,
                    "created_at": now,
                }
                links.append(item)
                additions.append(item)
            if additions:
                self.review_links.write(links)
                self._sync_structured_database()
        return additions

    def _sync_structured_database(self) -> None:
        """Write through to normalized legal tables when the configured database is active."""
        if not self.settings.database_enabled:
            return

        documents = [
            LegalDocumentRecord.model_validate(item) for item in self._list(self.documents)
        ]
        versions = [
            LegalDocumentVersionRecord.model_validate(item) for item in self._list(self.versions)
        ]
        articles = [self._enrich_article(item) for item in self._list(self.articles)]
        rules = [self._enrich_rule(item) for item in self._list(self.rules)]
        review_links = self._list(self.review_links)

        with get_session_factory()() as session:
            def upsert(model_type: type, record_id: str, values: dict[str, Any]) -> Any:
                item = session.get(model_type, record_id)
                if item is None:
                    item = model_type(id=record_id)
                    session.add(item)
                for key, value in values.items():
                    setattr(item, key, value)
                return item

            for document in documents:
                upsert(
                    LegalDocumentModel,
                    document.id,
                    {
                        "name": document.name,
                        "document_type": document.document_type,
                        "issuing_authority": document.issuing_authority,
                        "document_number": document.document_number,
                        "publication_date": document.publication_date,
                        "effective_date": document.effective_date,
                        "expiry_date": document.expiry_date,
                        "effect_status": document.effect_status.value,
                        "version_number": document.version_number,
                        "official_source_url": document.official_source_url,
                        "source_name": document.source_name,
                        "full_text": document.full_text,
                        "verification_status": document.verification_status.value,
                        "is_enabled": document.is_enabled,
                        "created_by": document.created_by,
                        "created_at": document.created_at,
                        "updated_at": document.updated_at,
                    },
                )

            for version in versions:
                upsert(
                    LegalDocumentVersionModel,
                    version.id,
                    {
                        "legal_document_id": version.legal_document_id,
                        "version_number": version.version_number,
                        "publication_date": version.publication_date,
                        "effective_date": version.effective_date,
                        "expiry_date": version.expiry_date,
                        "effect_status": version.effect_status.value,
                        "official_source_url": version.official_source_url,
                        "source_name": version.source_name,
                        "full_text": version.full_text,
                        "verification_status": version.verification_status.value,
                        "change_summary": version.change_summary,
                        "created_by": version.created_by,
                        "created_at": version.created_at,
                    },
                )

            for article in articles:
                upsert(
                    LegalArticleModel,
                    article.id,
                    {
                        "legal_document_id": article.legal_document_id,
                        "legal_document_version_id": article.legal_document_version_id,
                        "chapter_no": article.chapter_no,
                        "chapter_name": article.chapter_name,
                        "article_no": article.article_no,
                        "article_no_numeric": article.article_no_numeric,
                        "title": article.title,
                        "content": article.content,
                        "keywords": article.keywords,
                        "legal_topics": article.legal_topics,
                        "contract_types": article.contract_types,
                        "is_effective": article.is_effective,
                        "verification_status": article.verification_status.value,
                        "created_by": article.created_by,
                        "created_at": article.created_at,
                        "updated_at": article.updated_at,
                    },
                )

            for rule in rules:
                upsert(
                    ContractRiskRuleModel,
                    rule.id,
                    {
                        "rule_code": rule.rule_code,
                        "rule_name": rule.rule_name,
                        "contract_types": rule.contract_types,
                        "clause_type": rule.clause_type,
                        "risk_level": rule.risk_level,
                        "trigger_condition": rule.trigger_condition,
                        "keywords": rule.keywords,
                        "model_prompt": rule.model_prompt,
                        "risk_description": rule.risk_description,
                        "possible_consequence": rule.possible_consequence,
                        "modification_advice": rule.modification_advice,
                        "recommended_clause": rule.recommended_clause,
                        "is_enabled": rule.is_enabled,
                        "created_by": rule.created_by,
                        "created_at": rule.created_at,
                        "updated_at": rule.updated_at,
                    },
                )

                current_links = session.scalars(
                    select(RiskRuleLegalArticleModel).where(
                        RiskRuleLegalArticleModel.risk_rule_id == rule.id
                    )
                ).all()
                desired_ids = set(rule.legal_article_ids)
                for link in current_links:
                    if link.legal_article_id not in desired_ids:
                        session.delete(link)
                existing_ids = {link.legal_article_id for link in current_links}
                for article_id in desired_ids - existing_ids:
                    session.add(
                        RiskRuleLegalArticleModel(
                            risk_rule_id=rule.id,
                            legal_article_id=article_id,
                            created_by=rule.created_by,
                        )
                    )

            session.flush()
            for raw in review_links:
                issue_id = str(raw.get("review_issue_id") or "")
                article_id = str(raw.get("legal_article_id") or "")
                if not issue_id or not article_id:
                    continue
                if session.get(RiskFindingModel, issue_id) is None:
                    continue
                existing = session.scalar(
                    select(ReviewIssueLegalArticleModel).where(
                        ReviewIssueLegalArticleModel.review_issue_id == issue_id,
                        ReviewIssueLegalArticleModel.legal_article_id == article_id,
                    )
                )
                if existing is None:
                    session.add(
                        ReviewIssueLegalArticleModel(
                            id=str(raw.get("id") or f"issuearticle_{uuid4().hex}"),
                            review_id=str(raw.get("review_id") or ""),
                            review_issue_id=issue_id,
                            legal_article_id=article_id,
                            created_by=raw.get("created_by"),
                            created_at=datetime.fromisoformat(str(raw["created_at"])),
                        )
                    )
            session.commit()

    def _build_version(
        self,
        document_id: str,
        payload: LegalDocumentWrite,
        actor_id: str,
        change_summary: str,
        now: str,
    ) -> dict[str, Any]:
        return {
            "id": f"lawver_{uuid4().hex}",
            "legal_document_id": document_id,
            "version_number": payload.version_number,
            "publication_date": payload.publication_date.isoformat()
            if payload.publication_date
            else None,
            "effective_date": payload.effective_date.isoformat() if payload.effective_date else None,
            "expiry_date": payload.expiry_date.isoformat() if payload.expiry_date else None,
            "effect_status": payload.effect_status.value,
            "official_source_url": (
                str(payload.official_source_url) if payload.official_source_url else None
            ),
            "source_name": payload.source_name,
            "full_text": payload.full_text,
            "verification_status": payload.verification_status.value,
            "change_summary": change_summary,
            "created_by": actor_id,
            "created_at": now,
        }

    def _enrich_article(self, raw: dict[str, Any]) -> LegalArticleRecord:
        document = self.get_document(str(raw["legal_document_id"]))
        version = self.get_version(str(raw["legal_document_version_id"]))
        return LegalArticleRecord.model_validate(
            {
                **raw,
                "law_name": document.name,
                "law_version": version.version_number,
                "effect_status": version.effect_status,
                "source_name": version.source_name,
                "source_url": version.official_source_url,
            }
        )

    def _enrich_rule(self, raw: dict[str, Any]) -> ContractRiskRuleRecord:
        return ContractRiskRuleRecord.model_validate(raw)

    def _validate_article_ids(self, article_ids: list[str]) -> None:
        known = {item.get("id") for item in self._list(self.articles)}
        missing = [article_id for article_id in dict.fromkeys(article_ids) if article_id not in known]
        if missing:
            raise LegalKnowledgeError(f"关联法条不存在：{', '.join(missing)}")

    def _is_valid_article_id(self, article_id: str) -> bool:
        try:
            return self._article_is_usable(self.get_article(article_id, public_only=False))
        except LegalKnowledgeError:
            return False

    def _document_is_usable(self, item: LegalDocumentRecord) -> bool:
        today = date.today()
        return (
            item.is_enabled
            and item.verification_status == VerificationStatus.verified
            and item.effect_status == LegalEffectStatus.effective
            and (item.effective_date is None or item.effective_date <= today)
            and (item.expiry_date is None or item.expiry_date >= today)
        )

    def _article_is_usable(self, item: LegalArticleRecord) -> bool:
        try:
            document = self.get_document(item.legal_document_id)
        except LegalKnowledgeError:
            return False
        return (
            item.is_effective
            and item.verification_status == VerificationStatus.verified
            and item.effect_status == LegalEffectStatus.effective
            and self._document_is_usable(document)
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class LegalKnowledgeRetriever:
    """Stable retrieval interface; a vector implementation can replace this class later."""

    def __init__(self, settings: Settings) -> None:
        self.service = LegalKnowledgeService(settings)

    def searchByKeywords(self, keywords: list[str], limit: int = 8) -> list[LegalArticleRecord]:
        return self._rank(keywords=keywords, limit=limit)

    def searchByContractType(
        self, contract_type: str, limit: int = 8
    ) -> list[LegalArticleRecord]:
        return self.service.search_articles(contract_type=contract_type, limit=limit)

    def searchByClauseType(self, clause_type: str, limit: int = 8) -> list[LegalArticleRecord]:
        return self.service.search_articles(clause_type=clause_type, limit=limit)

    def searchRelevantArticles(
        self,
        *,
        contract_type: str,
        clause_type: str | None,
        legal_topics: list[str],
        keywords: list[str],
        limit: int = 8,
    ) -> list[LegalArticleRecord]:
        candidates = self.service.search_articles(contract_type=contract_type, limit=200)
        tokens = self._tokens([clause_type or "", *legal_topics, *keywords])
        scored: list[tuple[int, LegalArticleRecord]] = []
        for item in candidates:
            haystack = " ".join(
                [
                    item.law_name,
                    item.article_no,
                    item.title or "",
                    item.content,
                    *item.keywords,
                    *item.legal_topics,
                ]
            ).casefold()
            score = sum(1 for token in tokens if token.casefold() in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1].updated_at), reverse=True)
        return [item for _, item in scored[:limit]]

    def retrieve_for_review(
        self,
        *,
        contract_text: str,
        contract_type: str,
        findings: list[dict[str, Any]],
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        tokens = self._tokens(
            [
                contract_text[:6000],
                *[
                    " ".join(
                        str(item.get(key, ""))
                        for key in ("风险类别", "风险标题", "问题说明", "相关条款")
                    )
                    for item in findings
                ],
            ]
        )
        articles = self.searchRelevantArticles(
            contract_type=contract_type,
            clause_type=None,
            legal_topics=[],
            keywords=tokens,
            limit=limit,
        )
        return [self.article_to_candidate(item) for item in articles]

    def match_risk_rules(self, contract_text: str, contract_type: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        level_cn = {"low": "低", "medium": "中", "high": "高", "critical": "严重"}
        for rule in self.service.list_rules(enabled=True, contract_type=contract_type):
            matched_keyword = next(
                (keyword for keyword in rule.keywords if keyword and keyword in contract_text),
                None,
            )
            if not matched_keyword:
                continue
            start = contract_text.find(matched_keyword)
            clause = contract_text[max(0, start - 50) : min(len(contract_text), start + 150)]
            bases = []
            for article_id in rule.legal_article_ids:
                try:
                    article = self.service.get_article(article_id, public_only=True)
                except LegalKnowledgeError:
                    continue
                bases.append(self.article_to_reference(article).model_dump())
            evidence = (
                "；".join(f"《{item['lawName']}》{item['articleNo']}" for item in bases)
                if bases
                else "未匹配到已核验法律依据"
            )
            findings.append(
                {
                    "hasRisk": True,
                    "riskLevel": rule.risk_level,
                    "riskName": rule.rule_name,
                    "originalClause": clause,
                    "riskDescription": rule.risk_description,
                    "possibleConsequence": rule.possible_consequence,
                    "legalBasis": bases,
                    "modificationAdvice": rule.modification_advice,
                    "recommendedClause": rule.recommended_clause,
                    "confidence": 0.9,
                    "风险类别": rule.clause_type,
                    "风险等级": level_cn[rule.risk_level],
                    "短标题": rule.rule_name[:10],
                    "风险标题": rule.rule_name,
                    "相关条款": clause,
                    "问题说明": rule.risk_description,
                    "可能后果": rule.possible_consequence,
                    "审查依据": evidence,
                    "修改方向": rule.modification_advice,
                    "推荐条款": rule.recommended_clause,
                    "来源": "自建法律知识库规则",
                    "rule_id": rule.id,
                    "legal_basis": bases,
                    "knowledge_document_ids": [item["legalArticleId"] for item in bases],
                    "requires_human_review": True,
                }
            )
        return findings

    def validate_legal_basis(
        self,
        raw_basis: object,
        *,
        allowed_article_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_basis, list):
            return []
        validated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_basis:
            if not isinstance(item, dict):
                continue
            article_id = str(
                item.get("legalArticleId") or item.get("legal_article_id") or ""
            ).strip()
            if not article_id or article_id in seen:
                continue
            if allowed_article_ids is not None and article_id not in allowed_article_ids:
                continue
            try:
                article = self.service.get_article(article_id, public_only=True)
            except LegalKnowledgeError:
                continue
            validated.append(self.article_to_reference(article).model_dump())
            seen.add(article_id)
        return validated

    def article_to_candidate(self, item: LegalArticleRecord) -> dict[str, Any]:
        return {
            **self.article_to_reference(item).model_dump(),
            "content": item.content,
            "legalTopics": item.legal_topics,
            "contractTypes": item.contract_types,
            "verificationStatus": item.verification_status.value,
            "effectStatus": item.effect_status.value,
        }

    def article_to_reference(self, item: LegalArticleRecord) -> LegalBasisReference:
        summary = re.sub(r"\s+", " ", item.content).strip()
        return LegalBasisReference(
            legalArticleId=item.id,
            lawName=item.law_name,
            articleNo=item.article_no,
            sourceUrl=item.source_url,
            contentSummary=summary[:220],
            sourceName=item.source_name,
            version=item.law_version,
        )

    def _rank(self, *, keywords: list[str], limit: int) -> list[LegalArticleRecord]:
        tokens = self._tokens(keywords)
        candidates = self.service.search_articles(limit=500)
        scored: list[tuple[int, LegalArticleRecord]] = []
        for item in candidates:
            haystack = " ".join(
                [item.law_name, item.article_no, item.title or "", item.content, *item.keywords]
            ).casefold()
            score = sum(1 for token in tokens if token.casefold() in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1].updated_at), reverse=True)
        return [item for _, item in scored[:limit]]

    def _tokens(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            for token in re.split(r"[\s,，。；;、:：()（）\[\]【】]+", value):
                token = token.strip()
                if 2 <= len(token) <= 20 and token not in result:
                    result.append(token)
        return result[:160]
