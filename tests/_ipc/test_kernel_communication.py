"""Tests for ZeroMQ-based kernel communication."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import time

import msgspec
import pytest
from dirty_equals import IsFloat, IsList, IsUUID

from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.commands import (
    AppMetadata,
    BatchableCommand,
    CodeCompletionCommand,
    CommandMessage,
    ExecuteCellsCommand,
    HTTPRequest,
    ModelCommand,
    ModelUpdateMessage,
    UpdateUIElementCommand,
)
from marimo._types.ids import CellId_t

HAS_DEPS = DependencyManager.has("zmq")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.skip(reason="TODO: fix this test. Currently flaky on CI.")
def test_kernel_launch_and_execute_cells():
    """Test launching a kernel and executing cells with stdout/stderr."""
    from marimo._ipc import KernelArgs, QueueManager

    execute_request = ExecuteCellsCommand(
        cell_ids=[CellId_t("cell1")],
        codes=[
            """\
import sys
print("stdout")
print("stderr", file=sys.stderr)
x = 42"""
        ],
    )

    queue_manager, connection_info = QueueManager.create()
    kernel_args = KernelArgs(
        connection_info=connection_info,
        profile_path=None,
        configs={cid: CellConfig() for cid in execute_request.cell_ids},
        user_config=DEFAULT_CONFIG,
        log_level=GLOBAL_SETTINGS.LOG_LEVEL,
        app_metadata=AppMetadata(
            query_params={}, cli_args={}, app_config=_AppConfig()
        ),
    )

    # IMPORTANT: The module path "marimo._ipc.launch_kernel" is a public API
    # used by external consumers (e.g., marimo-lsp). Changing this path is a
    # BREAKING CHANGE and should be done with care and proper deprecation.
    process = subprocess.Popen(
        [sys.executable, "-m", "marimo._ipc.launch_kernel"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert process.stdin is not None
    process.stdin.write(kernel_args.encode_json())
    process.stdin.flush()
    process.stdin.close()

    assert process.stdout is not None
    assert process.stderr is not None

    ready_line = process.stdout.readline().decode("utf-8").strip()

    if ready_line != "KERNEL_READY":
        exit_code = process.poll()
        stderr_content = process.stderr.read().decode("utf-8")
        if exit_code is not None and exit_code != 0:
            raise RuntimeError(
                f"Kernel process failed with exit code {exit_code}. Stderr: {stderr_content}"
            )
        else:
            raise RuntimeError(
                f"Expected KERNEL_READY, got: '{ready_line}'. Stderr: {stderr_content}"
            )

    queue_manager.control_queue.put(execute_request)

    messages = []
    seen_completed = False
    extra_collection_start = None

    while True:
        try:
            encoded = queue_manager.stream_queue.get(timeout=0.01)
            decoded = json.loads(encoded)
            messages.append(decoded)

            if decoded["op"] == "completed-run":
                seen_completed = True
                extra_collection_start = time.time()

        except queue.Empty:
            if seen_completed and extra_collection_start is not None:
                # FIXME: stdin/stdout are flushed every 10ms, so wait 100ms
                # (after "completed-run") to ensure all related events.
                if time.time() - extra_collection_start >= 0.1:
                    break

            # If we haven't seen completed-run yet, continue waiting
            continue

    assert messages == [
        {
            "op": "variables",
            "variables": IsList(
                {
                    "declared_by": [
                        "cell1",
                    ],
                    "name": "x",
                    "used_by": [],
                },
                {
                    "declared_by": [
                        "cell1",
                    ],
                    "name": "sys",
                    "used_by": [],
                },
                check_order=False,
            ),
        },
        {
            "cell_id": "cell1",
            "console": None,
            "op": "cell-op",
            "output": None,
            "run_id": IsUUID(),
            "serialization": None,
            "stale_inputs": None,
            "status": "queued",
            "timestamp": IsFloat(),
        },
        {
            "cell_id": "cell1",
            "op": "remove-ui-elements",
        },
        {
            "cell_id": "cell1",
            "console": [],
            "op": "cell-op",
            "output": None,
            "run_id": IsUUID(),
            "serialization": None,
            "stale_inputs": None,
            "status": "running",
            "timestamp": IsFloat(),
        },
        {
            "op": "variable-values",
            "variables": IsList(
                {
                    "datatype": "int",
                    "name": "x",
                    "value": "42",
                },
                {
                    "datatype": "module",
                    "name": "sys",
                    "value": "sys",
                },
                check_order=False,
            ),
        },
        {
            "cell_id": "cell1",
            "console": None,
            "op": "cell-op",
            "output": {
                "channel": "output",
                "data": "",
                "mimetype": "text/plain",
                "timestamp": IsFloat(),
            },
            "run_id": IsUUID(),
            "serialization": None,
            "stale_inputs": None,
            "status": None,
            "timestamp": IsFloat(),
        },
        {
            "cell_id": "cell1",
            "console": None,
            "op": "cell-op",
            "output": None,
            "run_id": None,
            "serialization": None,
            "stale_inputs": None,
            "status": "idle",
            "timestamp": IsFloat(),
        },
        {
            "op": "completed-run",
        },
        {
            "cell_id": "cell1",
            "console": {
                "channel": "stdout",
                "data": "stdout\n",
                "mimetype": "text/plain",
                "timestamp": IsFloat(),
            },
            "op": "cell-op",
            "output": None,
            "run_id": None,
            "serialization": None,
            "stale_inputs": None,
            "status": None,
            "timestamp": IsFloat(),
        },
        {
            "cell_id": "cell1",
            "console": {
                "channel": "stderr",
                "data": "stderr\n",
                "mimetype": "text/plain",
                "timestamp": IsFloat(),
            },
            "op": "cell-op",
            "output": None,
            "run_id": None,
            "serialization": None,
            "stale_inputs": None,
            "status": None,
            "timestamp": IsFloat(),
        },
    ]

    process.terminate()
    process.wait(timeout=2)
    queue_manager.close_queues()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_queue_manager_connection():
    """Test creating and connecting queue managers."""
    from marimo._ipc import QueueManager

    host_manager, connection_info = QueueManager.create()
    client_manager = QueueManager.connect(connection_info)

    test_request = ExecuteCellsCommand(
        cell_ids=[CellId_t("cell1")],
        codes=["print('test')"],
    )
    host_manager.control_queue.put(test_request)
    assert client_manager.control_queue.get(timeout=1) == test_request

    kernel_message = b'{"op": "test-op", "data": "test"}'
    client_manager.stream_queue.put(kernel_message)
    assert host_manager.stream_queue.get(timeout=1) == kernel_message

    host_manager.close_queues()
    client_manager.close_queues()


class TestMsgpackIPC:
    """Test msgspec msgpack serialization for IPC channels.

    Each IPC channel has a specific type that must survive encode/decode.
    These tests mirror the channel types in Connection.create/connect:

        control:         CommandMessage (discriminated union)
        ui_element:      BatchableCommand (discriminated union)
        completion:      CodeCompletionCommand
        input:           str
        win32_interrupt: bool
        stream:          bytes
    """

    def test_control_channel(self) -> None:
        """CommandMessage union dispatches to the correct subtype."""
        cmd = ExecuteCellsCommand(cell_ids=["c1"], codes=["x=1"])
        encoded = msgspec.msgpack.encode(cmd)
        decoded = msgspec.msgpack.Decoder(CommandMessage).decode(encoded)
        assert decoded == cmd

    def test_control_channel_with_http_request(self) -> None:
        """HTTPRequest (a @dataclass) survives the round-trip as a nested field."""
        req = HTTPRequest(
            url={"path": "/run"},
            base_url={"path": "/"},
            headers={"content-type": "application/json"},
            query_params={"key": ["val1", "val2"]},
            path_params={},
            cookies={},
            meta={},
            user={},
        )
        cmd = ExecuteCellsCommand(cell_ids=["c1"], codes=["x=1"], request=req)
        encoded = msgspec.msgpack.encode(cmd)
        decoded = msgspec.msgpack.Decoder(CommandMessage).decode(encoded)
        assert decoded.request is not None
        assert decoded.request["url"]["path"] == "/run"
        assert decoded.request["query_params"]["key"] == ["val1", "val2"]

    def test_ui_element_channel(self) -> None:
        """BatchableCommand union round-trips both member types."""
        ui = UpdateUIElementCommand(
            object_ids=["e1"], values=[{"nested": [1, 2]}], token="tok"
        )
        encoded = msgspec.msgpack.encode(ui)
        assert msgspec.msgpack.Decoder(BatchableCommand).decode(encoded) == ui

        msg = ModelUpdateMessage(state={"k": "v"}, buffer_paths=[])
        model = ModelCommand(
            model_id="m1", message=msg, buffers=[b"buf"], token="tok"
        )
        encoded = msgspec.msgpack.encode(model)
        assert (
            msgspec.msgpack.Decoder(BatchableCommand).decode(encoded) == model
        )

    def test_completion_channel(self) -> None:
        cmd = CodeCompletionCommand(id="t", document="x = 1", cell_id="c1")
        encoded = msgspec.msgpack.encode(cmd)
        decoded = msgspec.msgpack.Decoder(CodeCompletionCommand).decode(
            encoded
        )
        assert decoded == cmd

    def test_primitive_channels(self) -> None:
        """str (input), bool (win32_interrupt), and bytes (stream) channels."""
        for value, typ in [
            ("user_input", str),
            (True, bool),
            (b'{"op": "cell-op"}', bytes),
        ]:
            encoded = msgspec.msgpack.encode(value)
            assert msgspec.msgpack.Decoder(typ).decode(encoded) == value

    def test_unknown_fields_are_ignored(self) -> None:
        """Decoder silently drops fields it doesn't recognize.

        This matters when the sender is newer than the receiver (e.g.
        a field was added to a command). msgspec must not reject the
        message — it should decode the known fields and discard the rest.
        """

        # A "V2" struct with the same tag but an extra field
        class ExecuteCellsCommandV2(
            msgspec.Struct,
            rename="camel",
            tag_field="type",
            tag="execute-cells",
        ):
            cell_ids: list[str]
            codes: list[str]
            new_field: str = "added_later"

        v2 = ExecuteCellsCommandV2(
            cell_ids=["c1"], codes=["x=1"], new_field="extra"
        )
        encoded = msgspec.msgpack.encode(v2)

        decoded = msgspec.msgpack.Decoder(CommandMessage).decode(encoded)
        assert type(decoded) is ExecuteCellsCommand
        assert decoded.cell_ids == ["c1"]
        assert decoded.codes == ["x=1"]

    def test_missing_optional_fields_get_defaults(self) -> None:
        """Decoder fills in defaults for fields the sender didn't include.

        This matters when the receiver is newer than the sender (e.g.
        a field was added with a default, but the sender hasn't been
        updated yet).
        """

        class ExecuteCellsCommandV2(
            msgspec.Struct,
            rename="camel",
            tag_field="type",
            tag="execute-cells",
        ):
            cell_ids: list[str]
            codes: list[str]
            new_field: str = "default_value"

        old = ExecuteCellsCommand(cell_ids=["c1"], codes=["x=1"])
        encoded = msgspec.msgpack.encode(old)

        decoded = msgspec.msgpack.Decoder(ExecuteCellsCommandV2).decode(
            encoded
        )
        assert decoded.cell_ids == ["c1"]
        assert decoded.new_field == "default_value"
