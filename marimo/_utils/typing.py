from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    from typing_extensions import Annotated as _Annotated
else:
    from typing import Annotated as _Annotated

Annotated = _Annotated
