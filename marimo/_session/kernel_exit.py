# Copyright 2026 Marimo. All rights reserved.
"""Classify how a kernel subprocess exited.

Used to turn a raw ``multiprocessing.Process.exitcode`` into a structured
``KernelExitInfo`` with a human-readable message. Best-effort cgroup
inspection adds memory diagnostics on Linux when the kernel was SIGKILLed,
which on a container is almost always the cgroup OOM killer.
"""

from __future__ import annotations

import os
import signal
import sys

from marimo._session.types import KernelExitInfo

# POSIX signal numbers used for kernel-exit classification. We pull them from
# the ``signal`` module so the branches read naturally, with numeric fallbacks
# for Windows (which doesn't define SIGKILL). The surrounding code is gated to
# Linux at runtime, so the fallbacks only matter for tests that monkeypatch
# ``sys.platform``.
_SIGKILL = getattr(signal, "SIGKILL", 9)
_SIGSEGV = getattr(signal, "SIGSEGV", 11)

# Set by the container runtime / launcher to the pod's memory limit in
# mebibytes (binary, 1 MiB = 1024 * 1024 bytes). Used purely to enrich OOM
# messages; safe to leave unset.
_MEMORY_LIMIT_ENV = "MARIMO_KERNEL_MEMORY_LIMIT_MIB"

# cgroup v1 paths (used in molab's gVisor sandbox today). v2 uses different
# filenames under /sys/fs/cgroup directly; we try both.
_CGROUP_V1_FAILCNT = "/sys/fs/cgroup/memory/memory.failcnt"
_CGROUP_V1_PEAK = "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"
_CGROUP_V2_EVENTS = "/sys/fs/cgroup/memory.events"
_CGROUP_V2_PEAK = "/sys/fs/cgroup/memory.peak"


_RESTART_HINT = "Click Restart to start a fresh kernel."


def classify_kernel_exit(exitcode: int | None) -> KernelExitInfo:
    """Return a KernelExitInfo describing how the kernel exited.

    Messages are end-user-facing: each one names the cause in plain language
    and ends with a concrete next step (typically pressing Restart, sometimes
    paired with advice on freeing memory or trimming inputs).
    """
    if exitcode is None:
        return KernelExitInfo(
            exitcode=None,
            cause="unknown",
            message=f"The kernel stopped unexpectedly. {_RESTART_HINT}",
        )
    if exitcode == 0:
        return KernelExitInfo(
            exitcode=0,
            cause="success",
            message=f"The kernel finished cleanly. {_RESTART_HINT}",
        )
    if exitcode > 0:
        return KernelExitInfo(
            exitcode=exitcode,
            cause="exit",
            message=(
                f"The kernel exited with error code {exitcode}. "
                f"{_RESTART_HINT}"
            ),
        )

    # ``exitcode < 0`` only occurs on POSIX (Windows never returns negative
    # exitcodes). The signal-name and cgroup OOM logic below assumes Linux
    # conventions (POSIX signal numbers per multiprocessing.Process.exitcode,
    # see https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.exitcode,
    # and Linux-specific cgroup files under /sys/fs/cgroup). On other
    # platforms (including darwin) we have no way to confirm OOM, so we
    # surface a generic failure rather than guessing -- claiming OOM for
    # every SIGKILL would mislead users when the real cause is a crash,
    # ``kill -9``, or something else.
    if sys.platform != "linux":
        return KernelExitInfo(
            exitcode=exitcode,
            cause="abnormal",
            message=(f"The kernel was stopped unexpectedly. {_RESTART_HINT}"),
        )

    signal_num = -exitcode
    if signal_num == _SIGKILL:
        peak_mib = _peak_rss_mib()
        if _was_oom_killed():
            limit_mib = _memory_limit_mib()
            usage = (
                f" Notebook used {peak_mib} MiB of the {limit_mib} MiB limit."
                if peak_mib is not None and limit_mib is not None
                else f" Peak memory: {peak_mib} MiB."
                if peak_mib is not None
                else ""
            )
            return KernelExitInfo(
                exitcode=exitcode,
                cause="oom",
                message=(
                    "The kernel ran out of memory and was stopped."
                    + usage
                    + " Free large variables (e.g. `del x; import gc; "
                    "gc.collect()`), reduce data sizes, or request a larger "
                    f"sandbox. {_RESTART_HINT}"
                ),
            )
        # SIGKILL without cgroup-confirmed OOM: the cause is genuinely
        # unknown (could be ``kill -9``, an external OOM-killer outside our
        # cgroup, a crash, etc.). Be honest rather than guessing OOM.
        return KernelExitInfo(
            exitcode=exitcode,
            cause="sigkill",
            message=(f"The kernel was stopped unexpectedly. {_RESTART_HINT}"),
        )
    elif signal_num == _SIGSEGV:
        return KernelExitInfo(
            exitcode=exitcode,
            cause="segfault",
            message=(
                "A native extension crashed the kernel (segmentation "
                f"fault). {_RESTART_HINT} If it recurs, try a different "
                "version of the package that triggered it."
            ),
        )
    return KernelExitInfo(
        exitcode=exitcode,
        cause=f"signal_{signal_num}",
        message=(
            f"The kernel was stopped by the operating system (signal "
            f"{signal_num}). {_RESTART_HINT}"
        ),
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
