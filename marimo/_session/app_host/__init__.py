# Copyright 2026 Marimo. All rights reserved.
"""App isolation for serving multiple notebooks.

Each notebook is hosted in an AppHost, which isolates the notebook from other
running notebooks. Sessions for the same notebook are routed to a single
AppHost.

AppHosts are created and managed by an AppHostPool.
"""

from marimo._session.app_host.host import AppHost
from marimo._session.app_host.pool import AppHostContext, AppHostPool

__all__ = [
    "AppHost",
    "AppHostContext",
    "AppHostPool",
]
