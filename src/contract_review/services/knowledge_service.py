from __future__ import annotations

from pathlib import Path
from typing import Any

KEYWORD_MAP = {
    "主体": ["主体", "甲方", "乙方", "授权", "签约"],
    "金额": ["金额", "价款", "付款", "支付", "结算", "发票"],
    "期限": ["期限", "履行", "交付", "验收", "延期"],
    "违约": ["违约", "赔偿", "损失", "违约金", "责任"],
    "争议": ["争议", "诉讼", "仲裁", "法院", "管辖"],
    "保密": ["保密", "商业秘密", "数据", "泄露"],
    "终止": ["解除", "终止", "不可抗力", "退出"],
}


class KnowledgeService:
    def __init__(self, knowledge_dir: Path | None = None) -> None:
        self.knowledge_dir = knowledge_dir or Path(__file__).resolve().parents[1] / "knowledge"

    def retrieve(self, findings: list[dict[str, Any]], limit: int = 6) -> list[dict[str, str]]:
        keywords = self._collect_keywords(findings)
        snippets: list[dict[str, str]] = []
        for file_path in sorted(self.knowledge_dir.glob("*.md")):
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for paragraph in self._paragraphs(text):
                score = sum(1 for keyword in keywords if keyword in paragraph)
                if score <= 0:
                    continue
                snippets.append(
                    {
                        "来源": file_path.name,
                        "匹配分": str(score),
                        "内容": paragraph[:280],
                    }
                )
        snippets.sort(key=lambda item: int(item["匹配分"]), reverse=True)
        return snippets[:limit]

    def _collect_keywords(self, findings: list[dict[str, Any]]) -> set[str]:
        keywords: set[str] = set()
        for finding in findings:
            source = " ".join(
                str(finding.get(key, "")) for key in ("风险类别", "风险标题", "问题说明")
            )
            for group, words in KEYWORD_MAP.items():
                if group in source or any(word in source for word in words):
                    keywords.update(words)
        return keywords or {"合同", "风险", "条款"}

    def _paragraphs(self, text: str) -> list[str]:
        parts = [part.strip() for part in text.split("\n\n")]
        return [part.replace("\n", " ") for part in parts if len(part.strip()) >= 20]
