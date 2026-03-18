"""Plain text importer."""

import aiofiles
from pathlib import Path

from .base import BaseImporter, register_importer


@register_importer
class TxtImporter(BaseImporter):
    """Plain text file importer."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".text", ".log"]

    async def extract_text(self, file_path: str) -> str:
        """Extract plain text from a file.

        Args:
            file_path: Path to the text file

        Returns:
            Text content
        """
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
        # Basic cleanup: remove excessive whitespace
        lines = [line.strip() for line in content.split("\n")]
        return "\n".join(line for line in lines if line)
