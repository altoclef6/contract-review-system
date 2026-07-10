from __future__ import annotations

import asyncio
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
        final_report = result.get("final_report")
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
                self.settings.jwt_secret_key.get_secret_value(),
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
                ),
            )

        return ReviewResponse(
            review_id=review_id,
            file_name=original_file_name,
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
