"""Tests for memory store module."""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.core.config import Settings
from src.core.memory_store import MemoryStore


@pytest.fixture
def temp_settings():
    """Create temporary settings for testing."""
    settings = Settings()
    settings.storage.base_dir = tempfile.mkdtemp()
    return settings


@pytest.fixture
def store(temp_settings):
    """Create memory store for testing."""
    return MemoryStore("test-user", temp_settings)


@pytest.mark.asyncio
async def test_append_short_term(store):
    """Test appending to short-term log."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    entry_id = await store.append_short_term(messages, session_id="test-session")

    assert entry_id is not None
    assert len(entry_id) > 0


@pytest.mark.asyncio
async def test_read_short_term(store):
    """Test reading short-term log."""
    messages = [
        {"role": "user", "content": "Test message"},
    ]
    await store.append_short_term(messages, session_id="test-session")

    entries = await store.read_short_term(limit=10, session_id="test-session")
    assert len(entries) > 0
    assert entries[0]["messages"][0]["content"] == "Test message"


@pytest.mark.asyncio
async def test_append_long_term(store):
    """Test appending long-term memory."""
    memory_id = await store.append_long_term(
        content="This is a test memory",
        title="Test Memory",
        tags=["test", "sample"],
    )

    assert memory_id is not None
    assert len(memory_id) > 0


@pytest.mark.asyncio
async def test_read_long_term(store):
    """Test reading long-term memory."""
    await store.append_long_term(
        content="Test content",
        title="Test Title",
        tags=["test"],
    )

    memories = await store.read_long_term(limit=10)
    assert len(memories) > 0


@pytest.mark.asyncio
async def test_list_memories(store):
    """Test listing memories."""
    await store.append_long_term(
        content="Memory 1",
        title="First",
        tags=["test"],
    )
    await store.append_long_term(
        content="Memory 2",
        title="Second",
        tags=["test"],
    )

    memories = await store.list_memories(include_content=False)
    assert len(memories) >= 2


@pytest.mark.asyncio
async def test_log_operation(store):
    """Test operation logging."""
    entry_id = await store.log_operation(
        "test_operation",
        {"key": "value"},
    )

    assert entry_id is not None

    logs = await store.get_operations(operation="test_operation")
    assert len(logs) > 0
    assert logs[0]["operation"] == "test_operation"


@pytest.mark.asyncio
async def test_delete_memory(store):
    """Test deleting memory."""
    memory_id = await store.append_long_term(
        content="To be deleted",
        title="Delete Me",
    )

    deleted = await store.delete_memory(memory_id)
    assert deleted is True
