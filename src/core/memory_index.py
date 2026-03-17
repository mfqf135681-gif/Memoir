"""Memory indexing layer for Memoir.

Provides vector (Chroma) and full-text (FTS5) indexing.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from ..utils.logger import get_logger
from .config import Settings, get_settings

logger = get_logger(__name__)

# Try to import chromadb, make it optional
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class MemoryIndex:
    """Index manager for user memories.

    Provides:
    - Vector indexing via ChromaDB
    - Full-text search via SQLite FTS5
    """

    def __init__(self, user_id: str, settings: Optional[Settings] = None):
        """Initialize index for a user.

        Args:
            user_id: User identifier
            settings: Optional settings override
        """
        self.settings = settings or get_settings()
        self.user_id = user_id
        self.base_dir = Path(self.settings.storage.base_dir) / self.settings.storage.users_dir / user_id
        self.index_dir = self.base_dir / "index"
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self._chroma_client = None
        self._chroma_collection = None

    @property
    def chroma_path(self) -> Path:
        """Chroma database path."""
        return self.index_dir / "chroma"

    @property
    def fts_db_path(self) -> Path:
        """FTS database path."""
        return self.index_dir / "search.db"

    def _get_chroma_client(self):
        """Get or create ChromaDB client."""
        if not CHROMADB_AVAILABLE:
            raise RuntimeError("ChromaDB not available. Install with: pip install chromadb")

        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._chroma_client

    def _get_chroma_collection(self):
        """Get or create ChromaDB collection."""
        if self._chroma_collection is None:
            client = self._get_chroma_client()
            self._chroma_collection = client.get_or_create_collection(
                name="memories",
                metadata={"user_id": self.user_id},
            )
        return self._chroma_collection

    def _init_fts(self):
        """Initialize FTS5 table if not exists."""
        conn = sqlite3.connect(str(self.fts_db_path))
        cursor = conn.cursor()

        # Note: FTS5 tokenize option doesn't support parameter binding
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                id,
                title,
                content,
                tags,
                created_at
            )
        """)

        conn.commit()
        conn.close()

    async def index_user_memories(self, force_rebuild: bool = False):
        """Index all memories for a user.

        Args:
            force_rebuild: If True, rebuild entire index
        """
        if force_rebuild:
            await self._clear_index()

        # Get all long-term memories
        from .memory_store import MemoryStore
        store = MemoryStore(self.user_id, self.settings)
        memories = await store.read_long_term(limit=10000)

        logger.info(f"Indexing {len(memories)} memories for user {self.user_id}")

        # Index each memory
        for memory in memories:
            await self.update_memory_file(
                memory_id=memory.get("id", ""),
                content=memory.get("content", ""),
                title=memory.get("title"),
                tags=memory.get("tags", []),
            )

    async def _clear_index(self):
        """Clear all indexes."""
        # Clear Chroma
        if CHROMADB_AVAILABLE and self.chroma_path.exists():
            import shutil
            shutil.rmtree(self.chroma_path)
            self._chroma_client = None
            self._chroma_collection = None

        # Clear FTS
        if self.fts_db_path.exists():
            self.fts_db_path.unlink()

        self._init_fts()

    async def update_memory_file(
        self,
        memory_id: str,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """Update or add a memory to the index.

        Args:
            memory_id: Memory ID
            content: Memory content
            title: Optional title
            tags: Optional tags
        """
        # Update vector index
        if self.settings.index.vector.enabled and CHROMADB_AVAILABLE:
            try:
                collection = self._get_chroma_collection()

                # Generate embedding text
                embedding_text = f"{title or ''} {' '.join(tags or [])} {content}"

                # Upsert to Chroma
                collection.upsert(
                    ids=[memory_id],
                    documents=[embedding_text],
                    metadatas=[{
                        "memory_id": memory_id,
                        "title": title or "",
                        "tags": ",".join(tags or []),
                        "updated_at": datetime.utcnow().isoformat(),
                    }],
                )
            except Exception as e:
                logger.error(f"Error updating vector index: {e}")

        # Update FTS index
        if self.settings.index.fulltext.enabled:
            try:
                self._init_fts()
                conn = sqlite3.connect(str(self.fts_db_path))
                cursor = conn.cursor()

                # Delete existing entry
                cursor.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))

                # Insert new entry
                cursor.execute("""
                    INSERT INTO memories_fts (id, title, content, tags, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    memory_id,
                    title or "",
                    content,
                    ",".join(tags or []),
                    datetime.utcnow().isoformat(),
                ))

                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error updating FTS index: {e}")

    async def search(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining vector and FTS results.

        Args:
            query: Search query
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score

        Returns:
            List of matching memories with scores
        """
        results = []

        # Vector search
        if self.settings.index.vector.enabled and CHROMADB_AVAILABLE:
            try:
                collection = self._get_chroma_collection()
                vector_results = collection.query(
                    query_texts=[query],
                    n_results=top_k * 2,
                )

                if vector_results and vector_results.get("ids"):
                    for i, mem_id in enumerate(vector_results["ids"][0]):
                        distance = vector_results["distances"][0][i]
                        similarity = 1 - distance  # Convert distance to similarity

                        if similarity >= similarity_threshold:
                            results.append({
                                "id": mem_id,
                                "source": "vector",
                                "similarity": similarity,
                                "metadata": vector_results.get("metadatas", [[{}]])[0][i],
                            })
            except Exception as e:
                logger.error(f"Error in vector search: {e}")

        # FTS search
        if self.settings.index.fulltext.enabled:
            try:
                self._init_fts()
                conn = sqlite3.connect(str(self.fts_db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Simple FTS search with ranking
                limit = top_k * 2
                # Escape single quotes in query
                safe_query = query.replace("'", "''")
                cursor.execute(f"""
                    SELECT id, title, content, tags, created_at,
                           rank as score
                    FROM memories_fts
                    WHERE memories_fts MATCH '{safe_query}'
                    ORDER BY rank
                    LIMIT {limit}
                """)

                for row in cursor.fetchall():
                    # Normalize BM25 score (negative, lower is better)
                    normalized_score = 1 / (1 + abs(row["score"]))

                    # Check if already in results from vector
                    existing = next((r for r in results if r["id"] == row["id"]), None)
                    if existing:
                        # Combine scores
                        existing["similarity"] = (existing["similarity"] + normalized_score) / 2
                        existing["source"] = "hybrid"
                    else:
                        results.append({
                            "id": row["id"],
                            "source": "fts",
                            "similarity": normalized_score,
                            "title": row["title"],
                            "content": row["content"],
                            "tags": row["tags"].split(",") if row["tags"] else [],
                            "created_at": row["created_at"],
                        })

                conn.close()
            except Exception as e:
                logger.error(f"Error in FTS search: {e}")

        # Sort by similarity and limit
        results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return results[:top_k]

    async def delete_memory(self, memory_id: str):
        """Remove a memory from the index.

        Args:
            memory_id: Memory ID to remove
        """
        # Remove from Chroma
        if CHROMADB_AVAILABLE:
            try:
                collection = self._get_chroma_collection()
                collection.delete(ids=[memory_id])
            except Exception as e:
                logger.error(f"Error deleting from vector index: {e}")

        # Remove from FTS
        if self.fts_db_path.exists():
            try:
                conn = sqlite3.connect(str(self.fts_db_path))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error deleting from FTS index: {e}")

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get index statistics.

        Returns:
            Dict with index stats
        """
        stats = {
            "user_id": self.user_id,
            "vector_enabled": self.settings.index.vector.enabled,
            "fts_enabled": self.settings.index.fulltext.enabled,
        }

        # Vector count
        if CHROMADB_AVAILABLE:
            try:
                collection = self._get_chroma_collection()
                stats["vector_count"] = collection.count()
            except:
                stats["vector_count"] = 0
        else:
            stats["vector_count"] = 0

        # FTS count
        if self.fts_db_path.exists():
            try:
                conn = sqlite3.connect(str(self.fts_db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM memories_fts")
                stats["fts_count"] = cursor.fetchone()[0]
                conn.close()
            except:
                stats["fts_count"] = 0
        else:
            stats["fts_count"] = 0

        return stats
