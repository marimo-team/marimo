# Copyright 2024 Marimo. All rights reserved.
import atexit
from dataclasses import dataclass


@dataclass
class Exiting:
    value: bool = False


_PYTHON_EXITING = Exiting()


def python_exiting() -> bool:
    return _PYTHON_EXITING.value


def _exit() -> None:
    _PYTHON_EXITING.value = True


atexit.register(_exit)
