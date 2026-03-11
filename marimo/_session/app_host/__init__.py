# Copyright 2026 Marimo. All rights reserved.
"""Per-app process isolation for running multiple notebooks.

Each notebook gets its own OS process to avoid collisions in sys.modules
and other Python global data structures. Multiple client sessions for the
same notebook share a single host process.

AppHost: wraps a subprocess for one notebook, managing ZeroMQ channels.
AppHostPool: manages host processes keyed by absolute file path.
"""

from marimo._session.app_host.host import AppHost
from marimo._session.app_host.pool import AppHostPool

__all__ = [
    "AppHost",
    "AppHostPool",
]
