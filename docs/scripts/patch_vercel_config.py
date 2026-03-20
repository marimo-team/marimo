"""Patch .vercel/output/config.json to add edge middleware routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: patch_vercel_config.py <config.json>")
        raise SystemExit(1)

    config_path = Path(sys.argv[1])

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {"version": 3}

    # Ensure routes list exists
    if "routes" not in config:
        config["routes"] = []

    # Add middleware route at the beginning if not already present
    middleware_route = {
        "src": "/(?!_static/|assets/|stylesheets/|favicon\\.ico)(.*)",
        "middlewarePath": "_middleware",
        "continue": True,
    }

    # Check if middleware route already exists
    has_middleware = any(
        r.get("middlewarePath") == "_middleware" for r in config["routes"]
    )

    if not has_middleware:
        config["routes"].insert(0, middleware_route)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Patched {config_path} with middleware route")


if __name__ == "__main__":
    main()
