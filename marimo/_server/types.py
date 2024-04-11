# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Union

if TYPE_CHECKING:
    import multiprocessing as mp
    from queue import Queue

T = TypeVar("T")
# strings for python 3.8 compatibility
QueueType = Union["mp.Queue[T]", "Queue[T]"]
