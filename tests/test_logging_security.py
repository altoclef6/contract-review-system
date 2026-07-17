from __future__ import annotations

import logging

from contract_review.core.logging import SecurityContextFilter, redact_log_message


def test_log_redaction_masks_common_credentials() -> None:
    message = "Authorization=Bearer abc.def.ghi password=hunter2 api_key=sk-example"
    redacted = redact_log_message(message)
    assert "abc.def.ghi" not in redacted
    assert "hunter2" not in redacted
    assert "sk-example" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_security_context_filter_clears_format_arguments() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=%s",
        args=("sensitive-value",),
        exc_info=None,
    )
    assert SecurityContextFilter().filter(record)
    assert record.getMessage() == "token=[REDACTED]"
    assert record.request_id == "-"
