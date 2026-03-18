"""JSON importer."""

import json

import aiofiles

from .base import BaseImporter, register_importer


@register_importer
class JsonImporter(BaseImporter):
    """JSON file importer."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".json"]

    async def extract_text(self, file_path: str) -> str:
        """Extract and format text from a JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Formatted JSON string
        """
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        # Try to parse and reformat
        try:
            data = json.loads(content)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            # If parsing fails, return as-is
            return content
