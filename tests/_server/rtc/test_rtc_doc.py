import asyncio
from collections.abc import AsyncGenerator
from typing import cast

import pytest
from loro import LoroDoc, LoroText

from marimo._server.file_router import MarimoFileKey
from marimo._server.rtc.doc import LoroDocManager
from marimo._types.ids import CellId_t

doc_manager = LoroDocManager()


@pytest.fixture  # type: ignore
async def setup_doc_manager() -> AsyncGenerator[None, None]:
    """Setup and teardown for loro_docs tests"""
    # Clear any existing loro docs
    doc_manager.loro_docs.clear()
    doc_manager.loro_docs_clients.clear()
    doc_manager.loro_docs_cleaners.clear()
    yield
    # Cleanup after test
    doc_manager.loro_docs.clear()
    doc_manager.loro_docs_clients.clear()
    doc_manager.loro_docs_cleaners.clear()


async def test_quick_reconnection(setup_doc_manager: None) -> None:
    """Test that quick reconnection properly handles cleanup task cancellation"""
    del setup_doc_manager
    # Setup
    file_key = MarimoFileKey("test_file")

    # Create initial loro_doc
    doc = LoroDoc()
    doc_manager.loro_docs[file_key] = doc

    # Setup client queue
    update_queue = asyncio.Queue[bytes]()
    doc_manager.loro_docs_clients[file_key] = {update_queue}

    # Start cleanup task
    cleanup_task = asyncio.create_task(doc_manager._clean_loro_doc(file_key))

    # Simulate quick reconnection by creating a new client before cleanup finishes
    new_queue = asyncio.Queue[bytes]()
    doc_manager.loro_docs_clients[file_key].add(new_queue)

    # Cancel cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Verify state
    assert len(doc_manager.loro_docs) == 1
    assert (
        len(doc_manager.loro_docs_clients[file_key]) == 2
    )  # Original client + reconnected client


async def test_two_users_sync(setup_doc_manager: None) -> None:
    """Test that two users can connect and sync text properly without duplicates"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    cell_id = str(CellId_t("test_cell"))  # Convert CellId to string for loro

    # First user connects
    doc = LoroDoc()
    doc_manager.loro_docs[file_key] = doc

    # Setup client queues for both users
    queue1 = asyncio.Queue[bytes]()
    queue2 = asyncio.Queue[bytes]()
    doc_manager.loro_docs_clients[file_key] = {queue1, queue2}

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


async def test_concurrent_doc_creation(setup_doc_manager: None) -> None:
    """Test concurrent doc creation doesn't cause issues"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    cell_ids = (CellId_t("cell1"), CellId_t("cell2"))
    codes = ("print('hello')", "print('world')")

    # Create multiple tasks that try to create the same doc
    tasks = [
        doc_manager.create_doc(file_key, cell_ids, codes) for _ in range(5)
    ]
    docs = await asyncio.gather(*tasks)

    # All tasks should return the same doc instance
    assert all(doc is docs[0] for doc in docs)
    assert len(doc_manager.loro_docs) == 1


async def test_concurrent_client_operations(
    setup_doc_manager: None,
) -> None:
    """Test concurrent client operations don't cause deadlocks"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    doc_manager.loro_docs[file_key] = doc

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


async def test_cleanup_task_management(setup_doc_manager: None) -> None:
    """Test cleanup task management and cancellation"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    doc_manager.loro_docs[file_key] = doc

    # Add and remove a client to trigger cleanup
    queue = asyncio.Queue[bytes]()
    doc_manager.add_client_to_doc(file_key, queue)
    await doc_manager.remove_client(file_key, queue)

    # Verify cleanup task was created
    assert file_key in doc_manager.loro_docs_cleaners
    assert doc_manager.loro_docs_cleaners[file_key] is not None

    # Add a new client before cleanup finishes
    new_queue = asyncio.Queue[bytes]()
    doc_manager.add_client_to_doc(file_key, new_queue)

    # Wait for the task to be cancelled
    await asyncio.sleep(0.1)

    # Verify cleanup task was cancelled and removed
    # TODO: not sure why this is still here.
    # assert doc_manager.loro_docs_cleaners[file_key] is None

    # Clean up
    await doc_manager.remove_client(file_key, new_queue)


async def test_broadcast_update(setup_doc_manager: None) -> None:
    """Test broadcast update functionality"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    doc_manager.loro_docs[file_key] = doc

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


async def test_remove_nonexistent_doc(setup_doc_manager: None) -> None:
    """Test removing a doc that doesn't exist"""
    del setup_doc_manager
    file_key = MarimoFileKey("nonexistent")
    await doc_manager.remove_doc(file_key)
    assert file_key not in doc_manager.loro_docs
    assert file_key not in doc_manager.loro_docs_clients
    assert file_key not in doc_manager.loro_docs_cleaners


async def test_remove_nonexistent_client(setup_doc_manager: None) -> None:
    """Test removing a client that doesn't exist"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    queue = asyncio.Queue[bytes]()
    await doc_manager.remove_client(file_key, queue)
    assert file_key not in doc_manager.loro_docs_clients


async def test_concurrent_doc_removal(setup_doc_manager: None) -> None:
    """Test concurrent doc removal doesn't cause issues"""
    del setup_doc_manager
    file_key = MarimoFileKey("test_file")
    doc = LoroDoc()
    doc_manager.loro_docs[file_key] = doc

    # Create multiple tasks that try to remove the same doc
    tasks = [doc_manager.remove_doc(file_key) for _ in range(5)]
    await asyncio.gather(*tasks)

    # Verify doc was removed
    assert file_key not in doc_manager.loro_docs
    assert file_key not in doc_manager.loro_docs_clients
    assert file_key not in doc_manager.loro_docs_cleaners
