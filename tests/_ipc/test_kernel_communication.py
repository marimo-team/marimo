"""Tests for ZeroMQ-based kernel communication."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import time

import pytest
from dirty_equals import IsFloat, IsList, IsUUID

from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.requests import (
    AppMetadata,
    ExecuteMultipleRequest,
)
from marimo._types.ids import CellId_t

HAS_DEPS = DependencyManager.has("zmq")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_kernel_launch_and_execute_cells():
    """Test launching a kernel and executing cells with stdout/stderr."""
    from marimo._ipc import KernelArgs, QueueManager

    execute_request = ExecuteMultipleRequest(
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

    test_request = ExecuteMultipleRequest(
        cell_ids=[CellId_t("cell1")],
        codes=["print('test')"],
    )
    host_manager.control_queue.put(test_request)
    assert client_manager.control_queue.get(timeout=1) == test_request

    kernel_message = ("test-op", b'{"data": "test"}')
    client_manager.stream_queue.put(kernel_message)
    assert host_manager.stream_queue.get(timeout=1) == kernel_message

    host_manager.close_queues()
    client_manager.close_queues()
