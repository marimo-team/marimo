"""marimo cell body for the Pyodide WASM concurrency matrix.

The Node JSPI harness injects this file into a generated notebook cell. The
cell runs in Pyodide with `marimoWasmConcurrency*` JS
globals, uses top-level `await`, and writes JSON rows to
`/home/pyodide/wasm_concurrency_matrix_result.json`.
The JS harness owns the required-row and tier manifest.
"""

# ruff: noqa: F704, PLE1142

import asyncio
import json
import sys

import marimo as mo

if "/home/pyodide" not in sys.path:
    sys.path.insert(0, "/home/pyodide")

from wasm_concurrency_matrix_cases import _shared as shared
from wasm_concurrency_matrix_cases.futures_cases import run_futures_cases
from wasm_concurrency_matrix_cases.marimo_thread_cases import (
    run_marimo_thread_cases,
)
from wasm_concurrency_matrix_cases.process_cases import (
    run_process_shaped_cases,
)
from wasm_concurrency_matrix_cases.stress_cases import run_stress_cases
from wasm_concurrency_matrix_cases.threading_cases import (
    run_threading_and_queue_cases,
)


async def run_group(name, action) -> None:
    shared.CURRENT_GROUP = name
    try:
        await action()
    except BaseException as error:
        shared.write_matrix_failure(name, error)
        raise
    finally:
        shared.CURRENT_GROUP = None


def stdout_messages_since(message_index):
    messages = []
    for raw_message in shared.marimoWasmConcurrencyMessages.to_py()[
        message_index:
    ]:
        message = json.loads(raw_message)
        if message.get("op") != "cell-op":
            continue
        payload = message.get("data") or {}
        console = payload.get("console")
        console_outputs = console if isinstance(console, list) else [console]
        for output in console_outputs:
            if isinstance(output, dict) and output.get("channel") == "stdout":
                messages.append(
                    {
                        "cell_id": payload.get("cell_id"),
                        "data": output.get("data", ""),
                    }
                )
    return messages


async def run_notebook_cell_thread_cases() -> None:
    print_marker = "mo.Thread print routed through Pyodide"
    message_index = len(shared.marimoWasmConcurrencyMessages)

    def print_worker():
        print(print_marker)

    print_thread = mo.Thread(target=print_worker, name="print-worker")
    print_thread.start()
    print_thread.join(1)
    assert not print_thread.is_alive()

    def matrix_cell_print_messages():
        return [
            message
            for message in stdout_messages_since(message_index)
            if message["cell_id"] == "wasm-concurrency-matrix"
            and print_marker in message["data"]
        ]

    for _ in range(20):
        if matrix_cell_print_messages():
            break
        await asyncio.sleep(0.01)
    assert matrix_cell_print_messages()
    shared.record("marimo_thread.print_routes_console", "api-compatible")


async def run_runtime_and_install_cases() -> None:
    async def _jspi_probe():
        return shared.run_sync(
            shared.marimoWasmConcurrencyDelay("cell-task", 1)
        )

    assert await asyncio.create_task(_jspi_probe()) == "cell-task"
    shared.record("runtime.jspi_run_sync_in_cell_task", "api-compatible")

    import concurrent.futures
    import multiprocessing
    import threading

    bootstrapped_values = multiprocessing.Queue()

    def bootstrapped_process_target(output):
        output.put("bootstrapped-process")

    bootstrapped_process = multiprocessing.Process(
        target=bootstrapped_process_target,
        args=(bootstrapped_values,),
    )
    bootstrapped_process.start()
    bootstrapped_process.join(timeout=1)
    assert not bootstrapped_process.is_alive()
    assert bootstrapped_process.exitcode == 0
    assert bootstrapped_values.get(block=False) == "bootstrapped-process"

    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
        assert (
            executor.submit(str, "bootstrapped-executor").result(timeout=1)
            == "bootstrapped-executor"
        )
    shared.record("install.process_shaped_bootstrapped", "serialized")

    install_thread_records = []

    def install_thread_probe():
        install_thread_records.append(threading.current_thread().name)

    install_thread = threading.Thread(
        target=install_thread_probe, name="install-probe"
    )
    install_thread.start()
    install_thread.join(1)
    assert install_thread_records == ["install-probe"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(lambda: "executor-ok").result(timeout=1) == (
            "executor-ok"
        )

    marimo_thread_records = []

    def marimo_thread_probe():
        current = mo.current_thread()
        marimo_thread_records.append((current.name, current.should_exit))

    marimo_probe = mo.Thread(
        target=marimo_thread_probe,
        name="marimo-install-probe",
    )
    marimo_probe.start()
    marimo_probe.join(1)
    assert marimo_thread_records == [("marimo-install-probe", False)]
    shared.record("install.shim_before_user_cell", "api-compatible")
    shared.record("marimo_thread.bootstrap_current_thread", "api-compatible")


try:
    await run_group("runtime_and_install", run_runtime_and_install_cases)
    await run_group("threading_and_queue", run_threading_and_queue_cases)
    await run_group(
        "notebook_cell_thread",
        run_notebook_cell_thread_cases,
    )
    await run_group("marimo_thread", run_marimo_thread_cases)
    await run_group("futures", run_futures_cases)
    await run_group("process_shaped", run_process_shaped_cases)
    await run_group("stress", run_stress_cases)
except BaseException as error:
    if not shared.FAILURE_WRITTEN:
        shared.write_matrix_failure(
            shared.CURRENT_GROUP or "matrix_teardown", error
        )
    raise

try:
    shared.assert_unique_matrix_rows()
    shared.write_matrix_result()
except BaseException as error:
    shared.write_matrix_failure(shared.CURRENT_GROUP or "matrix_result", error)
    raise
