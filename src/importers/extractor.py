"""Memory extraction using LLM."""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .base import get_importer

logger = get_logger(__name__)

# Default chunk size (characters)
DEFAULT_CHUNK_SIZE = 6000
# Overlap between chunks
CHUNK_OVERLAP = 200


EXTRACTION_PROMPT = """你是一个信息提取助手。从以下文本中提取出值得长期记住的信息，如个人偏好、事实、目标、重要决策等。

以 JSON 数组形式返回，每个元素是一个对象，包含：
- "text": 记忆内容（简洁，一句话）
- "confidence": 置信度（0-1之间的浮点数）

如果没有重要信息，返回空数组 []。

文本内容：
{text}

返回格式示例：
[
  {{"text": "用户喜欢科幻电影", "confidence": 0.95}},
  {{"text": "用户的职业是设计师", "confidence": 0.9}}
]
"""


class MemoryExtractor:
    """Extract potential memories from text using LLM."""

    def __init__(
        self,
        llm_client: Any,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ):
        """Initialize the extractor.

        Args:
            llm_client: LLM client for generating extractions
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between chunks
        """
        self.llm_client = llm_client
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into overlapping chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at a newline or sentence boundary
            if end < len(text):
                # Look for paragraph breaks first
                break_point = text.rfind("\n\n", start, end)
                if break_point > start + self.chunk_size // 2:
                    end = break_point + 2
                else:
                    # Then sentence boundaries
                    break_point = max(
                        text.rfind(". ", start, end),
                        text.rfind("? ", start, end),
                        text.rfind("! ", start, end),
                    )
                    if break_point > start + self.chunk_size // 2:
                        end = break_point + 2

            chunks.append(text[start:end])
            start = end - self.chunk_overlap

        return chunks

    async def _extract_from_chunk(
        self,
        chunk: str,
        source: str,
        max_retries: int = 2,
    ) -> List[Dict[str, Any]]:
        """Extract memories from a single chunk.

        Args:
            chunk: Text chunk to analyze
            source: Source identifier
            max_retries: Maximum retry attempts

        Returns:
            List of extracted memories
        """
        prompt = EXTRACTION_PROMPT.format(text=chunk)

        for attempt in range(max_retries):
            try:
                response = await self.llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1500,
                )

                # Parse JSON from response
                memories = self._parse_json_response(response)

                # Add source snippet and metadata
                for mem in memories:
                    mem["source_file"] = source
                    mem["source_snippet"] = chunk[:500]  # First 500 chars as reference

                return memories

            except Exception as e:
                logger.warning(f"Extraction attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to extract from chunk after {max_retries} attempts")
                    return []

        return []

    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse JSON from LLM response.

        Args:
            response: LLM response text

        Returns:
            List of memory dicts
        """
        # Try to extract JSON array from response
        # First, look for JSON in code blocks
        code_block_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", response)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find any array in the response
        array_match = re.search(r"\[[\s\S]*\]", response)
        if array_match:
            try:
                result = json.loads(array_match.group(0))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # Last resort: try to clean and parse the whole response
        try:
            result = json.loads(response)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        logger.warning(f"Could not parse JSON from LLM response: {response[:200]}...")
        return []

    def _deduplicate_memories(
        self,
        memories: List[Dict[str, Any]],
        threshold: float = 0.85,
    ) -> List[Dict[str, Any]]:
        """Remove duplicate memories based on text similarity.

        Args:
            memories: List of memories
            threshold: Similarity threshold (0-1)

        Returns:
            Deduplicated list
        """
        if not memories:
            return []

        # Simple deduplication using exact match first
        seen = set()
        unique = []

        for mem in memories:
            text = mem.get("text", "").strip().lower()
            if text and text not in seen:
                seen.add(text)
                unique.append(mem)

        return unique

    async def extract(
        self,
        text: str,
        source: str = "imported_file",
    ) -> List[Dict[str, Any]]:
        """Extract potential memories from text.

        Args:
            text: Full text to analyze
            source: Source identifier (e.g., filename)

        Returns:
            List of candidate memories with metadata
        """
        logger.info(f"Starting memory extraction from {source}, text length: {len(text)}")

        # Split into chunks
        chunks = self._split_into_chunks(text)
        logger.info(f"Split into {len(chunks)} chunks")

        # Extract from each chunk
        all_candidates = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i + 1}/{len(chunks)}")
            candidates = await self._extract_from_chunk(chunk, source)
            all_candidates.extend(candidates)

        logger.info(f"Extracted {len(all_candidates)} raw candidates")

        # Deduplicate
        unique_candidates = self._deduplicate_memories(all_candidates)
        logger.info(f"After deduplication: {len(unique_candidates)} candidates")

        # Add IDs and timestamps
        for mem in unique_candidates:
            mem["id"] = str(uuid.uuid4())
            mem["created_at"] = datetime.utcnow().isoformat()
            mem["confidence"] = mem.get("confidence", 1.0)

        return unique_candidates


class ImportManager:
    """Manages import jobs and pending memories."""

    def __init__(self, user_id: str, base_dir: str):
        """Initialize the import manager.

        Args:
            user_id: User identifier
            base_dir: Base data directory
        """
        self.user_id = user_id
        self.base_dir = Path(base_dir) / "users" / user_id
        self.pending_dir = self.base_dir / "meta" / "pending_memories"
        self.jobs_dir = self.base_dir / "meta" / "import_jobs"
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _get_pending_file(self, job_id: Optional[str] = None) -> Path:
        """Get the pending memories file path.

        Args:
            job_id: Optional job ID

        Returns:
            Path to pending memories file
        """
        if job_id:
            return self.pending_dir / f"{job_id}.jsonl"
        return self.pending_dir / "all.jsonl"

    def _get_job_file(self, job_id: str) -> Path:
        """Get the job status file path.

        Args:
            job_id: Job ID

        Returns:
            Path to job file
        """
        return self.jobs_dir / f"{job_id}.json"

    async def create_import_job(
        self,
        file_path: str,
        original_filename: str,
        llm_client: Any,
    ) -> Dict[str, Any]:
        """Create and process an import job.

        Args:
            file_path: Path to the uploaded file
            original_filename: Original filename
            llm_client: LLM client for extraction

        Returns:
            Job info including job_id and initial status
        """
        import aiofiles
        import json

        job_id = str(uuid.uuid4())
        job_file = self._get_job_file(job_id)

        # Save initial job status
        job_info = {
            "job_id": job_id,
            "status": "processing",
            "filename": original_filename,
            "created_at": datetime.utcnow().isoformat(),
            "candidates_count": 0,
            "completed_at": None,
        }

        async with aiofiles.open(job_file, "w") as f:
            await f.write(json.dumps(job_info))

        # Get appropriate importer
        importer = get_importer(file_path)
        if not importer:
            await self._update_job_status(job_id, "failed", error="Unsupported file format")
            return {**job_info, "error": "Unsupported file format"}

        try:
            # Extract text
            text = await importer.extract_text(file_path)
            logger.info(f"Extracted {len(text)} characters from {original_filename}")

            if not text.strip():
                await self._update_job_status(job_id, "failed", error="Empty file")
                return {**job_info, "error": "Empty file", "status": "failed"}

            # Extract memories using LLM
            extractor = MemoryExtractor(llm_client)
            candidates = await extractor.extract(text, original_filename)

            # Save candidates to pending file
            pending_file = self._get_pending_file(job_id)
            async with aiofiles.open(pending_file, "w") as f:
                for mem in candidates:
                    await f.write(json.dumps(mem, ensure_ascii=False) + "\n")

            # Update job status
            await self._update_job_status(
                job_id,
                "completed",
                candidates_count=len(candidates),
            )

            return {
                "job_id": job_id,
                "status": "completed",
                "candidates_count": len(candidates),
                "filename": original_filename,
            }

        except Exception as e:
            logger.error(f"Import job {job_id} failed: {e}")
            await self._update_job_status(job_id, "failed", error=str(e))
            return {**job_info, "error": str(e), "status": "failed"}

    async def _update_job_status(
        self,
        job_id: str,
        status: str,
        candidates_count: int = 0,
        error: Optional[str] = None,
    ):
        """Update job status.

        Args:
            job_id: Job ID
            status: New status
            candidates_count: Number of candidates
            error: Optional error message
        """
        import aiofiles
        import json

        job_file = self._get_job_file(job_id)
        job_info = {
            "job_id": job_id,
            "status": status,
            "candidates_count": candidates_count,
            "completed_at": datetime.utcnow().isoformat() if status in ("completed", "failed") else None,
            "error": error,
        }

        async with aiofiles.open(job_file, "w") as f:
            await f.write(json.dumps(job_info))

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status.

        Args:
            job_id: Job ID

        Returns:
            Job info or None if not found
        """
        import aiofiles
        import json

        job_file = self._get_job_file(job_id)
        if not job_file.exists():
            return None

        async with aiofiles.open(job_file, "r") as f:
            content = await f.read()
            return json.loads(content)

    async def get_pending_memories(
        self,
        job_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get pending memories.

        Args:
            job_id: Optional job ID filter
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with items and pagination info
        """
        import aiofiles
        import json

        pending_file = self._get_pending_file(job_id)
        if not pending_file.exists():
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            }

        memories = []
        async with aiofiles.open(pending_file, "r") as f:
            async for line in f:
                if line.strip():
                    try:
                        memories.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        total = len(memories)
        start = (page - 1) * page_size
        end = start + page_size
        items = memories[start:end]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    async def confirm_memories(
        self,
        memory_ids: List[str],
        memory_store: Any,
        memory_index: Any = None,
    ) -> Dict[str, Any]:
        """Confirm and save memories to long-term storage.

        Args:
            memory_ids: List of memory IDs to confirm
            memory_store: Memory store instance
            memory_index: Optional memory index for re-indexing

        Returns:
            Result with confirmed count
        """
        import aiofiles
        import json

        confirmed_count = 0

        # Read all pending memories
        pending_file = self._get_pending_file()
        if not pending_file.exists():
            return {"success": False, "confirmed_count": 0, "error": "No pending memories"}

        memories = []
        memory_map = {}

        async with aiofiles.open(pending_file, "r") as f:
            async for line in f:
                if line.strip():
                    try:
                        mem = json.loads(line)
                        memories.append(mem)
                        memory_map[mem["id"]] = mem
                    except json.JSONDecodeError:
                        pass

        # Process confirmations
        for mem_id in memory_ids:
            if mem_id in memory_map:
                mem = memory_map[mem_id]
                # Save to long-term memory
                await memory_store.append_long_term(
                    content=mem["text"],
                    title=mem.get("title", mem["text"][:50]),
                    tags=["imported", f"source:{mem.get('source_file', 'unknown')}"],
                    metadata={
                        "imported_from": mem.get("source_file", "unknown"),
                        "source_snippet": mem.get("source_snippet", ""),
                        "confidence": mem.get("confidence", 1.0),
                        "import_job_id": mem.get("import_job_id", ""),
                    },
                )
                confirmed_count += 1
                # Remove from memory_map
                del memory_map[mem_id]

        # Rewrite pending file with remaining memories
        async with aiofiles.open(pending_file, "w") as f:
            for mem in memories:
                if mem["id"] in memory_map:
                    await f.write(json.dumps(mem, ensure_ascii=False) + "\n")

        # Re-index if index provided
        if memory_index and confirmed_count > 0:
            try:
                await memory_index.index_user_memories()
            except Exception as e:
                logger.warning(f"Failed to re-index: {e}")

        return {"success": True, "confirmed_count": confirmed_count}

    async def reject_memories(self, memory_ids: List[str]) -> Dict[str, Any]:
        """Reject memories from pending list.

        Args:
            memory_ids: List of memory IDs to reject

        Returns:
            Result with rejected count
        """
        import aiofiles
        import json

        rejected_count = 0

        pending_file = self._get_pending_file()
        if not pending_file.exists():
            return {"success": False, "rejected_count": 0, "error": "No pending memories"}

        memories = []
        rejected_ids = set(memory_ids)

        async with aiofiles.open(pending_file, "r") as f:
            async for line in f:
                if line.strip():
                    try:
                        mem = json.loads(line)
                        if mem["id"] not in rejected_ids:
                            memories.append(mem)
                        else:
                            rejected_count += 1
                    except json.JSONDecodeError:
                        pass

        # Rewrite pending file
        async with aiofiles.open(pending_file, "w") as f:
            for mem in memories:
                await f.write(json.dumps(mem, ensure_ascii=False) + "\n")

        return {"success": True, "rejected_count": rejected_count}

    async def get_all_pending_count(self) -> int:
        """Get total count of all pending memories.

        Returns:
            Total count
        """
        import aiofiles
        import json

        count = 0
        pending_file = self._get_pending_file()

        if pending_file.exists():
            async with aiofiles.open(pending_file, "r") as f:
                async for line in f:
                    if line.strip():
                        count += 1

        return count
