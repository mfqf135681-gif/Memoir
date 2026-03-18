"""PDF importer."""

from pathlib import Path

import pdfplumber

from .base import BaseImporter, register_importer


@register_importer
class PdfImporter(BaseImporter):
    """PDF document importer."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    async def extract_text(self, file_path: str) -> str:
        """Extract text from a PDF document.

        Args:
            file_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        text_parts = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    # Basic cleanup: remove excessive empty lines
                    lines = [line.strip() for line in page_text.split("\n")]
                    cleaned = "\n".join(line for line in lines if line)
                    if cleaned:
                        text_parts.append(cleaned)

        return "\n\n".join(text_parts)
