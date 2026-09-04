# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextvars
import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, Generic, TypeVar, cast

F = TypeVar("F", bound=Callable[..., None])


class Debounce(Generic[F]):
    def __init__(
        self,
        wait_time: float,
        func: F,
        leading: bool = True,
        trailing: bool = False,
    ) -> None:
        self.wait_time = wait_time
        self.func = func
        self.leading = leading
        self.trailing = trailing
        self._default_wrapper = self._create_wrapper(func)

    def _create_wrapper(self, target_func: F) -> F:
        last_called: float = 0
        timer: threading.Timer | None = None
        lock = threading.Lock()
        trailing_args: tuple[Any, ...] | None = None
        trailing_kwargs: dict[str, Any] | None = None

        def _fire(ctx: contextvars.Context) -> None:
            nonlocal last_called, timer, trailing_args, trailing_kwargs
            with lock:
                args = trailing_args
                kwargs = trailing_kwargs
                trailing_args = None
                trailing_kwargs = None
                timer = None
                if args is None and kwargs is None:
                    return
                last_called = time.time()
            ctx.run(target_func, *(args or ()), **(kwargs or {}))

        @wraps(target_func)
        def wrapped(*args: Any, **kwargs: Any) -> None:
            nonlocal last_called, timer, trailing_args, trailing_kwargs
            current_time = time.time()
            execute_now = False
            with lock:
                elapsed = current_time - last_called
                if self.leading and elapsed >= self.wait_time:
                    if timer is not None:
                        timer.cancel()
                        timer = None
                    last_called = current_time
                    trailing_args = None
                    trailing_kwargs = None
                    execute_now = True
                elif self.trailing:
                    trailing_args = args
                    trailing_kwargs = kwargs
                    if timer is None:
                        remaining = (
                            max(0.0, self.wait_time - elapsed)
                            if last_called > 0
                            else self.wait_time
                        )
                        ctx = contextvars.copy_context()
                        timer = threading.Timer(remaining, _fire, args=(ctx,))
                        timer.daemon = True
                        timer.start()
            if execute_now:
                target_func(*args, **kwargs)

        def cancel() -> None:
            nonlocal timer, trailing_args, trailing_kwargs
            with lock:
                if timer is not None:
                    timer.cancel()
                    timer = None
                trailing_args = None
                trailing_kwargs = None

        wrapped.cancel = cancel
        return cast(F, wrapped)

    def cancel(self) -> None:
        if hasattr(self._default_wrapper, "cancel"):
            self._default_wrapper.cancel()

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self._default_wrapper(*args, **kwargs)

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self
        bound_func = self.func.__get__(instance, owner)  # type: ignore[attr-defined]
        bound_wrapper = self._create_wrapper(cast(F, bound_func))
        name = self.func.__name__
        setattr(instance, name, bound_wrapper)
        return bound_wrapper


def debounce(
    wait_time: float,
    *,
    leading: bool = True,
    trailing: bool = False,
) -> Callable[[F], Debounce[F]]:
    """
    Decorator to prevent a function from being called more than once every
    wait_time seconds. Supports both leading-edge and trailing-edge execution.
    """

    def decorator(func: F) -> Debounce[F]:
        return Debounce(wait_time, func, leading=leading, trailing=trailing)

    return decorator
