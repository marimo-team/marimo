from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, cast

import pytest

from marimo._server.file_router import MarimoFileKey
from marimo._server.rtc.doc import LoroDocManager
from marimo._types.ids import CellId_t

if sys.version_info >= (3, 11) and sys.version_info < (3, 14):
    from loro import LoroDoc, LoroText

doc_manager = LoroDocManager()


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture  # type: ignore
async def setup_doc_manager() -> AsyncGenerator[None, None]:
    """Setup and teardown for loro_docs tests"""
    # Clear any existing loro docs
    doc_manager.loro_docs.clear()
    doc_manager.loro_docs_clients.clear()
    doc_manager._subscriptions.clear()
    yield
    # Cleanup after test
    doc_manager.loro_docs.clear()
    doc_manager.loro_docs_clients.clear()
    doc_manager._subscriptions.clear()


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_register_doc(setup_doc_manager: None) -> None:
    """Test registering a LoroDoc with the manager."""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()

    await doc_manager.register_doc(file_key, doc)

    assert file_key in doc_manager.loro_docs
    assert doc_manager.loro_docs[file_key] is doc
    assert file_key in doc_manager._subscriptions


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_register_doc_idempotent(setup_doc_manager: None) -> None:
    """Registering the same file_key twice keeps the first doc."""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc1 = LoroDoc()
    doc2 = LoroDoc()

    await doc_manager.register_doc(file_key, doc1)
    await doc_manager.register_doc(file_key, doc2)

    assert doc_manager.loro_docs[file_key] is doc1


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_get_doc(setup_doc_manager: None) -> None:
    """Test retrieving a registered doc."""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    await doc_manager.register_doc(file_key, doc)

    result = await doc_manager.get_doc(file_key)
    assert result is doc


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_get_doc_missing(setup_doc_manager: None) -> None:
    """Getting an unregistered doc raises KeyError."""
    del setup_doc_manager
    with pytest.raises(KeyError):
        await doc_manager.get_doc(MarimoFileKey("missing"))


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_two_users_sync(setup_doc_manager: None) -> None:
    """Test that two users can connect and sync text properly without duplicates"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    cell_id = str(CellId_t("test_cell"))  # Convert CellId to string for loro

    # Register the doc
    doc = LoroDoc()
    await doc_manager.register_doc(file_key, doc)

    # Setup client queues for both users
    queue1 = asyncio.Queue[bytes]()
    queue2 = asyncio.Queue[bytes]()
    doc_manager.add_client_to_doc(file_key, queue1)
    doc_manager.add_client_to_doc(file_key, queue2)

    # Get maps from doc
    doc_codes = doc.get_map("codes")
    doc_languages = doc.get_map("languages")

    # Add text to the doc using get_or_create_container
    code_text = doc_codes.get_or_create_container(cell_id, LoroText())
    code_text_typed = cast(LoroText, code_text)
    code_text_typed.insert(0, "print('hello')")

    lang_text = doc_languages.get_or_create_container(cell_id, LoroText())
    lang_text_typed = cast(LoroText, lang_text)
    lang_text_typed.insert(0, "python")

    # Verify state
    assert len(doc_manager.loro_docs) == 1
    assert len(doc_manager.loro_docs_clients[file_key]) == 2

    # Make sure we can get the text content
    assert code_text_typed.to_string() == "print('hello')"

    # Second user makes changes - no need to retrieve the text again
    code_text_typed.insert(
        len(code_text_typed.to_string()), "\nprint('world')"
    )

    # Verify changes propagate
    assert code_text_typed.to_string() == "print('hello')\nprint('world')"
    assert lang_text_typed.to_string() == "python"


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_concurrent_registration(setup_doc_manager: None) -> None:
    """Test concurrent doc registration doesn't cause issues"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()

    # Create multiple tasks that try to register the same doc
    tasks = [doc_manager.register_doc(file_key, doc) for _ in range(5)]
    await asyncio.gather(*tasks)

    # Only one doc should be registered
    assert len(doc_manager.loro_docs) == 1


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_concurrent_client_operations(
    setup_doc_manager: None,
) -> None:
    """Test concurrent client operations don't cause deadlocks"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    await doc_manager.register_doc(file_key, doc)

    # Create multiple client queues
    queues = [asyncio.Queue[bytes]() for _ in range(5)]
    doc_manager.loro_docs_clients[file_key] = set(queues)

    # Concurrently add and remove clients
    async def client_operation(queue: asyncio.Queue[bytes]) -> None:
        doc_manager.add_client_to_doc(file_key, queue)
        await asyncio.sleep(0.1)  # Simulate some work
        await doc_manager.remove_client(file_key, queue)

    tasks = [client_operation(queue) for queue in queues]
    await asyncio.gather(*tasks)

    # Verify final state
    assert len(doc_manager.loro_docs_clients[file_key]) == 0


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_broadcast_update(setup_doc_manager: None) -> None:
    """Test broadcast update functionality"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    await doc_manager.register_doc(file_key, doc)

    # Create multiple client queues
    queues = [asyncio.Queue[bytes]() for _ in range(3)]
    doc_manager.loro_docs_clients[file_key] = set(queues)

    # Broadcast a message
    message = b"test message"
    await doc_manager.broadcast_update(
        file_key, message, exclude_queue=queues[0]
    )

    # Verify all queues except excluded one received the message
    for i, queue in enumerate(queues):
        if i == 0:
            assert queue.empty()
        else:
            assert await queue.get() == message


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_local_update_broadcast(setup_doc_manager: None) -> None:
    """Server-side Loro mutations are broadcast to RTC clients."""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    await doc_manager.register_doc(file_key, doc)

    queue: asyncio.Queue[bytes] = asyncio.Queue()
    doc_manager.add_client_to_doc(file_key, queue)

    # Mutate the doc server-side (simulates SetCode via NotebookDocument)
    codes = doc.get_map("codes")
    text = codes.get_or_create_container("cell1", LoroText())
    text.insert(0, "x = 1")
    doc.commit()

    # The subscription should have enqueued the update
    assert not queue.empty()


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_remove_nonexistent_doc(setup_doc_manager: None) -> None:
    """Test removing a doc that doesn't exist"""
    del setup_doc_manager
    file_key = MarimoFileKey("nonexistent")
    await doc_manager.remove_doc(file_key)
    assert file_key not in doc_manager.loro_docs
    assert file_key not in doc_manager.loro_docs_clients
    assert file_key not in doc_manager._subscriptions


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_remove_nonexistent_client(setup_doc_manager: None) -> None:
    """Test removing a client that doesn't exist"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    queue = asyncio.Queue[bytes]()
    await doc_manager.remove_client(file_key, queue)
    assert file_key not in doc_manager.loro_docs_clients


@pytest.mark.skipif(
    "sys.version_info < (3, 11) or sys.version_info >= (3, 14)"
)
async def test_concurrent_doc_removal(setup_doc_manager: None) -> None:
    """Test concurrent doc removal doesn't cause issues"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    await doc_manager.register_doc(file_key, doc)

    # Create multiple tasks that try to remove the same doc
    tasks = [doc_manager.remove_doc(file_key) for _ in range(5)]
    await asyncio.gather(*tasks)

    # Verify doc was removed
    assert file_key not in doc_manager.loro_docs
    assert file_key not in doc_manager.loro_docs_clients
    assert file_key not in doc_manager._subscriptions
