"""Memory storage layer for Memoir.

Handles user directory management, short-term/long-term memory,
file uploads, and operation logs.
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import aiofiles.os

from ..utils.logger import get_logger
from .config import Settings, get_settings

logger = get_logger(__name__)


class MemoryStore:
    """Core storage class for user memories.

    Directory structure:
        users/{user_id}/
        ├── short_term/       # Short-term logs (JSONL)
        ├── long_term/        # Long-term memories (Markdown)
        ├── files/            # Uploaded files
        ├── meta/             # Metadata
        └── logs/             # Operation logs
    """

    def __init__(self, user_id: str, settings: Optional[Settings] = None):
        """Initialize memory store for a user.

        Args:
            user_id: User identifier
            settings: Optional settings override
        """
        self.settings = settings or get_settings()
        self.user_id = user_id
        self.base_dir = Path(self.settings.storage.base_dir) / self.settings.storage.users_dir / user_id
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        dirs = [
            self.base_dir / "short_term",
            self.base_dir / "long_term",
            self.base_dir / "files",
            self.base_dir / "meta",
            self.base_dir / "logs",
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    @property
    def short_term_dir(self) -> Path:
        """Short-term memory directory."""
        return self.base_dir / "short_term"

    @property
    def long_term_dir(self) -> Path:
        """Long-term memory directory."""
        return self.base_dir / "long_term"

    @property
    def files_dir(self) -> Path:
        """Uploaded files directory."""
        return self.base_dir / "files"

    @property
    def meta_dir(self) -> Path:
        """Metadata directory."""
        return self.base_dir / "meta"

    @property
    def logs_dir(self) -> Path:
        """Operation logs directory."""
        return self.base_dir / "logs"

    async def append_short_term(
        self,
        messages: List[Dict[str, Any]],
        session_id: Optional[str] = None,
    ) -> str:
        """Append messages to short-term log.

        Args:
            messages: List of message dicts with 'role' and 'content'
            session_id: Optional session identifier

        Returns:
            Log entry ID
        """
        entry_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        # Determine log file (by date for organization)
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self.short_term_dir / f"{date_str}.jsonl"

        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "session_id": session_id,
            "messages": messages,
        }

        async with aiofiles.open(log_file, mode="a") as f:
            await f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"Appended {len(messages)} messages to short-term log: {entry_id}")
        return entry_id

    async def read_short_term(
        self,
        limit: int = 100,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Read recent messages from short-term log.

        Args:
            limit: Maximum number of entries to return
            session_id: Optional filter by session ID

        Returns:
            List of log entries
        """
        # Get all JSONL files sorted by date (newest first)
        jsonl_files = sorted(self.short_term_dir.glob("*.jsonl"), reverse=True)

        entries = []
        for log_file in jsonl_files:
            async with aiofiles.open(log_file, mode="r") as f:
                async for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if session_id is None or entry.get("session_id") == session_id:
                            entries.append(entry)
                        if len(entries) >= limit:
                            break
            if len(entries) >= limit:
                break

        # Return newest first, limited
        return entries[:limit]

    async def append_long_term(
        self,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append a long-term memory.

        Args:
            content: Memory content (Markdown)
            title: Optional title
            tags: Optional tags
            metadata: Optional additional metadata

        Returns:
            Memory ID
        """
        memory_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        # Create filename from title or ID
        safe_title = "".join(c for c in (title or memory_id)[:50] if c.isalnum() or c in "-_")
        filename = f"{safe_title}_{memory_id[:8]}.md"
        filepath = self.long_term_dir / filename

        # Build frontmatter
        frontmatter = {
            "id": memory_id,
            "created_at": timestamp,
            "title": title,
            "tags": tags or [],
            **(metadata or {}),
        }

        # Write markdown with frontmatter
        frontmatter_yaml = "---\n"
        for key, value in frontmatter.items():
            if isinstance(value, list):
                frontmatter_yaml += f"{key}:\n"
                for item in value:
                    frontmatter_yaml += f"  - {item}\n"
            else:
                frontmatter_yaml += f"{key}: {value}\n"
        frontmatter_yaml += "---\n\n"

        full_content = frontmatter_yaml + content

        async with aiofiles.open(filepath, mode="w") as f:
            await f.write(full_content)

        logger.info(f"Appended long-term memory: {memory_id}")
        return memory_id

    async def read_long_term(
        self,
        memory_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Read long-term memories.

        Args:
            memory_id: Optional specific memory ID
            tags: Optional filter by tags
            limit: Maximum number of memories

        Returns:
            List of memory entries with content
        """
        memories = []

        if memory_id:
            # Find specific memory
            for md_file in self.long_term_dir.glob("*.md"):
                content = await self._read_markdown_file(md_file)
                if content and content.get("id") == memory_id:
                    memories.append(content)
                    break
        else:
            # List all memories
            for md_file in sorted(self.long_term_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                content = await self._read_markdown_file(md_file)
                if content:
                    # Filter by tags if specified
                    if tags:
                        if any(tag in content.get("tags", []) for tag in tags):
                            memories.append(content)
                    else:
                        memories.append(content)

                if len(memories) >= limit:
                    break

        return memories

    async def _read_markdown_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Read a markdown file and parse frontmatter.

        Args:
            filepath: Path to markdown file

        Returns:
            Dict with metadata and content
        """
        try:
            async with aiofiles.open(filepath, mode="r") as f:
                content = await f.read()

            # Parse frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter_text = parts[1].strip()
                    body = parts[2].strip()

                    # Simple YAML-like parsing
                    metadata = {}
                    for line in frontmatter_text.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value = value.strip()
                            if value.startswith("[") and value.endswith("]"):
                                metadata[key] = [v.strip() for v in value[1:-1].split(",")]
                            else:
                                metadata[key] = value

                    return {
                        **metadata,
                        "content": body,
                        "file": str(filepath),
                    }

            return {"content": content, "file": str(filepath)}
        except Exception as e:
            logger.error(f"Error reading markdown file {filepath}: {e}")
            return None

    async def save_file(
        self,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """Save an uploaded file.

        Args:
            filename: Original filename
            content: File content as bytes
            content_type: Optional content type

        Returns:
            File ID
        """
        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix
        safe_filename = f"{file_id}{ext}"
        filepath = self.files_dir / safe_filename

        async with aiofiles.open(filepath, mode="wb") as f:
            await f.write(content)

        # Save metadata
        meta = {
            "id": file_id,
            "original_filename": filename,
            "content_type": content_type,
            "size": len(content),
            "created_at": datetime.utcnow().isoformat(),
        }

        meta_file = self.meta_dir / f"{file_id}.json"
        async with aiofiles.open(meta_file, mode="w") as f:
            await f.write(json.dumps(meta, indent=2))

        logger.info(f"Saved file: {file_id} ({filename})")
        return file_id

    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata and path.

        Args:
            file_id: File identifier

        Returns:
            Dict with file info or None if not found
        """
        meta_file = self.meta_dir / f"{file_id}.json"
        if not meta_file.exists():
            return None

        async with aiofiles.open(meta_file, mode="r") as f:
            meta = json.loads(await f.read())

        # Find the actual file
        for file_path in self.files_dir.glob(f"{file_id}.*"):
            meta["path"] = str(file_path)
            return meta

        return None

    async def log_operation(
        self,
        operation: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an operation.

        Args:
            operation: Operation name
            details: Optional operation details

        Returns:
            Log entry ID
        """
        entry_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        log_file = self.logs_dir / "operations.jsonl"
        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "operation": operation,
            "details": details or {},
        }

        async with aiofiles.open(log_file, mode="a") as f:
            await f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry_id

    async def get_operations(
        self,
        operation: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get operation logs.

        Args:
            operation: Optional filter by operation name
            limit: Maximum number of entries

        Returns:
            List of operation entries
        """
        log_file = self.logs_dir / "operations.jsonl"
        if not log_file.exists():
            return []

        entries = []
        async with aiofiles.open(log_file, mode="r") as f:
            async for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if operation is None or entry.get("operation") == operation:
                        entries.append(entry)
                        if len(entries) >= limit:
                            break

        return entries

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a long-term memory.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        for md_file in self.long_term_dir.glob("*.md"):
            content = await self._read_markdown_file(md_file)
            if content and content.get("id") == memory_id:
                await aiofiles.os.remove(md_file)
                logger.info(f"Deleted memory: {memory_id}")
                return True
        return False

    async def list_memories(self, include_content: bool = False) -> List[Dict[str, Any]]:
        """List all long-term memories.

        Args:
            include_content: Whether to include full content

        Returns:
            List of memory metadata
        """
        memories = []
        for md_file in sorted(self.long_term_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            content = await self._read_markdown_file(md_file)
            if content:
                memories.append({
                    "id": content.get("id"),
                    "title": content.get("title"),
                    "tags": content.get("tags", []),
                    "created_at": content.get("created_at"),
                    "file": content.get("file"),
                    "content": content.get("content") if include_content else None,
                })
        return memories
