# Source - https://stackoverflow.com/a
# Posted by Kache, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-17, License - CC BY-SA 4.0
from __future__ import annotations

import inspect
import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import FrameType


def fast_stack(max_depth: int | None = None) -> list[inspect.FrameInfo]:
    """Fast alternative to `inspect.stack()`

    Use optional `max_depth` to limit search depth
    Based on: github.com/python/cpython/blob/3.11/Lib/inspect.py

    Compared to `inspect.stack()`:
     * Does not read source files to load neighboring context
     * Less accurate filename determination, still correct for most cases
     * Does not compute 3.11+ code positions (PEP 657)

    Compare:

    In [3]: %timeit stack_depth(100, lambda: inspect.stack())
    67.7 ms ± 1.35 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)

    In [4]: %timeit stack_depth(100, lambda: inspect.stack(0))
    22.7 ms ± 747 µs per loop (mean ± std. dev. of 7 runs, 10 loops each)

    In [5]: %timeit stack_depth(100, lambda: fast_stack())
    108 µs ± 180 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)

    In [6]: %timeit stack_depth(100, lambda: fast_stack(10))
    14.1 µs ± 33.4 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)
    """

    def frame_infos(
        frame: FrameType | None,
    ) -> Generator[inspect.FrameInfo, None, None]:
        while frame := frame and frame.f_back:
            yield inspect.FrameInfo(
                frame,
                inspect.getfile(frame),
                frame.f_lineno,
                frame.f_code.co_name,
                None,
                None,
            )

    return list(
        itertools.islice(frame_infos(inspect.currentframe()), max_depth)
    )
