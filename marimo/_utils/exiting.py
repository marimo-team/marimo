# Copyright 2024 Marimo. All rights reserved.
import atexit
from dataclasses import dataclass


@dataclass
class Exiting:
    value: bool = False


_PYTHON_EXITING = Exiting()


# bind the global _PYTHON_EXITING to ensure it still exists
# at Python destruction time; for graceful exits when running as a script
def python_exiting(_exiting: Exiting = _PYTHON_EXITING) -> bool:
    return _exiting.value


def _exit() -> None:
    _PYTHON_EXITING.value = True


atexit.register(_exit)
