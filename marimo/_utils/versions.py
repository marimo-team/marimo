# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import re
from importlib.metadata import Distribution


def is_editable(pkg_name: str) -> bool:
    """Check if a package is an editable install"""

    try:
        direct_url = Distribution.from_name(pkg_name).read_text(
            "direct_url.json"
        )
    except Exception:
        return False

    if direct_url is None:
        return False

    pkg_is_editable = (
        json.loads(direct_url).get("dir_info", {}).get("editable", False)
    )
    return bool(pkg_is_editable)


def without_version_specifier(package: str) -> str:
    return re.split(r"[=<>~]+", package)[0]


def without_extras(package: str) -> str:
    if "[" not in package:
        return package
    return package.split("[")[0]


def has_version_specifier(package: str) -> bool:
    return re.search(r"[=<>~]+", package) is not None
