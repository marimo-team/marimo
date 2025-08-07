from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable


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
