from uuid import uuid4


def generate_review_id() -> str:
    return f"review_{uuid4().hex}"
