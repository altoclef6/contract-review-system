from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractParty(BaseModel):
    model_config = ConfigDict(title="合同主体")

    name: str = Field(title="主体名称", description="合同主体名称，例如甲方公司名称或乙方公司名称。")
    role: str | None = Field(
        default=None,
        title="主体角色",
        description="合同主体角色，例如甲方、乙方、买方、卖方、服务方。",
    )
    identifier: str | None = Field(
        default=None,
        title="主体证照编号",
        description="统一社会信用代码、营业执照号或身份证号。",
    )


class ContractAmount(BaseModel):
    model_config = ConfigDict(title="合同金额")

    value: float | None = Field(default=None, title="金额数值", description="金额的数字化结果。")
    currency: str | None = Field(default="CNY", title="币种", description="币种，默认人民币。")
    original_text: str = Field(title="金额原文", description="合同原文中的金额表达。")


class ExtractedContractFields(BaseModel):
    model_config = ConfigDict(title="合同关键要素")

    parties: list[ContractParty] = Field(default_factory=list, title="合同主体列表")
    amounts: list[ContractAmount] = Field(default_factory=list, title="合同金额列表")
    liability_clauses: list[str] = Field(default_factory=list, title="违约责任条款")
    performance_periods: list[str] = Field(default_factory=list, title="履行期限条款")


class RiskFinding(BaseModel):
    model_config = ConfigDict(title="合规风险点")

    id: str = Field(title="风险编号", description="风险点的唯一编号。")
    category: str = Field(title="风险类别", description="例如主体资格、付款条款、违约责任、争议解决。")
    level: Literal["低", "中", "高", "严重"] = Field(title="风险等级")
    clause_text: str = Field(title="相关条款", description="触发风险判断的合同条款原文。")
    reason: str = Field(title="判断理由", description="说明为什么该条款存在风险。")
    evidence: str | None = Field(default=None, title="依据", description="法律法规或企业内控依据。")


class RevisionSuggestion(BaseModel):
    model_config = ConfigDict(title="修改建议")

    finding_id: str = Field(title="对应风险编号", description="该建议对应的风险点编号。")
    suggestion: str = Field(title="修改建议", description="针对风险点给出的处理建议。")
    revised_clause: str | None = Field(default=None, title="建议条款", description="建议替换后的条款文本。")
