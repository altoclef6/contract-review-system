from __future__ import annotations

import re
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from contract_review.core.exceptions import (
    UnsafeUploadError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
)

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".png": {"image/png", "application/octet-stream"},
    ".jpg": {"image/jpeg", "application/octet-stream"},
    ".jpeg": {"image/jpeg", "application/octet-stream"},
    ".tif": {"image/tiff", "application/octet-stream"},
    ".tiff": {"image/tiff", "application/octet-stream"},
    ".bmp": {"image/bmp", "image/x-ms-bmp", "application/octet-stream"},
}
MAX_OFFICE_ENTRIES = 1_000
MAX_OFFICE_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_OFFICE_COMPRESSION_RATIO = 100


def sanitize_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return normalized or "contract"


async def save_upload_file(file: UploadFile, upload_dir: Path, max_size_mb: int) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_filename = file.filename or "contract"
    suffix = Path(original_filename).suffix.lower()
    supplied_mime = (file.content_type or "application/octet-stream").lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UnsupportedDocumentTypeError(f"不支持的合同文件类型：{suffix or '无扩展名'}")
    if supplied_mime not in ALLOWED_MIME_TYPES[suffix]:
        await file.close()
        raise UnsafeUploadError("文件 MIME 类型与扩展名不匹配")
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


def validate_office_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_OFFICE_ENTRIES:
                raise UnsafeUploadError("Office 文件包含过多压缩条目")
            names = {entry.filename.replace("\\", "/") for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UnsafeUploadError("文件不是有效的 DOCX 文档")
            total_size = 0
            for entry in entries:
                normalized = entry.filename.replace("\\", "/")
                if normalized.startswith("/") or ".." in normalized.split("/"):
                    raise UnsafeUploadError("Office 文件包含不安全路径")
                total_size += entry.file_size
                if total_size > MAX_OFFICE_UNCOMPRESSED_BYTES:
                    raise UnsafeUploadError("Office 文件解压后体积超过安全限制")
                compressed = max(entry.compress_size, 1)
                ratio = entry.file_size / compressed
                if entry.file_size > 1024 * 1024 and ratio > MAX_OFFICE_COMPRESSION_RATIO:
                    raise UnsafeUploadError("Office 文件压缩率异常")
    except zipfile.BadZipFile as exc:
        raise UnsafeUploadError("Office 文件压缩结构损坏") from exc


def validate_file_signature(path: Path, suffix: str | None = None) -> None:
    resolved_suffix = (suffix or path.suffix).lower()
    with path.open("rb") as file_obj:
        header = file_obj.read(8)
    valid = False
    if resolved_suffix == ".pdf":
        valid = header.startswith(b"%PDF-")
    elif resolved_suffix == ".docx":
        valid = header.startswith(b"PK\x03\x04")
        if valid:
            validate_office_archive(path)
    elif resolved_suffix == ".doc":
        valid = header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    elif resolved_suffix == ".txt":
        try:
            raw = path.read_bytes()
            if b"\x00" in raw[:4096]:
                valid = raw.startswith((b"\xff\xfe", b"\xfe\xff"))
            else:
                raw.decode("utf-8-sig")
                valid = True
        except UnicodeDecodeError:
            try:
                raw.decode("gb18030")
                valid = True
            except UnicodeDecodeError:
                valid = False
    elif resolved_suffix in IMAGE_EXTENSIONS:
        try:
            with Image.open(path) as image:
                image.verify()
            valid = True
        except Exception:
            valid = False
    if not valid:
        raise UnsafeUploadError("文件内容与扩展名不匹配，已拒绝上传")
