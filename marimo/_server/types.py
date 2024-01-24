# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import multiprocessing as mp
from queue import Queue
from typing import TypeVar, Union

T = TypeVar("T")
# strings for python 3.8 compatibility
QueueType = Union["mp.Queue[T]", "Queue[T]"]
