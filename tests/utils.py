from __future__ import annotations

import time
from typing import TYPE_CHECKING

from marimo._messaging.msgspec_encoder import (
    asdict,
    encode_json_bytes,
)
from marimo._utils.parse_dataclass import parse_raw

if TYPE_CHECKING:
    from typing import Callable

    import msgspec


def try_assert_n_times(n: int, assert_fn: Callable[[], None]) -> None:
    """Attempt an assert multiple times.

    Sleeps between each attempt.
    """
    n_tries = 0
    while n_tries <= n - 1:
        try:
            assert_fn()
            return
        except Exception:
            n_tries += 1
            time.sleep(0.1)
    assert_fn()


def assert_serialize_roundtrip(obj: msgspec.Struct) -> None:
    serialized = encode_json_bytes(obj)
    cls = type(obj)
    parsed = parse_raw(serialized, cls)
    assert asdict(obj) == asdict(parsed)
