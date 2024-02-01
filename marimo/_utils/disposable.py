# Copyright 2024 Marimo. All rights reserved.
from typing import Callable


class Disposable:
    def __init__(self, action: Callable[[], None]) -> None:
        self.action = action
        self._is_disposed = False

    def __call__(self) -> None:
        return self.dispose()

    def dispose(self) -> None:
        self.action()
        self._is_disposed = True

    def is_disposed(self) -> bool:
        return self._is_disposed

    @staticmethod
    def empty() -> "Disposable":
        return Disposable(lambda: None)
