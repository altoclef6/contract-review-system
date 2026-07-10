from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from contract_review.graph.state import ContractReviewState
from contract_review.llm.json_client import call_llm_json


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ：:;；,.，。")


def _deduplicate_dicts(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        value = str(item.get(key, "")).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def _deduplicate_text(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        cleaned = _clean_text(item)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _extract_parties(text: str) -> list[dict[str, str]]:
    parties: list[dict[str, str]] = []
    patterns = [
        ("甲方", r"甲方[（(]?.*?[）)]?[：:]\s*([^\n\r。；;]{2,80})"),
        ("乙方", r"乙方[（(]?.*?[）)]?[：:]\s*([^\n\r。；;]{2,80})"),
        ("买方", r"买方[（(]?.*?[）)]?[：:]\s*([^\n\r。；;]{2,80})"),
        ("卖方", r"卖方[（(]?.*?[）)]?[：:]\s*([^\n\r。；;]{2,80})"),
        ("委托方", r"委托方[（(]?.*?[）)]?[：:]\s*([^\n\r。；;]{2,80})"),
        ("受托方", r"受托方[（(]?.*?[）)]?[：:]\s*([^\n\r。；;]{2,80})"),
    ]
    for role, pattern in patterns:
        for match in re.finditer(pattern, text):
            parties.append({"角色": role, "名称": _clean_text(match.group(1))})
    return _deduplicate_dicts(parties, "名称")


def _extract_amounts(text: str) -> list[dict[str, str]]:
    amount_patterns = [
        r"(人民币\s*[壹贰叁肆伍陆柒捌玖拾佰仟万亿零整元角分]+)",
        r"(人民币\s*[0-9,]+(?:\.\d+)?\s*元)",
        r"([0-9,]+(?:\.\d+)?\s*万元)",
        r"([0-9,]+(?:\.\d+)?\s*元)",
    ]
    amounts: list[dict[str, str]] = []
    for pattern in amount_patterns:
        for match in re.finditer(pattern, text):
            amounts.append({"金额原文": _clean_text(match.group(1)), "币种": "人民币"})

    result: list[dict[str, str]] = []
    for item in sorted(
        _deduplicate_dicts(amounts, "金额原文"), key=lambda row: len(row["金额原文"]), reverse=True
    ):
        if any(item["金额原文"] in existing["金额原文"] for existing in result):
            continue
        result.append(item)
    return result


def _extract_periods(text: str) -> list[str]:
    patterns = [
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*(?:至|到|-|—)\s*\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日",
        r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\s*(?:至|到|-|—)\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}",
        r"履行期限[：:][^\n\r。；;]{2,120}",
        r"合同期限[：:][^\n\r。；;]{2,120}",
    ]
    periods: list[str] = []
    for pattern in patterns:
        periods.extend(match.group(0) for match in re.finditer(pattern, text))

    result: list[str] = []
    for period in sorted(_deduplicate_text(periods), key=len, reverse=True):
        if any(period in existing for existing in result):
            continue
        result.append(period)
    return result


def _extract_clauses(text: str, keywords: tuple[str, ...], limit: int = 8) -> list[str]:
    clauses: list[str] = []
    for sentence in re.split(r"[。；;\n\r]", text):
        cleaned = _clean_text(sentence)
        if 8 <= len(cleaned) <= 240 and any(keyword in cleaned for keyword in keywords):
            clauses.append(cleaned)
    return _deduplicate_text(clauses)[:limit]


def _rule_extract(text: str) -> dict[str, Any]:
    return {
        "合同主体": _extract_parties(text),
        "合同金额": _extract_amounts(text),
        "履行期限": _extract_periods(text),
        "付款条款": _extract_clauses(text, ("付款", "支付", "结算", "发票", "价款")),
        "违约责任条款": _extract_clauses(text, ("违约", "赔偿", "责任", "损失", "滞纳金")),
        "争议解决条款": _extract_clauses(text, ("争议", "仲裁", "诉讼", "法院", "管辖")),
        "保密条款": _extract_clauses(text, ("保密", "商业秘密", "泄密", "机密")),
        "解除终止条款": _extract_clauses(text, ("解除", "终止", "不可抗力")),
        "原文长度": len(text),
        "提取方式": "规则提取",
    }


def _merge_extraction(
    rule_result: dict[str, Any], llm_result: dict[str, Any] | None
) -> dict[str, Any]:
    if not llm_result:
        return rule_result

    merged = dict(rule_result)
    data = (
        llm_result.get("结构化要素")
        if isinstance(llm_result.get("结构化要素"), dict)
        else llm_result
    )
    for key in (
        "合同主体",
        "合同金额",
        "履行期限",
        "付款条款",
        "违约责任条款",
        "争议解决条款",
        "保密条款",
        "解除终止条款",
    ):
        value = data.get(key) if isinstance(data, dict) else None
        if value:
            merged[key] = value
    merged["AI提取说明"] = llm_result.get("提取说明", "已使用外部大模型增强提取。")
    merged["提取方式"] = "规则提取 + AI增强"
    return merged


async def extractor_node(state: ContractReviewState) -> dict:
    text = state.get("raw_text", "")
    llm_config = state.get("llm_config")
    rule_result = _rule_extract(text)

    llm_result = await call_llm_json(
        state.get("prompt_templates", {}).get(
            "extraction", "你是企业合同结构化信息提取专家。请只输出 JSON，不要输出 Markdown。"
        ),
        f"""
请从以下合同文本中提取结构化要素。输出 JSON 格式：
{{
  "结构化要素": {{
    "合同主体": [{{"角色": "甲方/乙方/其他", "名称": "主体名称", "证照编号": ""}}],
    "合同金额": [{{"金额原文": "", "币种": "人民币", "说明": ""}}],
    "履行期限": [],
    "付款条款": [],
    "违约责任条款": [],
    "争议解决条款": [],
    "保密条款": [],
    "解除终止条款": []
  }},
  "提取说明": "一句话说明"
}}

合同文本：
{text}
""",
        llm_config=llm_config,
    )
    extracted = _merge_extraction(rule_result, llm_result if isinstance(llm_result, dict) else None)
    trace = state.get("agent_trace", []) + [
        {
            "节点": "提取者 Agent",
            "动作": "解析合同文本并抽取主体、金额、期限、付款和关键条款",
            "输出": f"识别主体 {len(extracted.get('合同主体', []))} 个，金额 {len(extracted.get('合同金额', []))} 项",
            "状态": "完成",
            "时间": datetime.now(timezone.utc).isoformat(),
        }
    ]
    return {"extracted_fields": extracted, "agent_trace": trace}
