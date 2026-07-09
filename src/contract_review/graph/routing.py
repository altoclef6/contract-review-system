from typing import Literal

from contract_review.graph.state import ContractReviewState


def route_after_coordinator(state: ContractReviewState) -> Literal["extractor", "finish"]:
    if state.get("next_step") == "finish" or state.get("final_report"):
        return "finish"
    return "extractor"
