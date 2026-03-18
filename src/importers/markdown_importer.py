"""Markdown importer."""

import aiofiles

from .base import BaseImporter, register_importer


@register_importer
class MarkdownImporter(BaseImporter):
    """Markdown file importer."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown"]

    async def extract_text(self, file_path: str) -> str:
        """Extract text from a markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            Text content (markdown preserved)
        """
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
        return content
