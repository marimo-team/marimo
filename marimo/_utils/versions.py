from __future__ import annotations

import json
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
