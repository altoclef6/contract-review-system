from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from contract_review.core.config import Settings
from contract_review.core.exceptions import UnsupportedDocumentTypeError


class DocumentLoader:
    supported_extensions = {
        ".pdf",
        ".doc",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def load_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix not in self.supported_extensions:
            raise UnsupportedDocumentTypeError(f"Unsupported contract file type: {suffix}")

        if suffix == ".pdf":
            return self._load_pdf(file_path)
        if suffix == ".docx":
            return self._load_docx(file_path)
        if suffix == ".doc":
            return self._load_legacy_doc(file_path)
        return self._load_image_with_ocr(file_path)

    def _load_pdf(self, file_path: Path) -> str:
        import fitz

        with fitz.open(file_path) as document:
            pages = [page.get_text("text").strip() for page in document]
            if sum(len(page) for page in pages) >= max(80, len(document) * 20):
                return "\n".join(pages)
            ocr_pages = []
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                ocr_pages.append(self._ocr_image(image))
            return "\n".join(ocr_pages)

    def _load_docx(self, file_path: Path) -> str:
        from docx import Document

        document = Document(str(file_path))
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        table_text = []
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    table_text.append(" | ".join(cells))
        return "\n".join([*paragraphs, *table_text])

    def _load_image_with_ocr(self, file_path: Path) -> str:
        with Image.open(file_path) as image:
            return self._ocr_image(image)

    def _ocr_image(self, image: Image.Image) -> str:
        import pytesseract

        if self.settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.settings.tesseract_cmd
        config = (
            f'--tessdata-dir "{self.settings.tessdata_dir}"' if self.settings.tessdata_dir else ""
        )
        return str(pytesseract.image_to_string(
            image,
            lang=self.settings.ocr_languages,
            config=config,
            timeout=self.settings.ocr_timeout_seconds,
        ))

    def _load_legacy_doc(self, file_path: Path) -> str:
        command = self.settings.libreoffice_cmd or shutil.which("soffice")
        if not command:
            raise UnsupportedDocumentTypeError(
                "读取旧版 .doc 需要安装 LibreOffice，并配置 LIBREOFFICE_CMD"
            )
        with tempfile.TemporaryDirectory() as output_dir:
            profile_dir = Path(output_dir) / "profile"
            completed = subprocess.run(
                [
                    command,
                    f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
                    "--headless",
                    "--norestore",
                    "--nodefault",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    output_dir,
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            converted = Path(output_dir) / f"{file_path.stem}.docx"
            if completed.returncode != 0 or not converted.exists():
                raise UnsupportedDocumentTypeError("旧版 .doc 转换失败，请检查 LibreOffice 配置")
            return self._load_docx(converted)
