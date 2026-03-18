"""Base importer class for memory import."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class BaseImporter(ABC):
    """Abstract base class for file importers.

    Subclasses must implement the extract_text method.
    """

    @property
    def name(self) -> str:
        """Importer name."""
        return self.__class__.__name__.replace("Importer", "").lower()

    @property
    def supported_extensions(self) -> list[str]:
        """List of supported file extensions."""
        return []

    @abstractmethod
    async def extract_text(self, file_path: str) -> str:
        """Extract text content from a file.

        Args:
            file_path: Path to the file

        Returns:
            Extracted text content

        Raises:
            NotImplementedError: If not implemented
        """
        raise NotImplementedError

    def can_handle(self, file_path: str) -> bool:
        """Check if this importer can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if the file extension is supported
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_extensions


# Registry of importers
IMPORTER_REGISTRY: dict[str, type[BaseImporter]] = {}


def register_importer(importer_class: type[BaseImporter]) -> type[BaseImporter]:
    """Decorator to register an importer class.

    Args:
        importer_class: The importer class to register

    Returns:
        The same class (for use as decorator)
    """
    instance = importer_class()
    for ext in instance.supported_extensions:
        IMPORTER_REGISTRY[ext] = importer_class
    return importer_class


def get_importer(file_path: str) -> Optional[BaseImporter]:
    """Get the appropriate importer for a file.

    Args:
        file_path: Path to the file

    Returns:
        An importer instance or None if no suitable importer found
    """
    ext = Path(file_path).suffix.lower()
    importer_class = IMPORTER_REGISTRY.get(ext)
    if importer_class:
        return importer_class()
    return None
