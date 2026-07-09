from __future__ import annotations

from pathlib import Path

from PIL import Image

from contract_review.core.config import Settings
from contract_review.core.exceptions import UnsupportedDocumentTypeError


class DocumentLoader:
    supported_extensions = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

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
        return self._load_image_with_ocr(file_path)

    def _load_pdf(self, file_path: Path) -> str:
        import fitz

        with fitz.open(file_path) as document:
            return "\n".join(page.get_text("text") for page in document)

    def _load_docx(self, file_path: Path) -> str:
        from docx import Document

        document = Document(file_path)
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        table_text = []
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    table_text.append(" | ".join(cells))
        return "\n".join([*paragraphs, *table_text])

    def _load_image_with_ocr(self, file_path: Path) -> str:
        import pytesseract

        if self.settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.settings.tesseract_cmd
        config = ""
        if self.settings.tessdata_dir:
            config = f'--tessdata-dir "{self.settings.tessdata_dir}"'
        with Image.open(file_path) as image:
            return pytesseract.image_to_string(
                image,
                lang=self.settings.ocr_languages,
                config=config,
            )
