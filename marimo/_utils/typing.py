# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    from typing_extensions import (
        Annotated as _Annotated,
        NotRequired as _NotRequired,
    )
else:
    from typing import (
        Annotated as _Annotated,
        NotRequired as _NotRequired,
    )

Annotated = _Annotated
NotRequired = _NotRequired
