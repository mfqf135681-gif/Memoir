"""HTML importer."""

from pathlib import Path

from bs4 import BeautifulSoup

from .base import BaseImporter, register_importer


@register_importer
class HtmlImporter(BaseImporter):
    """HTML file importer."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".html", ".htm"]

    async def extract_text(self, file_path: str) -> str:
        """Extract text from an HTML file.

        Args:
            file_path: Path to the HTML file

        Returns:
            Extracted text content
        """
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        # Get text from body or fallback to whole document
        body = soup.find("body")
        if body:
            text = body.get_text(separator="\n")
        else:
            text = soup.get_text(separator="\n")

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)
