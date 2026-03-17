"""Dialogue engine for Memoir.

Assembles prompts, calls LLM, and integrates memories.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .config import Settings, get_settings
from .llm_client import LLMClientBase, get_llm_client
from .memory_retriever import MemoryRetriever
from .memory_store import MemoryStore

logger = get_logger(__name__)


class DialogueEngine:
    """Dialogue generation engine with memory integration."""

    def __init__(
        self,
        user_id: str,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClientBase] = None,
    ):
        """Initialize dialogue engine.

        Args:
            user_id: User identifier
            settings: Optional settings override
            llm_client: Optional LLM client override
        """
        self.settings = settings or get_settings()
        self.user_id = user_id
        self.store = MemoryStore(user_id, self.settings)
        self.retriever = MemoryRetriever(user_id, self.settings)
        self.llm = llm_client or get_llm_client(settings=self.settings)

    async def generate(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        use_memory: bool = True,
        system_prompt: Optional[str] = None,
        **generation_kwargs,
    ) -> Dict[str, Any]:
        """Generate a response to user message.

        Args:
            message: User message
            session_id: Optional session ID
            history: Optional conversation history
            use_memory: Whether to use memory retrieval
            system_prompt: Optional custom system prompt
            **generation_kwargs: Additional LLM parameters

        Returns:
            Dict with response and metadata
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        # Build messages for LLM
        messages = []

        # System prompt
        system = system_prompt or self._get_default_system_prompt()
        messages.append({"role": "system", "content": system})

        # Add history if provided
        if history:
            messages.extend(history[-10:])  # Last 10 messages

        # Get context from memory if enabled
        context = ""
        used_memories = []

        if use_memory:
            context = await self.retriever.get_context_for_generation(
                query=message,
                session_id=session_id,
            )
            if context:
                # Add context as system context
                context_message = {
                    "role": "system",
                    "content": f"Relevant context from memory:\n\n{context}",
                }
                messages.append(context_message)

                # Track used memories
                retrieval_results = await self.retriever.retrieve(
                    query=message,
                    session_id=session_id,
                )
                for mem in retrieval_results.get("long_term", []):
                    used_memories.append({
                        "id": mem.get("id"),
                        "title": mem.get("title"),
                        "similarity": mem.get("similarity"),
                    })

        # Add current message
        messages.append({"role": "user", "content": message})

        # Generate response
        try:
            response = await self.llm.generate(messages, **generation_kwargs)
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise RuntimeError(f"Failed to generate response: {e}")

        # Save to short-term memory
        await self.store.append_short_term(
            messages=[
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ],
            session_id=session_id,
        )

        # Log the interaction
        await self.store.log_operation("chat", {
            "session_id": session_id,
            "message_length": len(message),
            "response_length": len(response),
            "used_memories": used_memories,
            "context_used": bool(context),
        })

        return {
            "response": response,
            "session_id": session_id,
            "used_memories": used_memories,
            "context_used": bool(context),
        }

    async def generate_with_memories(
        self,
        message: str,
        session_id: Optional[str] = None,
        memory_ids: Optional[List[str]] = None,
        **generation_kwargs,
    ) -> Dict[str, Any]:
        """Generate response with specific memories injected.

        Args:
            message: User message
            session_id: Optional session ID
            memory_ids: Specific memory IDs to include
            **generation_kwargs: Additional LLM parameters

        Returns:
            Dict with response and metadata
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        # Build messages
        messages = []

        # System prompt
        system = self._get_default_system_prompt()
        messages.append({"role": "system", "content": system})

        # Inject specific memories if provided
        if memory_ids:
            memory_contents = []
            for mem_id in memory_ids:
                memories = await self.store.read_long_term(memory_id=mem_id)
                if memories:
                    mem = memories[0]
                    memory_contents.append(
                        f"## {mem.get('title', 'Memory')}\n\n{mem.get('content', '')}"
                    )

            if memory_contents:
                context = "\n\n---\n\n".join(memory_contents)
                messages.append({
                    "role": "system",
                    "content": f"Relevant memories:\n\n{context}",
                })

        # Add current message
        messages.append({"role": "user", "content": message})

        # Generate
        try:
            response = await self.llm.generate(messages, **generation_kwargs)
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise RuntimeError(f"Failed to generate response: {e}")

        # Save to memory
        await self.store.append_short_term(
            messages=[
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ],
            session_id=session_id,
        )

        return {
            "response": response,
            "session_id": session_id,
            "used_memories": memory_ids or [],
        }

    async def summarize_and_store(
        self,
        session_id: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Summarize conversation and store in long-term memory.

        Args:
            session_id: Session to summarize
            title: Optional title for the memory
            tags: Optional tags

        Returns:
            Created memory ID
        """
        # Get session messages
        entries = await self.store.read_short_term(
            limit=100,
            session_id=session_id,
        )

        if not entries:
            return ""

        # Build conversation text
        conversation = []
        for entry in entries:
            for msg in entry.get("messages", []):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation.append(f"**{role}:** {content}")

        conversation_text = "\n\n".join(conversation)

        # Build summary prompt
        summary_prompt = [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes conversations. "
                           "Create a concise summary that captures the key points, decisions, "
                           "and important information from the conversation. "
                           "Format as Markdown.",
            },
            {
                "role": "user",
                "content": f"Please summarize this conversation:\n\n{conversation_text}",
            },
        ]

        # Generate summary
        try:
            summary = await self.llm.generate(summary_prompt, max_tokens=1024)
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            summary = conversation_text  # Fallback to full conversation

        # Store as long-term memory
        memory_id = await self.store.append_long_term(
            content=summary,
            title=title or f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            tags=tags or ["conversation", "summary"],
            metadata={"session_id": session_id},
        )

        # Update index
        from .memory_index import MemoryIndex
        index = MemoryIndex(self.user_id, self.settings)
        await index.update_memory_file(
            memory_id=memory_id,
            content=summary,
            title=title,
            tags=tags,
        )

        logger.info(f"Created summary memory: {memory_id}")
        return memory_id

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt.

        Returns:
            Default system prompt
        """
        return """You are a helpful AI assistant with long-term memory capabilities.

When answering questions, you can draw on relevant memories from the context provided.
Be concise, accurate, and helpful. If you're unsure about something, say so.

Your responses should be natural and conversational."""
