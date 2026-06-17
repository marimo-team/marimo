# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

if sys.version_info >= (3, 12):
    from typing import NotRequired as _NotRequired, override as _override
elif sys.version_info >= (3, 11):
    from typing import NotRequired as _NotRequired

    from typing_extensions import override as _override
else:
    from typing_extensions import (
        NotRequired as _NotRequired,
        override as _override,
    )

NotRequired = _NotRequired
override = _override
