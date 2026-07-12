from contract_review.core.config import Settings
from contract_review.services.review_service import ReviewService


def test_risk_clause_gets_exact_text_location(tmp_path) -> None:
    service = ReviewService(graph=None, settings=Settings(report_dir=tmp_path))
    text = "第一条 交付。\n第二条 任一方逾期付款，应按每日万分之五支付违约金。\n第三条 验收。"
    findings = [
        {
            "风险编号": "R001",
            "风险类别": "违约责任",
            "相关条款": "任一方逾期付款，应按每日万分之五支付违约金",
        }
    ]

    located = service._attach_text_locations(findings, text)
    location = located[0]["原文定位"]

    assert location["定位状态"] == "精确定位"
    assert text[location["字符起点"] : location["字符终点"]] == location["定位文本"]


def test_missing_clause_is_marked_without_fake_position(tmp_path) -> None:
    service = ReviewService(graph=None, settings=Settings(report_dir=tmp_path))
    located = service._attach_text_locations(
        [
            {
                "风险编号": "R002",
                "风险类别": "争议解决",
                "相关条款": "未在合同文本中识别到明确条款",
            }
        ],
        "本合同仅约定产品名称和数量。",
    )

    assert located[0]["原文定位"]["定位状态"] == "缺失条款"
    assert located[0]["原文定位"]["字符起点"] is None
