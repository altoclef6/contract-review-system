from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from contract_review.core.exceptions import UploadTooLargeError


def sanitize_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return normalized or "contract"


async def save_upload_file(file: UploadFile, upload_dir: Path, max_size_mb: int) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_filename = file.filename or "contract"
    suffix = Path(original_filename).suffix.lower()
    original_name = sanitize_filename(original_filename)
    saved_path = upload_dir / f"{uuid4().hex}{suffix}"
    max_bytes = max_size_mb * 1024 * 1024
    total_bytes = 0

    with saved_path.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                saved_path.unlink(missing_ok=True)
                raise UploadTooLargeError(f"Upload exceeds {max_size_mb} MB limit")
            buffer.write(chunk)

    await file.close()
    return saved_path
