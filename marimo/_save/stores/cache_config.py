# Copyright 2025 Marimo. All rights reserved.
"""
Config access for marimo persistent cache directory.
"""
import os
from marimo._config.manager import get_default_config_manager

def get_persistent_cache_dir() -> str | None:
    # 1. Check environment variable
    env = os.getenv("MARIMO_PERSISTENT_CACHE_DIR")
    if env:
        return env
    # 2. Check config (user, project, script)
    config_mgr = get_default_config_manager(current_path=None)
    config = config_mgr.get_config()
    # Allow both top-level and [runtime] for flexibility
    if "persistent_cache_dir" in config:
        return config["persistent_cache_dir"]
    if "runtime" in config and "persistent_cache_dir" in config["runtime"]:
        return config["runtime"]["persistent_cache_dir"]
    return None
