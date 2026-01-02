# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
import time
from typing import Optional, TypedDict

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

TIMEOUT = 10  # seconds

# Module-level state for cgroup CPU percent calculation (like psutil does)
_LAST_CGROUP_CPU_SAMPLE: Optional[tuple[int, float]] = (
    None  # (usage_usec, timestamp)
)


class MemoryStats(TypedDict):
    total: int
    used: int
    available: int
    percent: float
    free: int


# Constants for cgroup v2 file locations
# Reference: https://www.kernel.org/doc/Documentation/cgroup-v2.txt
CGROUP_V2_MEMORY_MAX_FILE = "/sys/fs/cgroup/memory.max"
CGROUP_V2_MEMORY_CURRENT_FILE = "/sys/fs/cgroup/memory.current"
CGROUP_V2_CPU_STAT_FILE = "/sys/fs/cgroup/cpu.stat"
CGROUP_V2_CPU_MAX_FILE = "/sys/fs/cgroup/cpu.max"

# cgroup v1 file locations (legacy hierarchy)
# Reference: https://www.kernel.org/doc/Documentation/cgroup-v1/
CGROUP_V1_CPU_USAGE_FILE = "/sys/fs/cgroup/cpuacct/cpuacct.usage"
CGROUP_V1_CPU_CFS_QUOTA_US_FILE = "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"
CGROUP_V1_CPU_CFS_PERIOD_US_FILE = "/sys/fs/cgroup/cpu/cpu.cfs_period_us"
CGROUP_V1_MEMORY_LIMIT_FILE = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
CGROUP_V1_MEMORY_USAGE_FILE = "/sys/fs/cgroup/memory/memory.usage_in_bytes"


def get_node_version() -> Optional[str]:
    try:
        process = subprocess.Popen(
            ["node", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = communicate_with_timeout(process)
        if stderr:
            return None
        if stdout and (stripped := stdout.strip()):
            return stripped.split()[-1]
        else:
            return None
    except FileNotFoundError:
        return None


def get_required_modules_list() -> dict[str, str]:
    packages = [
        "click",
        "docutils",
        "itsdangerous",
        "jedi",
        "markdown",
        "narwhals",
        "packaging",
        "psutil",
        "pygments",
        "pymdown-extensions",
        "pyyaml",
        "starlette",
        "tomlkit",
        "typing-extensions",
        "uvicorn",
        "websockets",
    ]
    return _get_versions(packages, include_missing=True)


def get_optional_modules_list() -> dict[str, str]:
    # List of common libraries we integrate with
    packages = [
        "altair",
        "anywidget",
        "basedpyright",
        "duckdb",
        "ibis-framework",
        "loro",
        "mcp",
        "nbformat",
        "openai",
        "opentelemetry",
        "pandas",
        "polars",
        "pyarrow",
        "pylsp-mypy",
        "pytest",
        "python-lsp-ruff",
        "python-lsp-server",
        "ruff",
        "sqlglot",
        "ty",
        "vegafusion",
        "watchdog",
    ]
    return _get_versions(packages, include_missing=False)


def _get_versions(
    packages: list[str], include_missing: bool
) -> dict[str, str]:
    package_versions: dict[str, str] = {}
    # Consider listing all installed modules and their versions
    # Submodules and private modules are can be filtered with:
    #  if not ("." in m or m.startswith("_")):
    for package in packages:
        try:
            package_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            if include_missing:
                package_versions[package] = "missing"

    return package_versions


def get_chrome_version() -> Optional[str]:
    def get_chrome_version_windows() -> Optional[str]:
        process = subprocess.Popen(
            [
                "reg",
                "query",
                "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon",
                "/v",
                "version",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = communicate_with_timeout(process)
        if stderr:
            return None
        parts = stdout.strip().split()
        if parts:
            return parts[-1]
        return None

    def get_chrome_version_mac() -> Optional[str]:
        process = subprocess.Popen(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "--version",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = communicate_with_timeout(process)
        if stderr:
            return None
        parts = stdout.strip().split()
        if parts:
            return parts[-1]
        return None

    def get_chrome_version_linux() -> Optional[str]:
        process = subprocess.Popen(
            ["google-chrome", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = communicate_with_timeout(process)
        if stderr:
            return None
        parts = stdout.strip().split()
        if parts:
            return parts[-1]
        return None

    try:
        if sys.platform.startswith("win32"):
            return get_chrome_version_windows()
        elif sys.platform.startswith("darwin"):
            return get_chrome_version_mac()
        elif sys.platform.startswith("linux"):
            return get_chrome_version_linux()
        else:
            return None
    except FileNotFoundError:
        return None
    except Exception as e:
        LOGGER.error(f"An error occurred: {e}")
        return None


def get_python_version() -> str:
    return sys.version.split()[0]


def communicate_with_timeout(
    process: subprocess.Popen[str], timeout: float = TIMEOUT
) -> tuple[str, str]:
    try:
        return process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        return "", "Error: Process timed out"


def _has_cgroup_cpu_limit() -> bool:
    """
    Returns True/False whether the container has a CPU limit set.
    This function checks for both cgroups v1 and v2.
    """
    if os.path.exists(CGROUP_V2_CPU_MAX_FILE):
        with open(CGROUP_V2_CPU_MAX_FILE, encoding="utf-8") as f:
            cpu_max = f.read().strip()
        return cpu_max != "max"
    # Fallback to cgroup v1 (legacy)
    if os.path.exists(CGROUP_V1_CPU_CFS_QUOTA_US_FILE):
        with open(CGROUP_V1_CPU_CFS_QUOTA_US_FILE, encoding="utf-8") as f:
            quota = int(f.read().strip())
            return quota > 0
    return False


def get_cgroup_mem_stats() -> Optional[MemoryStats]:
    """
    Get container memory stats from cgroup.

    Returns:
        Dictionary with memory stats if cgroup limits are configured,
        None if cgroup limits are not configured or unable to read.

    Example return value:
        {
            'total': 2147483648,      # bytes
            'used': 1073741824,      # bytes
            'available': 1073741824, # bytes
            'free': 1073741824,      # bytes
            'percent': 50.0,         # percentage
        }
    """
    try:
        if os.path.exists(CGROUP_V2_MEMORY_MAX_FILE):
            with open(CGROUP_V2_MEMORY_MAX_FILE, encoding="utf-8") as f:
                memory_max = f.read().strip()
            with open(CGROUP_V2_MEMORY_CURRENT_FILE, encoding="utf-8") as f:
                memory_current = f.read().strip()

            if memory_max != "max":
                total = int(memory_max)
                used = int(memory_current)
                available = total - used
                percent = (used / total) * 100 if total > 0 else 0
                return MemoryStats(
                    total=total,
                    used=used,
                    available=available,
                    percent=percent,
                    free=available,  # free == available for cgroup memory
                )
        elif os.path.exists(CGROUP_V1_MEMORY_LIMIT_FILE):
            with open(CGROUP_V1_MEMORY_LIMIT_FILE, encoding="utf-8") as f:
                total = int(f.read().strip())
            with open(CGROUP_V1_MEMORY_USAGE_FILE, encoding="utf-8") as f:
                used = int(f.read().strip())
            available = total - used
            percent = (used / total) * 100 if total > 0 else 0

            return MemoryStats(
                total=total,
                used=used,
                available=available,
                percent=percent,
                free=available,  # free == available for cgroup memory
            )
    except (FileNotFoundError, PermissionError, ValueError) as e:
        LOGGER.debug(f"Error reading container memory stats: {e}")

    return None


def _get_cgroup_allocated_cores() -> Optional[float]:
    """Get the number of CPU cores allocated to this cgroup (quota / period)."""
    try:
        if os.path.exists(CGROUP_V2_CPU_MAX_FILE):
            with open(CGROUP_V2_CPU_MAX_FILE, encoding="utf-8") as f:
                parts = f.read().strip().split()
            if len(parts) == 2 and parts[0] != "max":
                return int(parts[0]) / int(parts[1])
        elif os.path.exists(CGROUP_V1_CPU_CFS_QUOTA_US_FILE):
            with open(CGROUP_V1_CPU_CFS_QUOTA_US_FILE, encoding="utf-8") as f:
                quota = int(f.read().strip())
            with open(CGROUP_V1_CPU_CFS_PERIOD_US_FILE, encoding="utf-8") as f:
                period = int(f.read().strip())
            if quota > 0:
                return quota / period
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return None


def get_cgroup_cpu_percent() -> Optional[float]:
    """
    Get CPU usage percentage for a cgroup-limited container.

    Works like psutil.cpu_percent(interval=None):
    - First call stores the current reading and returns 0.0
    - Subsequent calls return the CPU percent since the last call

    Returns:
        CPU usage as a percentage (0-100).
        0.0 if cgroup limits are configured but unable to read current usage
            (e.g., on the first call)
        None if cgroup limits are not configured or unable to read.
    """
    global _LAST_CGROUP_CPU_SAMPLE

    # Early return if no CPU limit is configured
    if not _has_cgroup_cpu_limit():
        return None

    try:
        # Read current usage (microseconds)
        current_usage_microseconds: Optional[int] = None

        if os.path.exists(CGROUP_V2_CPU_STAT_FILE):
            with open(CGROUP_V2_CPU_STAT_FILE, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("usage_usec"):
                        current_usage_microseconds = int(line.split()[1])
                        break

        elif os.path.exists(CGROUP_V1_CPU_USAGE_FILE):
            with open(CGROUP_V1_CPU_USAGE_FILE, encoding="utf-8") as f:
                current_usage_microseconds = (
                    int(f.read().strip()) // 1_000_000
                )  # ns -> μs

        if current_usage_microseconds is None:
            return 0.0

        allocated_cores = _get_cgroup_allocated_cores()
        if allocated_cores is None or allocated_cores <= 0:
            return 0.0

        current_time = time.time()

        if _LAST_CGROUP_CPU_SAMPLE is None:
            # First call - store reading, return 0.0 (like psutil's first call)
            _LAST_CGROUP_CPU_SAMPLE = (
                current_usage_microseconds,
                current_time,
            )
            return 0.0

        last_usage, last_time = _LAST_CGROUP_CPU_SAMPLE
        _LAST_CGROUP_CPU_SAMPLE = (current_usage_microseconds, current_time)

        delta_time = current_time - last_time
        if delta_time <= 0:
            return 0.0

        delta_usage_microseconds = current_usage_microseconds - last_usage
        delta_time_microseconds = delta_time * 1_000_000
        percent = (
            delta_usage_microseconds
            / (delta_time_microseconds * 1_000_000 * allocated_cores)
        ) * 100

        return min(100.0, max(0.0, percent))

    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        # Error reading cgroup CPU stats — fall back to psutil
        return None
