from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from contract_review.core.exceptions import (
    UnsafeUploadError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
)

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def sanitize_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return normalized or "contract"


async def save_upload_file(file: UploadFile, upload_dir: Path, max_size_mb: int) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_filename = file.filename or "contract"
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UnsupportedDocumentTypeError(f"不支持的合同文件类型：{suffix or '无扩展名'}")
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
    try:
        validate_file_signature(saved_path, suffix)
    except Exception:
        saved_path.unlink(missing_ok=True)
        raise
    return saved_path


def validate_file_signature(path: Path, suffix: str | None = None) -> None:
    resolved_suffix = (suffix or path.suffix).lower()
    with path.open("rb") as file_obj:
        header = file_obj.read(8)
    valid = False
    if resolved_suffix == ".pdf":
        valid = header.startswith(b"%PDF-")
    elif resolved_suffix == ".docx":
        valid = header.startswith(b"PK\x03\x04")
    elif resolved_suffix == ".doc":
        valid = header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    elif resolved_suffix in IMAGE_EXTENSIONS:
        try:
            with Image.open(path) as image:
                image.verify()
            valid = True
        except Exception:
            valid = False
    if not valid:
        raise UnsafeUploadError("文件内容与扩展名不匹配，已拒绝上传")
