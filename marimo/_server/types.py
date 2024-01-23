# Copyright 2024 Marimo. All rights reserved.
from multiprocessing import Queue as MPQueue
from queue import Queue
from typing import TypeVar, Union

T = TypeVar("T")
QueueType = Union["MPQueue[T]", Queue[T]]
