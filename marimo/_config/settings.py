# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
from dataclasses import dataclass

from marimo._utils.env import is_env_true


@dataclass
class GlobalSettings:
    DEVELOPMENT_MODE: bool = False
    QUIET: bool = False
    YES: bool = False
    CHECK_STATUS_UPDATE: bool = False
    TRACING: bool = is_env_true("MARIMO_TRACING")
    PROFILE_DIR: str | None = None
    LOG_LEVEL: int = logging.WARNING
    MANAGE_SCRIPT_METADATA: bool = is_env_true("MARIMO_MANAGE_SCRIPT_METADATA")
    IN_SECURE_ENVIRONMENT: bool = is_env_true("MARIMO_IN_SECURE_ENVIRONMENT")
    # Mark the session cookie as `Secure` so browsers only send it over HTTPS.
    # Enable when serving marimo behind TLS / a TLS-terminating proxy. Default
    # "false" to preserve local (plain-HTTP) development.
    SESSION_COOKIE_SECURE: bool = is_env_true("MARIMO_SESSION_COOKIE_SECURE")
    # Disable authentication on the virtual file endpoint (`/@file/...`).
    # Useful in sandboxed/embedded deployments where virtual file URLs need
    # to be fetched in trusted contexts. Default "false", meaning auth is required.
    DISABLE_AUTH_ON_VIRTUAL_FILES: bool = is_env_true(
        "_MARIMO_DISABLE_AUTH_ON_VIRTUAL_FILES"
    )
    # Hide all external code-sharing affordances (shareable WASM links, molab,
    # HTML sharing) across every notebook session. Enforced by
    # SecurityConfigManager, which MarimoConfigManager merges after all other
    # config sources, so it cannot be re-enabled by any config file or runtime
    # override. Intended for machine-wide enforcement set by infra admins in a
    # devpod or container spec.
    #
    # Note: this is a UI-hiding/policy control, not a server-side security
    # boundary -- exported HTML still embeds source and endpoints still serve
    # code. Pair with network egress filtering for defence-in-depth.
    RESTRICT_SHARING: bool = is_env_true("MARIMO_RESTRICT_SHARING")


GLOBAL_SETTINGS = GlobalSettings()
