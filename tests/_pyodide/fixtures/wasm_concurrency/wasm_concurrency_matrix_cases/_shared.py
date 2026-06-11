# Copyright 2026 Marimo. All rights reserved.
"""Shared state and helpers for the WASM concurrency matrix."""

# ruff: noqa: F401, I001

import asyncio
import concurrent.futures
import contextvars
import inspect
import json
import logging
import marimo as mo
import queue
import sys
import threading
from concurrent.futures import CancelledError
from js import (
    marimoWasmConcurrencyDelay,
    marimoWasmConcurrencyMessages,
)
from pyodide.ffi import run_sync

matrix = []

COOPERATIVE_TIMEOUT = 0.25
TIMER_DELAY = 0.05
TIMER_DELAY_MS = max(1, int(TIMER_DELAY * 1000))


def record(case_id, tier):
    matrix.append(
        {
            "id": case_id,
            "tier": tier,
        }
    )


def assert_run_sync_not_called(action):
    import pyodide.ffi as pyodide_ffi

    original_run_sync = pyodide_ffi.run_sync

    def forbidden_run_sync(_awaitable):
        raise AssertionError("immediate timeout called pyodide.ffi.run_sync")

    pyodide_ffi.run_sync = forbidden_run_sync
    try:
        return action()
    finally:
        pyodide_ffi.run_sync = original_run_sync


def start_delayed_thread(label, action):
    async def delayed_action():
        await marimoWasmConcurrencyDelay(label, TIMER_DELAY_MS)
        action()

    thread = threading.Thread(
        target=delayed_action,
        name=f"{label}-delay",
    )
    thread.start()
    return thread


CURRENT_GROUP = None
FAILURE_WRITTEN = False
FAILURE_PATH = "/home/pyodide/wasm_concurrency_matrix_failure.json"
RESULT_PATH = "/home/pyodide/wasm_concurrency_matrix_result.json"


def write_matrix_failure(group, error):
    global FAILURE_WRITTEN

    import traceback

    failure = {
        "group": group,
        "error_type": type(error).__name__,
        "error": str(error),
        "traceback": traceback.format_exc(),
        "partial_rows": matrix,
    }
    with open(FAILURE_PATH, "w", encoding="utf-8") as f:
        json.dump(failure, f, indent=2)
    FAILURE_WRITTEN = True


def assert_unique_matrix_rows():
    seen_case_ids = [row["id"] for row in matrix]
    duplicate_case_ids = sorted(
        {
            case_id
            for case_id in seen_case_ids
            if seen_case_ids.count(case_id) > 1
        }
    )
    assert not duplicate_case_ids, duplicate_case_ids


def write_matrix_result():
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=2)
