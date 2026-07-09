from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewResponse(BaseModel):
    model_config = ConfigDict(
        title="合同审查响应",
        json_schema_extra={
            "example": {
                "review_id": "review_123456",
                "file_name": "采购合同.docx",
                "status": "已完成",
                "extracted_fields": {
                    "合同主体": [{"角色": "甲方", "名称": "北京示例科技有限公司"}],
                    "合同金额": [{"金额原文": "人民币100000元", "币种": "人民币"}],
                    "履行期限": ["2026年8月1日至2026年12月31日"],
                    "付款条款": [],
                    "违约责任条款": [],
                    "争议解决条款": [],
                    "原文长度": 1024,
                },
                "risk_findings": [
                    {
                        "风险编号": "R001",
                        "风险类别": "违约责任",
                        "风险等级": "高",
                        "风险标题": "缺少明确违约责任",
                        "问题说明": "合同未明确违约行为、违约金或损失赔偿范围。",
                    }
                ],
                "revision_suggestions": [
                    {
                        "对应风险编号": "R001",
                        "风险类别": "违约责任",
                        "修改建议": "明确违约金计算标准和损失赔偿范围。",
                    }
                ],
                "final_report": {
                    "总体风险等级": "高风险",
                    "审查摘要": "本次审查共识别 1 个风险点，整体评估为高风险。",
                },
                "report_path": "data/reports/review_123456.json",
                "agent_trace": [
                    {
                        "节点": "协调者 Agent",
                        "动作": "接收合同并启动审查流程",
                        "输出": "已路由至提取者 Agent",
                        "状态": "完成",
                    }
                ],
                "errors": [],
            }
        },
    )

    review_id: str = Field(title="审查任务编号", description="系统生成的唯一审查任务编号。")
    file_name: str = Field(title="合同文件名", description="用户上传的原始合同文件名。")
    status: Literal["已完成", "失败"] = Field(title="任务状态", description="合同审查任务的处理状态。")
    extracted_fields: dict[str, Any] = Field(
        default_factory=dict,
        title="结构化提取结果",
        description="从合同中提取的主体、金额、违约责任、履行期限等关键要素。",
    )
    risk_findings: list[dict[str, Any]] = Field(
        default_factory=list,
        title="合规风险点",
        description="合规审查 Agent 识别出的潜在风险点列表。",
    )
    revision_suggestions: list[dict[str, Any]] = Field(
        default_factory=list,
        title="修改建议",
        description="反馈与修改 Agent 针对风险点生成的条款修改建议。",
    )
    final_report: dict[str, Any] | None = Field(
        default=None,
        title="最终审查报告",
        description="协调者 Agent 汇总所有节点结果后形成的最终审查报告。",
    )
    report_path: str | None = Field(
        default=None,
        title="报告文件路径",
        description="系统保存的 JSON 审查报告路径。",
    )
    export_paths: dict[str, str] = Field(
        default_factory=dict,
        title="导出文件路径",
        description="系统生成的 JSON、Word、PDF 报告路径。",
    )
    agent_trace: list[dict[str, Any]] = Field(
        default_factory=list,
        title="Agent 协同轨迹",
        description="LangGraph 编排下各 Agent 节点的处理动作和输出摘要。",
    )
    errors: list[str] = Field(
        default_factory=list,
        title="错误信息",
        description="处理过程中产生的错误信息；为空表示未发现系统处理错误。",
    )
