from __future__ import annotations

import asyncio
import re
from pathlib import Path
from time import perf_counter
from typing import Any

from contract_review.core.config import Settings
from contract_review.schemas.review import ReviewResponse
from contract_review.services.document_loader import DocumentLoader
from contract_review.services.history_service import HistoryService, build_history_item
from contract_review.services.model_config_service import ModelConfigService
from contract_review.services.prompt_template_service import PromptTemplateService
from contract_review.services.report_service import ReportService
from contract_review.utils.id_generator import generate_review_id


class ReviewService:
    def __init__(self, graph: Any, settings: Settings) -> None:
        self.graph = graph
        self.settings = settings
        self.document_loader = DocumentLoader(settings)
        self.report_service = ReportService(settings.report_dir)
        self.history_service = HistoryService(settings.report_dir.parent)

    async def review_file(
        self,
        file_path: Path,
        original_file_name: str,
        content_type: str | None,
        llm_config: dict[str, Any] | None = None,
        contract_type: str = "general",
    ) -> ReviewResponse:
        review_id = generate_review_id()
        started_at = perf_counter()
        raw_text = await asyncio.to_thread(self.document_loader.load_text, file_path)
        prompt_templates = PromptTemplateService(self.settings.prompt_template_data_dir).resolve(
            contract_type
        )
        initial_state = {
            "review_id": review_id,
            "file_path": str(file_path),
            "file_name": original_file_name,
            "file_type": content_type,
            "raw_text": raw_text,
            "llm_config": llm_config or {},
            "contract_type": contract_type,
            "prompt_templates": prompt_templates,
            "errors": [],
        }
        result = await self.graph.ainvoke(initial_state)
        located_findings = self._attach_text_locations(
            result.get("compliance_findings", []), raw_text
        )
        result["compliance_findings"] = located_findings
        final_report = result.get("final_report")
        if final_report is not None:
            final_report["风险点"] = located_findings
        export_paths: dict[str, str] = {}
        if final_report:
            generated = await asyncio.to_thread(
                self.report_service.save_all_reports,
                review_id,
                final_report,
            )
            export_paths = {key: str(path) for key, path in generated.items()}
            active_model = ModelConfigService(
                self.settings.model_config_data_dir,
                self.settings.resolve_model_credential_encryption_key(),
            ).get_active()
            await asyncio.to_thread(
                self.history_service.append,
                build_history_item(
                    review_id=review_id,
                    file_name=original_file_name,
                    final_report=final_report,
                    report_path=export_paths.get("json"),
                    exports=export_paths,
                    contract_type=contract_type,
                    duration_ms=round((perf_counter() - started_at) * 1000),
                    model_provider=active_model.provider.value if active_model else None,
                    model_name=active_model.model_name if active_model else None,
                    prompt_snapshot=prompt_templates,
                    source_file_path=str(file_path),
                ),
            )

        return ReviewResponse(
            review_id=review_id,
            file_name=original_file_name,
            contract_text=raw_text,
            status="已完成",
            extracted_fields=result.get("extracted_fields", {}),
            risk_findings=result.get("compliance_findings", []),
            revision_suggestions=result.get("revision_suggestions", []),
            final_report=final_report,
            report_path=export_paths.get("json"),
            export_paths=export_paths,
            agent_trace=result.get("agent_trace", []),
            errors=result.get("errors", []),
        )

    def _attach_text_locations(
        self,
        findings: list[dict[str, Any]],
        contract_text: str,
    ) -> list[dict[str, Any]]:
        keyword_map = {
            "主体信息": ("甲方", "乙方", "买方", "卖方"),
            "交易金额": ("合同金额", "价款", "人民币"),
            "履行期限": ("履行期限", "合同期限", "交付期限"),
            "付款结算": ("付款", "支付", "结算"),
            "违约责任": ("违约", "赔偿", "违约金"),
            "争议解决": ("争议", "仲裁", "管辖"),
            "保密义务": ("保密", "商业秘密"),
            "解除终止": ("解除", "终止", "不可抗力"),
        }
        located: list[dict[str, Any]] = []
        for finding in findings:
            item = dict(finding)
            clause = str(item.get("相关条款") or "").strip()
            match = self._find_clause(contract_text, clause)
            exact = match is not None
            if match is None:
                for keyword in keyword_map.get(str(item.get("风险类别")), ()):
                    match = self._find_keyword_context(contract_text, keyword)
                    if match is not None:
                        break
            if match is None:
                item["原文定位"] = {
                    "定位状态": "缺失条款",
                    "字符起点": None,
                    "字符终点": None,
                    "定位文本": "",
                }
            else:
                start, end = match
                item["原文定位"] = {
                    "定位状态": "精确定位" if exact else "相关上下文",
                    "字符起点": start,
                    "字符终点": end,
                    "定位文本": contract_text[start:end],
                }
            located.append(item)
        return located

    def _find_clause(self, text: str, clause: str) -> tuple[int, int] | None:
        if not clause or clause.startswith("未在合同文本中"):
            return None
        candidates = [clause]
        candidates.extend(
            segment.strip()
            for segment in re.split(r"[。；;\n]", clause)
            if len(segment.strip()) >= 8
        )
        for candidate in sorted(set(candidates), key=len, reverse=True):
            start = text.find(candidate)
            if start >= 0:
                return start, start + len(candidate)
        return None

    def _find_keyword_context(self, text: str, keyword: str) -> tuple[int, int] | None:
        position = text.find(keyword)
        if position < 0:
            return None
        start = (
            max(
                text.rfind("\n", 0, position),
                text.rfind("。", 0, position),
                text.rfind("；", 0, position),
            )
            + 1
        )
        endings = [
            value
            for value in (text.find(mark, position) for mark in ("\n", "。", "；"))
            if value >= 0
        ]
        end = min(endings) + 1 if endings else min(len(text), position + 160)
        return start, end
