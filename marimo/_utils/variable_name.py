from __future__ import annotations

import inspect
from typing import Any

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def infer_variable_name(value: Any, fallback: str) -> str:
    """Infer the variable name that holds ``value`` in the caller's caller.

    Walks up two frames (skipping this helper and the direct caller) and
    searches locals for an identity match (``is``).  Returns *fallback* if
    the lookup fails for any reason.

    Frame references are always cleaned up to avoid reference cycles.
    """
    frame = None
    target_frame = None
    try:
        frame = inspect.currentframe()
        if frame is not None and frame.f_back is not None:
            target_frame = frame.f_back.f_back
        if target_frame is not None:
            for var_name, var_value in target_frame.f_locals.items():
                if var_value is value:
                    return var_name
    except Exception:
        LOGGER.debug(
            "Failed to infer variable name from caller frame.",
            exc_info=True,
        )
    finally:
        del frame
        del target_frame
    return fallback
