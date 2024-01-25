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

    @classmethod
    def empty(cls):
        return Disposable(lambda: None)
