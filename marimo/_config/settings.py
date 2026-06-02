# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass
class GlobalSettings:
    DEVELOPMENT_MODE: bool = False
    QUIET: bool = False
    YES: bool = False
    CHECK_STATUS_UPDATE: bool = False
    TRACING: bool = os.getenv("MARIMO_TRACING", "false") in ("true", "1")
    PROFILE_DIR: str | None = None
    LOG_LEVEL: int = logging.WARNING
    MANAGE_SCRIPT_METADATA: bool = os.getenv(
        "MARIMO_MANAGE_SCRIPT_METADATA", "false"
    ) in ("true", "1")
    IN_SECURE_ENVIRONMENT: bool = os.getenv(
        "MARIMO_IN_SECURE_ENVIRONMENT", "false"
    ) in ("true", "1")
    # Disable authentication on the virtual file endpoint (`/@file/...`).
    # Useful in sandboxed/embedded deployments where virtual file URLs need
    # to be fetched in trusted contexts. Default "false", meaning auth is required.
    DISABLE_AUTH_ON_VIRTUAL_FILES: bool = os.getenv(
        "_MARIMO_DISABLE_AUTH_ON_VIRTUAL_FILES", "false"
    ) in ("true", "1")
    # Hide all external code-sharing affordances (shareable WASM links, molab,
    # HTML sharing) across every notebook session. Enforced as a final clamp
    # after all config sources are merged (see MarimoConfigManager
    # .get_config_overrides), so it cannot be re-enabled by any config file or
    # runtime override. Intended for machine-wide enforcement set by infra
    # admins in a devpod or container spec.
    #
    # Note: this is a UI-hiding/policy control, not a server-side security
    # boundary -- exported HTML still embeds source and endpoints still serve
    # code. Pair with network egress filtering for defence-in-depth.
    RESTRICT_SHARING: bool = os.getenv("MARIMO_RESTRICT_SHARING", "false") in (
        "true",
        "1",
    )


GLOBAL_SETTINGS = GlobalSettings()
