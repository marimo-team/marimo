# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
from typing import Any, Optional

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

TIMEOUT = 10  # seconds


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


def has_cgroup_limits() -> tuple[bool, bool]:
    """
    Check if cgroup resource limits are explicitly set.

    This is the standard way to detect container resource limits on Linux.
    These cgroup paths are part of the kernel ABI and are stable across versions.
    See: https://www.kernel.org/doc/Documentation/cgroup-v2.txt
         https://www.kernel.org/doc/Documentation/cgroup-v1/

    Returns:
        (has_memory_limit, has_cpu_limit): Tuple of booleans indicating
        whether memory and CPU limits are set.
    """
    has_memory = False
    has_cpu = False

    try:
        # Check cgroup v2 (modern containers)
        if os.path.exists("/sys/fs/cgroup/memory.max"):
            with open("/sys/fs/cgroup/memory.max", encoding="utf-8") as f:
                memory_max = f.read().strip()
            # 'max' means unlimited, any number means limited
            has_memory = memory_max != "max"

        if os.path.exists("/sys/fs/cgroup/cpu.max"):
            with open("/sys/fs/cgroup/cpu.max", encoding="utf-8") as f:
                cpu_max = f.read().strip()
            # 'max' means unlimited
            has_cpu = cpu_max != "max"

        # Fallback to cgroup v1 (legacy)
        if not has_memory and os.path.exists(
            "/sys/fs/cgroup/memory/memory.limit_in_bytes"
        ):
            with open(
                "/sys/fs/cgroup/memory/memory.limit_in_bytes", encoding="utf-8"
            ) as f:
                limit = int(f.read().strip())
            # Very large number (typically > 2^62) indicates unlimited
            # This is the default "unlimited" value in cgroup v1
            has_memory = limit < (1 << 62)

        if not has_cpu and os.path.exists(
            "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"
        ):
            with open(
                "/sys/fs/cgroup/cpu/cpu.cfs_quota_us", encoding="utf-8"
            ) as f:
                quota = int(f.read().strip())
            # In cgroup v1, -1 means unlimited
            has_cpu = quota > 0

    except (FileNotFoundError, PermissionError, ValueError) as e:
        LOGGER.debug(f"Error checking cgroup limits: {e}")

    return has_memory, has_cpu


def get_container_resources() -> Optional[dict[str, Any]]:
    """
    Get container resource limits if running in a resource-restricted container.

    Returns:
        Dictionary with 'memory' and/or 'cpu' keys if limits are set,
        None if not in a container or no limits are configured.

    Example return value:
        {
            'memory': {
                'total': 2147483648,      # bytes
                'used': 1073741824,       # bytes
                'available': 1073741824,  # bytes
                'percent': 50.0           # percentage
            },
            'cpu': {
                'quota': 200000,   # microseconds
                'period': 100000,  # microseconds
                'cores': 2.0       # effective number of cores
            }
        }
    """
    has_memory_limit, has_cpu_limit = has_cgroup_limits()

    if not (has_memory_limit or has_cpu_limit):
        return None

    resources: dict[str, Any] = {}

    # Get memory stats if limited
    if has_memory_limit:
        try:
            # Try cgroup v2 first
            if os.path.exists("/sys/fs/cgroup/memory.max"):
                with open("/sys/fs/cgroup/memory.max", encoding="utf-8") as f:
                    memory_max = f.read().strip()
                    f.close()
                with open(
                    "/sys/fs/cgroup/memory.current", encoding="utf-8"
                ) as f:
                    memory_current = f.read().strip()
                    f.close()

                if memory_max != "max":
                    total = int(memory_max)
                    used = int(memory_current)
                    available = total - used
                    percent = (used / total) * 100 if total > 0 else 0

                    resources["memory"] = {
                        "total": total,
                        "used": used,
                        "available": available,
                        "percent": percent,
                    }
            # Fallback to cgroup v1
            elif os.path.exists("/sys/fs/cgroup/memory/memory.limit_in_bytes"):
                with open(
                    "/sys/fs/cgroup/memory/memory.limit_in_bytes",
                    encoding="utf-8",
                ) as f:
                    total = int(f.read().strip())
                    f.close()
                with open(
                    "/sys/fs/cgroup/memory/memory.usage_in_bytes",
                    encoding="utf-8",
                ) as f:
                    used = int(f.read().strip())
                    f.close()
                available = total - used
                percent = (used / total) * 100 if total > 0 else 0

                resources["memory"] = {
                    "total": total,
                    "used": used,
                    "available": available,
                    "percent": percent,
                }
        except (FileNotFoundError, PermissionError, ValueError) as e:
            LOGGER.debug(f"Error reading container memory stats: {e}")

    # Get CPU stats if limited
    if has_cpu_limit:
        try:
            # cgroup v2
            if os.path.exists("/sys/fs/cgroup/cpu.max"):
                with open("/sys/fs/cgroup/cpu.max", encoding="utf-8") as f:
                    cpu_max_line = f.read().strip()
                    f.close()
                if cpu_max_line != "max":
                    parts = cpu_max_line.split()
                    if len(parts) == 2:
                        quota = int(parts[0])
                        period = int(parts[1])
                        cores = quota / period

                        resources["cpu"] = {
                            "quota": quota,
                            "period": period,
                            "cores": cores,
                        }
            # cgroup v1
            elif os.path.exists("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"):
                with open(
                    "/sys/fs/cgroup/cpu/cpu.cfs_quota_us", encoding="utf-8"
                ) as f:
                    quota = int(f.read().strip())
                    f.close()
                with open(
                    "/sys/fs/cgroup/cpu/cpu.cfs_period_us", encoding="utf-8"
                ) as f:
                    period = int(f.read().strip())
                    f.close()
                if quota > 0:  # -1 means unlimited
                    cores = quota / period
                    resources["cpu"] = {
                        "quota": quota,
                        "period": period,
                        "cores": cores,
                    }
        except (FileNotFoundError, PermissionError, ValueError) as e:
            LOGGER.debug(f"Error reading container CPU stats: {e}")

    return resources if resources else None
