# Copyright 2026 Marimo. All rights reserved.
"""Spawn-pickleable target for test_patches.py.

Defined in a real importable module so spawn workers can resolve it via
``_fixup_main_from_path`` without relying on the test module's __main__.
"""

from __future__ import annotations


def noop_target() -> None:
    """No-op target for multiprocessing.Process.

    The point of the test is whether the spawn worker can be set up at all,
    not what it does.
    """
    return
