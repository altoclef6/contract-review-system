from datetime import datetime, timedelta, timezone
from pathlib import Path

from contract_review.core.config import get_settings
from contract_review.schemas.contract_management import ContractCreate
from contract_review.services.contract_service import ContractService
from contract_review.services.notification_service import NotificationService
from contract_review.tasks.jobs import send_expiration_reminders


def test_expiration_reminder_is_sent_once_per_day(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_DATA_DIR", str(tmp_path / "contracts"))
    monkeypatch.setenv("NOTIFICATION_DATA_DIR", str(tmp_path / "notifications"))
    monkeypatch.setenv("DATABASE_ENABLED", "false")
    get_settings.cache_clear()
    settings = get_settings()
    contract = ContractService(settings.contract_data_dir).create_contract(
        payload=ContractCreate(
            title="即将到期的采购合同",
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        ),
        actor_id="user_employee",
    )
    assert contract.expires_at is not None
    assert send_expiration_reminders(30) == {"sent": 1}
    assert send_expiration_reminders(30) == {"sent": 0}
    notices = NotificationService(settings.notification_data_dir).list_for_user("user_employee")
    assert len(notices) == 1
    assert notices[0].payload["contract_id"] == contract.id
