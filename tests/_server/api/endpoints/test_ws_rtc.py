from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Optional, cast

import pytest
from loro import LoroDoc, LoroText

from marimo._config.manager import UserConfigManager
from marimo._messaging.ops import KernelCapabilities, KernelReady
from marimo._server.api.endpoints.ws import DOC_MANAGER
from marimo._server.file_router import MarimoFileKey
from marimo._types.ids import CellId_t
from marimo._utils.parse_dataclass import parse_raw
from tests._server.conftest import get_session_manager, get_user_config_manager
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.testclient import TestClient


def create_response(
    partial_response: dict[str, Any],
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "cell_ids": ["Hbol"],
        "codes": ["import marimo as mo"],
        "names": ["__"],
        "layout": None,
        "resumed": False,
        "ui_values": {},
        "last_executed_code": {},
        "last_execution_time": {},
        "kiosk": False,
        "configs": [{"disabled": False, "hide_code": False}],
        "app_config": {"width": "full"},
        "capabilities": asdict(KernelCapabilities()),
    }
    response.update(partial_response)
    return response


def headers(session_id: str) -> dict[str, str]:
    return {
        "Marimo-Session-Id": session_id,
        **token_header("fake-token"),
    }


HEADERS = {
    **token_header("fake-token"),
}


def assert_kernel_ready_response(
    raw_data: dict[str, Any], response: Optional[dict[str, Any]] = None
) -> None:
    if response is None:
        response = create_response({})
    data = parse_raw(raw_data["data"], KernelReady)
    expected = parse_raw(response, KernelReady)
    assert data.cell_ids == expected.cell_ids
    assert data.codes == expected.codes
    assert data.names == expected.names
    assert data.layout == expected.layout
    assert data.resumed == expected.resumed
    assert data.ui_values == expected.ui_values
    assert data.configs == expected.configs
    assert data.app_config == expected.app_config
    assert data.kiosk == expected.kiosk
    assert data.capabilities == expected.capabilities


def assert_parse_ready_response(raw_data: dict[str, Any]) -> None:
    data = parse_raw(raw_data["data"], KernelReady)
    assert data is not None


@pytest.fixture  # type: ignore
async def setup_loro_docs() -> AsyncGenerator[None, None]:
    """Setup and teardown for loro_docs tests"""
    # Clear any existing loro docs
    DOC_MANAGER.loro_docs.clear()
    DOC_MANAGER.loro_docs_clients.clear()
    DOC_MANAGER.loro_docs_cleaners.clear()
    yield
    # Cleanup after test
    DOC_MANAGER.loro_docs.clear()
    DOC_MANAGER.loro_docs_clients.clear()
    DOC_MANAGER.loro_docs_cleaners.clear()


async def test_quick_reconnection(setup_loro_docs: None) -> None:
    """Test that quick reconnection properly handles cleanup task cancellation"""
    del setup_loro_docs
    # Setup
    file_key = MarimoFileKey("test_file")

    # Create initial loro_doc
    doc = LoroDoc()
    DOC_MANAGER.loro_docs[file_key] = doc

    # Setup client queue
    update_queue = asyncio.Queue[bytes]()
    DOC_MANAGER.loro_docs_clients[file_key] = {update_queue}

    # Start cleanup task
    cleanup_task = asyncio.create_task(DOC_MANAGER._clean_loro_doc(file_key))

    # Simulate quick reconnection by creating a new client before cleanup finishes
    new_queue = asyncio.Queue[bytes]()
    DOC_MANAGER.loro_docs_clients[file_key].add(new_queue)

    # Cancel cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Verify state
    assert len(DOC_MANAGER.loro_docs) == 1
    assert (
        len(DOC_MANAGER.loro_docs_clients[file_key]) == 2
    )  # Original client + reconnected client


async def test_two_users_sync(setup_loro_docs: None) -> None:
    """Test that two users can connect and sync text properly without duplicates"""
    del setup_loro_docs
    file_key = MarimoFileKey("test_file")
    cell_id = str(CellId_t("test_cell"))  # Convert CellId to string for loro

    # First user connects
    doc = LoroDoc()
    DOC_MANAGER.loro_docs[file_key] = doc

    # Setup client queues for both users
    queue1 = asyncio.Queue[bytes]()
    queue2 = asyncio.Queue[bytes]()
    DOC_MANAGER.loro_docs_clients[file_key] = {queue1, queue2}

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
    assert len(DOC_MANAGER.loro_docs) == 1
    assert len(DOC_MANAGER.loro_docs_clients[file_key]) == 2

    # Make sure we can get the text content
    assert code_text_typed.to_string() == "print('hello')"

    # Second user makes changes - no need to retrieve the text again
    code_text_typed.insert(
        len(code_text_typed.to_string()), "\nprint('world')"
    )

    # Verify changes propagate
    assert code_text_typed.to_string() == "print('hello')\nprint('world')"
    assert lang_text_typed.to_string() == "python"


@contextmanager
def rtc_enabled(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config({"experimental": {"rtc_v2": True}})
        yield
    finally:
        config.save_config(prev_config)


async def test_loro_sync(client: TestClient) -> None:
    """Test that Loro-CRDT sync works between multiple clients"""
    # Set up unique websocket paths for each client
    ws_1 = "/ws?session_id=123"
    ws_2 = "/ws?session_id=456"

    # Set up unique synchronization websocket paths for each client
    ws_1_sync = "/ws_sync?session_id=123"
    ws_2_sync = "/ws_sync?session_id=456"

    # First connect main websockets to create sessions
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect(ws_1) as websocket1,
        client.websocket_connect(ws_2) as websocket2,
    ):
        # Verify both websockets received kernel ready messages
        data1 = websocket1.receive_json()
        assert_kernel_ready_response(data1)
        data2 = websocket2.receive_json()
        assert_parse_ready_response(data2)

        # Connect first client to sync websocket
        with client.websocket_connect(ws_1_sync) as sync_ws1:
            # Should receive initial sync message (binary data)
            sync_msg1 = sync_ws1.receive_bytes()
            # Loro sends binary data directly
            assert len(sync_msg1) > 0

            # Connect second client to sync websocket
            with client.websocket_connect(ws_2_sync) as sync_ws2:
                # Should receive initial sync message (binary data)
                sync_msg2 = sync_ws2.receive_bytes()
                assert len(sync_msg2) > 0

                # Verify both clients received initial sync data
                assert len(sync_msg1) > 0
                assert len(sync_msg2) > 0

    # Clean up by shutting down the kernel
    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_loro_cleanup_on_session_close(
    client: TestClient,
) -> None:
    """Test that cell websockets are cleaned up when session closes"""
    from loro import ExportMode, LoroDoc

    # Create a LoroDoc for the cell content
    doc = LoroDoc()
    initial_code = doc.export(ExportMode.Snapshot())

    file_key = get_session_manager(client).file_router.get_unique_file_key()
    assert file_key is not None

    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect("/ws?session_id=123") as websocket,
    ):
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Connect to cell websocket
        with client.websocket_connect("/ws_sync?session_id=123") as cell_ws:
            sync_msg = cell_ws.receive_bytes()
            assert len(sync_msg) > 0

            assert file_key in DOC_MANAGER.loro_docs_clients
            assert len(DOC_MANAGER.loro_docs_clients[file_key]) == 1

            # Close main websocket
            websocket.close()

            # Give the server some time to process the disconnection
            await asyncio.sleep(1.5)

            try:
                cell_ws.send_bytes(initial_code)
            except Exception:
                pass

    assert len(DOC_MANAGER.loro_docs_clients[file_key]) == 0

    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_loro_persistence(client: TestClient) -> None:
    """Test that cell content persists between connections"""
    from loro import ExportMode, LoroDoc

    # Create a LoroDoc for the cell content
    doc = LoroDoc()
    initial_code = doc.export(ExportMode.Snapshot())

    # First connection sets initial code
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect("/ws?session_id=123") as websocket,
    ):
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        with client.websocket_connect("/ws_sync?session_id=123") as cell_ws1:
            sync_msg = cell_ws1.receive_bytes()
            assert len(sync_msg) > 0

            # Send initial code update
            # In Loro, we send the binary snapshot directly
            cell_ws1.send_bytes(initial_code)

            # Allow time for the update to be processed
            await asyncio.sleep(0.2)

    # Allow some time for cleanup between sessions
    await asyncio.sleep(0.2)

    # Second connection should receive persisted code
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect("/ws?session_id=456") as websocket,
    ):
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({"resumed": True}))

        with client.websocket_connect("/ws_sync?session_id=456") as cell_ws2:
            sync_msg = cell_ws2.receive_bytes()
            # Verify initial sync contains data
            assert len(sync_msg) > 0

    client.post("/api/kernel/shutdown", headers=HEADERS)
