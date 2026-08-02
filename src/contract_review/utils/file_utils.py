from __future__ import annotations

import re
import unicodedata
import zipfile
from pathlib import Path
from uuid import uuid4

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring
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
MAX_IMAGE_PIXELS = 80_000_000
MAX_PDF_PAGES = 500


def sanitize_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return normalized or "contract"


def normalize_original_filename(filename: str, max_length: int = 260) -> str:
    leaf = filename.replace("\\", "/").rsplit("/", 1)[-1]
    leaf = unicodedata.normalize("NFKC", leaf)
    leaf = re.sub(r"[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]", "", leaf).strip()
    if not leaf or leaf in {".", ".."}:
        return "contract"
    suffix = Path(leaf).suffix
    if suffix and len(suffix) < max_length:
        stem = leaf[: -len(suffix)]
        leaf = f"{stem[: max_length - len(suffix)]}{suffix}"
    return leaf[:max_length]


async def save_upload_file(
    file: UploadFile,
    upload_dir: Path,
    max_size_mb: int,
    *,
    max_pdf_pages: int = MAX_PDF_PAGES,
    max_image_pixels: int = MAX_IMAGE_PIXELS,
) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_filename = normalize_original_filename(file.filename or "contract")
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
        validate_file_signature(
            saved_path,
            suffix,
            max_pdf_pages=max_pdf_pages,
            max_image_pixels=max_image_pixels,
        )
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
                lowered = normalized.casefold()
                if lowered.endswith("vbaproject.bin"):
                    raise UnsafeUploadError("DOCX 文件包含不允许的宏内容")
                if lowered.endswith(".rels") and entry.file_size <= 1024 * 1024:
                    try:
                        relationship_root = fromstring(archive.read(entry))
                    except (DefusedXmlException, ParseError) as exc:
                        raise UnsafeUploadError("DOCX 关系文件 XML 结构不安全或已损坏") from exc
                    has_external_target = any(
                        any(
                            attribute.rsplit("}", 1)[-1].casefold() == "targetmode"
                            and value.casefold() == "external"
                            for attribute, value in relationship.attrib.items()
                        )
                        for relationship in relationship_root.iter()
                    )
                    if has_external_target:
                        raise UnsafeUploadError("DOCX 文件包含外部资源引用")
    except zipfile.BadZipFile as exc:
        raise UnsafeUploadError("Office 文件压缩结构损坏") from exc


def validate_file_signature(
    path: Path,
    suffix: str | None = None,
    *,
    max_pdf_pages: int = MAX_PDF_PAGES,
    max_image_pixels: int = MAX_IMAGE_PIXELS,
) -> None:
    resolved_suffix = (suffix or path.suffix).lower()
    with path.open("rb") as file_obj:
        header = file_obj.read(8)
    valid = False
    if resolved_suffix == ".pdf":
        valid = header.startswith(b"%PDF-")
        if valid:
            try:
                import fitz

                with fitz.open(path) as document:
                    if document.needs_pass or len(document) > max_pdf_pages:
                        raise UnsafeUploadError("PDF 已加密或页数超过安全限制")
            except UnsafeUploadError:
                raise
            except Exception:
                valid = False
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
                if image.width * image.height > max_image_pixels:
                    raise UnsafeUploadError("图片像素数量超过安全限制")
                image.verify()
            valid = True
        except UnsafeUploadError:
            raise
        except Exception:
            valid = False
    if not valid:
        raise UnsafeUploadError("文件内容与扩展名不匹配，已拒绝上传")
