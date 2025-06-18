# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
import inspect
import os
import time
from pathlib import Path
from typing import Any, Callable, TypeVar, Union

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

# Type for wrapped functions
F = TypeVar("F", bound=Callable[..., Any])

# Track original functions
_ORIGINAL_FUNCTIONS: dict[str, Any] = {}
_patched = False

# Default ignore patterns - paths containing these will be ignored
DEFAULT_IGNORE_PATTERNS = [
    ".venv",
    ".local",
]

# Current ignore patterns (can be customized)
_ignore_patterns = DEFAULT_IGNORE_PATTERNS.copy()


def _should_ignore_path(path: Union[str, Path]) -> bool:
    """Check if a path should be ignored based on ignore patterns."""
    if not _ignore_patterns:
        return False

    path_str = str(path)

    # Check if any ignore pattern is in the path
    for pattern in _ignore_patterns:
        if pattern in path_str:
            return True

    return False


def _get_caller_info() -> str:
    """Get information about the caller of a file I/O operation."""
    frame = inspect.currentframe()
    try:
        # Go up the stack to find the actual caller (skip our wrapper functions)
        for _ in range(4):
            if frame is None:
                break
            frame = frame.f_back

        if frame is None:
            return "unknown"

        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        funcname = frame.f_code.co_name

        # Make filename relative if possible
        try:
            filename = Path(filename).relative_to(Path.cwd())
        except ValueError:
            # Keep absolute path if can't make relative
            pass

        return f"{filename}:{lineno} in {funcname}()"
    finally:
        del frame


def _log_file_operation(
    operation: str,
    path: Union[str, Path],
    size: int | None = None,
    content_preview: str | None = None,
    **kwargs: Any,
) -> None:
    """Log a file I/O operation with detailed information."""
    # Check if path should be ignored
    if _should_ignore_path(path):
        return

    path_str = str(path)
    caller = _get_caller_info()

    # Create log message parts
    parts = [f"{operation}: {path_str}"]

    if size is not None:
        parts.append(f"size={size}B")

    if content_preview:
        # Limit preview length and escape newlines
        preview = (
            content_preview[:10].replace("\n", "\\n").replace("\r", "\\r")
        )
        if len(content_preview) > 10:
            preview += "..."
        parts.append(f"preview='({len(content_preview)}) {preview}'")

    # Add any additional kwargs
    for key, value in kwargs.items():
        parts.append(f"{key}={value}")

    parts.append(f"caller={caller}")

    message = " | ".join(parts)
    LOGGER.info(f"FILE_IO: {message}")


def _wrap_function(func: F, operation_name: str) -> F:
    """Generic wrapper for file I/O functions."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()

        # Try to extract path from arguments
        path = None
        if args:
            if isinstance(args[0], (str, Path)):
                path = args[0]
            elif hasattr(args[0], "_value") and isinstance(
                args[0]._value, Path
            ):
                # Handle PathState objects
                path = args[0]._value

        # Handle self parameter for Path methods
        if hasattr(args[0] if args else None, "__fspath__"):
            path = args[0]

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            # Log the operation
            log_kwargs = {"duration_ms": f"{duration * 1000:.1f}"}

            # Add operation-specific information
            if operation_name in ("read_text", "read_bytes") and result:
                size = (
                    len(result) if isinstance(result, (str, bytes)) else None
                )
                preview = result if isinstance(result, str) else None
                _log_file_operation(
                    operation_name,
                    path or "unknown",
                    size=size,
                    content_preview=preview,
                    **log_kwargs,
                )
            elif operation_name in ("write_text", "write_bytes"):
                # For write operations, check the content being written
                content = None
                size = None
                preview = None
                if len(args) > 1:
                    content = args[1]
                    size = (
                        len(content)
                        if isinstance(content, (str, bytes))
                        else None
                    )
                    preview = content if isinstance(content, str) else None
                elif "data" in kwargs:
                    content = kwargs["data"]
                    size = (
                        len(content)
                        if isinstance(content, (str, bytes))
                        else None
                    )
                    preview = content if isinstance(content, str) else None

                _log_file_operation(
                    operation_name,
                    path or "unknown",
                    size=size,
                    content_preview=preview,
                    **log_kwargs,
                )
            else:
                _log_file_operation(
                    operation_name, path or "unknown", **log_kwargs
                )

            return result

        except Exception as e:
            duration = time.time() - start_time
            _log_file_operation(
                f"{operation_name}_ERROR",
                path or "unknown",
                error=str(e),
                duration_ms=f"{duration * 1000:.1f}",
            )
            raise

    return wrapper  # type: ignore


def patch_pathlib() -> None:
    """Patch pathlib.Path methods to track file I/O operations."""
    if "pathlib_read_text" in _ORIGINAL_FUNCTIONS:
        return

    # Store original methods
    _ORIGINAL_FUNCTIONS["pathlib_read_text"] = Path.read_text
    _ORIGINAL_FUNCTIONS["pathlib_read_bytes"] = Path.read_bytes
    _ORIGINAL_FUNCTIONS["pathlib_write_text"] = Path.write_text
    _ORIGINAL_FUNCTIONS["pathlib_write_bytes"] = Path.write_bytes
    _ORIGINAL_FUNCTIONS["pathlib_open"] = Path.open

    # Patch with wrapped versions
    Path.read_text = _wrap_function(Path.read_text, "read_text")
    Path.read_bytes = _wrap_function(Path.read_bytes, "read_bytes")
    Path.write_text = _wrap_function(Path.write_text, "write_text")
    Path.write_bytes = _wrap_function(Path.write_bytes, "write_bytes")
    Path.open = _wrap_function(Path.open, "open")


def patch_builtins() -> None:
    """Patch built-in open function to track file I/O operations."""
    if "builtin_open" in _ORIGINAL_FUNCTIONS:
        return

    import builtins

    # Store original function
    _ORIGINAL_FUNCTIONS["builtin_open"] = builtins.open

    # Create wrapped version
    original_open = builtins.open

    @functools.wraps(original_open)
    def tracked_open(
        file: Union[str, Path], mode: str = "r", *args: Any, **kwargs: Any
    ) -> Any:
        _log_file_operation("open", file, mode=mode)
        return original_open(file, mode, *args, **kwargs)

    # Patch
    builtins.open = tracked_open


def patch_os_module() -> None:
    """Patch os module functions to track file I/O operations."""
    if "os_remove" in _ORIGINAL_FUNCTIONS:
        return

    # Store and patch os functions
    functions_to_patch = [
        "remove",
        "unlink",
        "rmdir",
        "mkdir",
        "makedirs",
        "rename",
        "replace",
        "stat",
        "listdir",
    ]

    for func_name in functions_to_patch:
        if hasattr(os, func_name):
            original_func = getattr(os, func_name)
            _ORIGINAL_FUNCTIONS[f"os_{func_name}"] = original_func
            setattr(
                os, func_name, _wrap_function(original_func, f"os.{func_name}")
            )


def enable_file_io_tracking() -> None:
    """Enable file I/O tracking by patching relevant modules."""
    global _patched

    if _patched:
        LOGGER.warning("File I/O tracking is already enabled")
        return

    LOGGER.info("Enabling file I/O tracking...")

    try:
        patch_pathlib()
        patch_builtins()
        patch_os_module()
        _patched = True
        LOGGER.info("File I/O tracking enabled successfully")
    except Exception as e:
        LOGGER.error(f"Failed to enable file I/O tracking: {e}")
        raise


def disable_file_io_tracking() -> None:
    """Disable file I/O tracking by restoring original functions."""
    global _patched

    if not _patched:
        LOGGER.warning("File I/O tracking is not enabled")
        return

    LOGGER.info("Disabling file I/O tracking...")

    try:
        import builtins

        # Restore pathlib methods
        if "pathlib_read_text" in _ORIGINAL_FUNCTIONS:
            Path.read_text = _ORIGINAL_FUNCTIONS["pathlib_read_text"]
            Path.read_bytes = _ORIGINAL_FUNCTIONS["pathlib_read_bytes"]
            Path.write_text = _ORIGINAL_FUNCTIONS["pathlib_write_text"]
            Path.write_bytes = _ORIGINAL_FUNCTIONS["pathlib_write_bytes"]
            Path.open = _ORIGINAL_FUNCTIONS["pathlib_open"]

        # Restore builtin open
        if "builtin_open" in _ORIGINAL_FUNCTIONS:
            builtins.open = _ORIGINAL_FUNCTIONS["builtin_open"]

        # Restore os functions
        for key, original_func in _ORIGINAL_FUNCTIONS.items():
            if key.startswith("os_"):
                func_name = key[3:]  # Remove "os_" prefix
                if hasattr(os, func_name):
                    setattr(os, func_name, original_func)

        _ORIGINAL_FUNCTIONS.clear()
        _patched = False
        LOGGER.info("File I/O tracking disabled successfully")

    except Exception as e:
        LOGGER.error(f"Failed to disable file I/O tracking: {e}")
        raise
