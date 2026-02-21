# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from uuid import uuid4


def is_windows() -> bool:
    return sys.platform == "win32" or sys.platform == "cygwin"


def is_pyodide() -> bool:
    return "pyodide" in sys.modules


def check_shared_memory_available() -> tuple[bool, str]:
    """Check if shared memory is available for multiprocessing.

    Returns:
        A tuple of (is_available, error_message).
        If is_available is True, error_message is empty.
        If is_available is False, error_message contains the reason.
    """
    if is_pyodide():
        return False, "Shared memory is not supported on the Pyodide platform."

    try:
        from multiprocessing import shared_memory

        # Try to create a small shared memory segment
        test_name = f"marimo_test_{uuid4().hex[:8]}"
        shm = shared_memory.SharedMemory(name=test_name, create=True, size=8)
        shm.close()
        shm.unlink()
    except ImportError as e:
        return (
            False,
            f"The multiprocessing.shared_memory module is not available: {e}",
        )
    except OSError as e:
        return (
            False,
            f"Unable to create shared memory: {e}. "
            "This can happen in restricted environments like some Docker "
            "containers or when /dev/shm is not available or has insufficient "
            "space.",
        )
    except Exception as e:
        return False, f"Unexpected error checking shared memory: {e}"
    else:
        return True, ""
