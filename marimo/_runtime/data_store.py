# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import random
import string
import threading
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem

if TYPE_CHECKING:
    from marimo._runtime.context import RuntimeContext

LOGGER = _loggers.marimo_logger()


_ALPHABET = string.ascii_letters + string.digits


def random_id() -> str:
    # adapted from: https://stackoverflow.com/questions/13484726/safe-enough-8-character-short-unique-random-string  # noqa: E501
    # TODO(akshayka): should callers redraw if they get a collision?
    tid = str(threading.get_native_id())
    return tid + "-" + "".join(random.choices(_ALPHABET, k=8))


class UIDataLifecycleItem(CellLifecycleItem):
    def __init__(self, data_store: dict[str, Any]) -> None:
        self.id = random_id()
        self.data_store = data_store

    def create(self, context: "RuntimeContext") -> None:
        context.ui_element_registry.add_data_store(self.id, self.data_store)

    def dispose(self, context: "RuntimeContext") -> None:
        context.ui_element_registry.remove_data_store(self.id)
