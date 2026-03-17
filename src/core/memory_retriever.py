"""Memory retrieval layer for Memoir.

Provides associative retrieval with session expansion,
time neighbor expansion, and similar memory expansion.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .config import Settings, get_settings
from .memory_index import MemoryIndex
from .memory_store import MemoryStore

logger = get_logger(__name__)


class MemoryRetriever:
    """Associative memory retrieval with multiple expansion strategies.

    Retrieval strategies:
    1. Session expansion: Include related messages from same session
    2. Time neighbor expansion: Include memories from nearby time periods
    3. Similar memory expansion: Include semantically similar memories
    """

    def __init__(self, user_id: str, settings: Optional[Settings] = None):
        """Initialize retriever for a user.

        Args:
            user_id: User identifier
            settings: Optional settings override
        """
        self.settings = settings or get_settings()
        self.user_id = user_id
        self.store = MemoryStore(user_id, settings)
        self.index = MemoryIndex(user_id, settings)

    async def retrieve(
        self,
        query: str,
        session_id: Optional[str] = None,
        include_short_term: bool = True,
        include_long_term: bool = True,
        expand_session: bool = True,
        expand_time: bool = True,
        expand_similar: bool = False,
    ) -> Dict[str, Any]:
        """Main retrieval entry point.

        Args:
            query: Search query
            session_id: Optional session ID for context
            include_short_term: Include short-term memory
            include_long_term: Include long-term memory
            expand_session: Expand with session context
            expand_time: Expand with time neighbors
            expand_similar: Expand with similar memories (enhanced mode)

        Returns:
            Dict with retrieved memories and metadata
        """
        results = {
            "query": query,
            "short_term": [],
            "long_term": [],
            "expanded": [],
        }

        # Get settings
        top_k = self.settings.retrieval.top_k
        threshold = self.settings.retrieval.similarity_threshold

        # 1. Short-term retrieval
        if include_short_term and session_id:
            short_term_entries = await self.store.read_short_term(
                limit=self.settings.memory.short_term_max_messages,
                session_id=session_id,
            )
            results["short_term"] = short_term_entries

        # 2. Long-term retrieval (semantic search)
        if include_long_term:
            long_term_results = await self.index.search(
                query=query,
                top_k=top_k,
                similarity_threshold=threshold,
            )
            results["long_term"] = long_term_results

            # 3. Session expansion (if enabled and we have a session)
            if expand_session and session_id:
                session_memories = await self._expand_session(
                    query,
                    session_id,
                    top_k,
                )
                results["expanded"].extend(session_memories)

            # 4. Time neighbor expansion
            if expand_time:
                time_memories = await self._expand_time_neighbor(
                    query,
                    top_k,
                )
                results["expanded"].extend(time_memories)

            # 5. Similar memory expansion (enhanced mode)
            if expand_similar:
                similar_memories = await self._expand_similar(
                    query,
                    top_k,
                )
                results["expanded"].extend(similar_memories)

        # Deduplicate results
        results["expanded"] = self._deduplicate_memories(results["expanded"])

        # Log the retrieval
        await self.store.log_operation("retrieve", {
            "query": query,
            "session_id": session_id,
            "short_term_count": len(results["short_term"]),
            "long_term_count": len(results["long_term"]),
            "expanded_count": len(results["expanded"]),
        })

        return results

    async def _expand_session(
        self,
        query: str,
        session_id: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Expand with session context.

        Args:
            query: Original query
            session_id: Session ID
            top_k: Number of results

        Returns:
            List of session-related memories
        """
        # Get recent messages from this session
        session_entries = await self.store.read_short_term(
            limit=self.settings.retrieval.expand_session_turns * 2,
            session_id=session_id,
        )

        if not session_entries:
            return []

        # Extract keywords from session for additional search
        session_text = " ".join(
            msg.get("content", "")
            for entry in session_entries
            for msg in entry.get("messages", [])
        )

        # Search long-term with session context
        session_query = f"{query} {session_text[:500]}"
        results = await self.index.search(
            query=session_query,
            top_k=top_k,
            similarity_threshold=0.5,  # Lower threshold for expansion
        )

        # Mark as session-expanded
        for r in results:
            r["expansion_type"] = "session"

        return results

    async def _expand_time_neighbor(
        self,
        query: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Expand with time-neighboring memories.

        Retrieves memories from nearby time periods.

        Args:
            query: Original query
            top_k: Number of results

        Returns:
            List of time-neighboring memories
        """
        # Get recent memories
        recent_memories = await self.store.read_long_term(limit=top_k * 2)

        if len(recent_memories) < 2:
            return []

        # Parse timestamps and find neighbors
        memories_by_time = []
        for mem in recent_memories:
            created_at = mem.get("created_at")
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    memories_by_time.append((dt, mem))
                except:
                    pass

        if len(memories_by_time) < 2:
            return []

        # Sort by time
        memories_by_time.sort(key=lambda x: x[0])

        # Find memories within time window
        days = self.settings.retrieval.expand_time_days
        time_window = timedelta(days=days)

        # Get the most recent memory's time as reference
        reference_time = memories_by_time[-1][0]

        neighbors = []
        for dt, mem in memories_by_time:
            if abs((reference_time - dt).total_seconds()) < time_window.total_seconds():
                # Don't include exact matches (already in main results)
                if mem.get("id") not in [r.get("id") for r in []]:
                    mem["expansion_type"] = "time_neighbor"
                    mem["similarity"] = 0.5  # Default similarity for time neighbors
                    neighbors.append(mem)

        return neighbors[:top_k]

    async def _expand_similar(
        self,
        query: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Expand with similar memories using iterative retrieval.

        Performs a second round of search using top results as queries.

        Args:
            query: Original query
            top_k: Number of results

        Returns:
            List of similar memories
        """
        # First search
        initial_results = await self.index.search(
            query=query,
            top_k=top_k,
            similarity_threshold=0.0,
        )

        if not initial_results:
            return []

        # Use top results to construct expanded query
        # Take content from top results and search again
        expanded_query_parts = [query]

        for result in initial_results[:3]:
            content = result.get("content", "")
            if content:
                # Take first 200 chars as additional context
                expanded_query_parts.append(content[:200])

        expanded_query = " ".join(expanded_query_parts)

        # Second search with expanded query
        second_results = await self.index.search(
            query=expanded_query,
            top_k=top_k,
            similarity_threshold=0.3,
        )

        # Mark as similar-expanded
        for r in second_results:
            r["expansion_type"] = "similar"

        # Filter out results already in initial search
        initial_ids = {r.get("id") for r in initial_results}
        return [r for r in second_results if r.get("id") not in initial_ids]

    def _deduplicate_memories(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Remove duplicate memories based on ID.

        Args:
            memories: List of memories

        Returns:
            Deduplicated list
        """
        seen_ids = set()
        unique = []

        for mem in memories:
            mem_id = mem.get("id")
            if mem_id and mem_id not in seen_ids:
                seen_ids.add(mem_id)
                unique.append(mem)

        return unique

    async def get_context_for_generation(
        self,
        query: str,
        session_id: Optional[str] = None,
        max_context_tokens: int = 4000,
    ) -> str:
        """Get formatted context string for LLM generation.

        Args:
            query: User query
            session_id: Optional session ID
            max_context_tokens: Approximate max tokens

        Returns:
            Formatted context string
        """
        # Get retrieval results
        results = await self.retrieve(
            query=query,
            session_id=session_id,
            include_short_term=True,
            include_long_term=True,
            expand_session=True,
            expand_time=True,
            expand_similar=False,
        )

        context_parts = []

        # Add short-term context
        if results["short_term"]:
            context_parts.append("## Recent Conversation")
            for entry in results["short_term"][-5:]:  # Last 5 entries
                for msg in entry.get("messages", []):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    context_parts.append(f"**{role}:** {content}")

        # Add long-term context
        if results["long_term"]:
            context_parts.append("\n## Relevant Memories")
            for mem in results["long_term"][:3]:  # Top 3
                title = mem.get("title", "Untitled")
                content = mem.get("content", "")[:500]
                context_parts.append(f"### {title}\n{content}...")

        # Add expanded context
        if results["expanded"]:
            context_parts.append("\n## Related Context")
            for mem in results["expanded"][:2]:
                title = mem.get("title", "Related")
                content = mem.get("content", "")[:300]
                context_parts.append(f"### {title}\n{content}...")

        return "\n\n".join(context_parts)
