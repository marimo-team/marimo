# Copyright 2026 Marimo. All rights reserved.
"""Classify how a kernel subprocess exited.

Used to turn a raw ``multiprocessing.Process.exitcode`` into a structured
``KernelExitInfo`` with a human-readable message. Best-effort cgroup
inspection adds memory diagnostics on Linux when the kernel was SIGKILLed,
which on a container is almost always the cgroup OOM killer.
"""

from __future__ import annotations

import os

from marimo._session.types import KernelExitInfo

# Set by the container runtime / launcher to the pod's memory limit in MiB.
# Used purely to enrich OOM messages; safe to leave unset.
_MEMORY_LIMIT_ENV = "MARIMO_KERNEL_MEMORY_LIMIT_MB"

# cgroup v1 paths (used in molab's gVisor sandbox today). v2 uses different
# filenames under /sys/fs/cgroup directly; we try both.
_CGROUP_V1_FAILCNT = "/sys/fs/cgroup/memory/memory.failcnt"
_CGROUP_V1_PEAK = "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"
_CGROUP_V2_EVENTS = "/sys/fs/cgroup/memory.events"
_CGROUP_V2_PEAK = "/sys/fs/cgroup/memory.peak"


def classify_kernel_exit(exitcode: int | None) -> KernelExitInfo:
    """Return a KernelExitInfo describing how the kernel exited."""
    if exitcode is None:
        return KernelExitInfo(
            exitcode=None,
            cause="unknown",
            message="kernel exit status unavailable",
        )
    if exitcode >= 0:
        return KernelExitInfo(
            exitcode=exitcode,
            cause="exit",
            message=f"exited with code {exitcode}",
        )

    signal_num = -exitcode
    if signal_num == 9:
        peak_mib = _peak_rss_mib()
        if _was_oom_killed():
            limit_mib = _memory_limit_mib()
            suffix = (
                f" (peak {peak_mib} MiB / limit {limit_mib} MiB)"
                if peak_mib is not None and limit_mib is not None
                else f" (peak {peak_mib} MiB)"
                if peak_mib is not None
                else ""
            )
            return KernelExitInfo(
                exitcode=exitcode,
                cause="oom",
                message=(
                    "out of memory" + suffix + "; "
                    "free large objects or use a larger sandbox"
                ),
            )
        suffix = f" (peak {peak_mib} MiB)" if peak_mib is not None else ""
        return KernelExitInfo(
            exitcode=exitcode,
            cause="sigkill",
            message="killed by SIGKILL" + suffix,
        )
    if signal_num == 11:
        return KernelExitInfo(
            exitcode=exitcode,
            cause="segfault",
            message="segmentation fault (native extension crashed)",
        )
    return KernelExitInfo(
        exitcode=exitcode,
        cause=f"signal_{signal_num}",
        message=f"killed by signal {signal_num}",
    )


def _was_oom_killed() -> bool:
    failcnt = _read_int(_CGROUP_V1_FAILCNT)
    if failcnt is not None:
        return failcnt > 0
    oom_kill = _read_kv(_CGROUP_V2_EVENTS, "oom_kill")
    if oom_kill is not None:
        return oom_kill > 0
    return False


def _peak_rss_mib() -> int | None:
    for path in (_CGROUP_V1_PEAK, _CGROUP_V2_PEAK):
        value = _read_int(path)
        if value is not None:
            return value // (1024 * 1024)
    return None


def _memory_limit_mib() -> int | None:
    raw = os.environ.get(_MEMORY_LIMIT_ENV)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _read_int(path: str) -> int | None:
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _read_kv(path: str, key: str) -> int | None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[0] == key:
                    try:
                        return int(parts[1])
                    except ValueError:
                        return None
    except OSError:
        return None
    return None
