# Copyright 2026 Marimo. All rights reserved.
"""Helpers for signaling subprocess trees on Unix."""

from __future__ import annotations

import os


def signal_process_group(pgid: int | None, sig: int) -> bool:
    """Best-effort signal delivery to a Unix process group."""
    if pgid is None:
        return False

    try:
        os.killpg(pgid, sig)
        return True
    except Exception:
        return False


def signal_process_tree(
    pid: int | None,
    sig: int,
    *,
    cached_pgid: int | None = None,
    parent_pgid: int | None = None,
) -> int | None:
    """Best-effort signal delivery to a subprocess and its process group.

    Returns:
        The process-group id that future calls can safely reuse, or the
        incoming `cached_pgid` if no safe process-group id was resolved.
        In practice this means:

        - if group signaling succeeds, returns that group id
        - if the child is still in the caller's process group (pre-`setsid`
          startup race), returns `cached_pgid` after signaling the child pid
          directly
        - if pid/group lookup or signaling fails, returns `cached_pgid`

    Callers are expected to use their own Windows fallback because there is no
    Unix-style process-group signaling equivalent there.
    """
    if pid is None:
        return cached_pgid

    pgid = cached_pgid
    if pgid is None:
        try:
            pgid = os.getpgid(pid)
        except Exception:
            return cached_pgid

        if parent_pgid is None:
            try:
                parent_pgid = os.getpgrp()
            except Exception:
                parent_pgid = None

        if parent_pgid is not None and pgid == parent_pgid:
            # The child may not have reached setsid() yet; avoid killing the
            # caller's own process group during startup races.
            try:
                os.kill(pid, sig)
            except Exception:
                pass
            return cached_pgid

    try:
        os.killpg(pgid, sig)
        return pgid
    except Exception:
        try:
            os.kill(pid, sig)
        except Exception:
            pass
        return cached_pgid
