# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired as _NotRequired
else:
    from typing import NotRequired as _NotRequired

NotRequired = _NotRequired
