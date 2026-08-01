from datetime import datetime, timezone
from uuid import uuid4


def generate_review_id() -> str:
    date_part = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")
    return f"CR-{date_part}-{uuid4().hex[:8].upper()}"
