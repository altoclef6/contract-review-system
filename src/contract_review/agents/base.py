from contract_review.graph.state import ContractReviewState


def append_error(state: ContractReviewState, message: str) -> dict[str, list[str]]:
    return {"errors": [*state.get("errors", []), message]}
