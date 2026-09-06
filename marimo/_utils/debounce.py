# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextvars
import functools
import threading
import time
import weakref
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

F = TypeVar("F", bound=Callable[..., None])


class Debounce(Generic[F]):
    """
    Debounce wrapper supporting leading and trailing edge execution,
    descriptor binding for instance methods, cancellation, and ContextVar propagation.
    """

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
        # Preserve function metadata, __wrapped__, annotations, and docstrings
        functools.update_wrapper(self, func)
        self._default_wrapper = self._create_wrapper(func)
        # Cache bound wrappers per instance using weak references (supports __slots__ classes)
        self._slots_wrappers: weakref.WeakKeyDictionary[Any, F] = (
            weakref.WeakKeyDictionary()
        )
        self._id_wrappers: dict[int, F] = {}
        self._instance_lock = threading.Lock()

    def _create_wrapper(self, target_func: F) -> F:
        last_called: float = 0.0
        timer: threading.Timer | None = None
        lock = threading.Lock()
        trailing_args: tuple[Any, ...] | None = None
        trailing_kwargs: dict[str, Any] | None = None
        trailing_ctx: contextvars.Context | None = None

        def _fire() -> None:
            nonlocal last_called, timer, trailing_args, trailing_kwargs, trailing_ctx
            with lock:
                args = trailing_args
                kwargs = trailing_kwargs
                ctx = trailing_ctx
                trailing_args = None
                trailing_kwargs = None
                trailing_ctx = None
                timer = None
                if args is None and kwargs is None:
                    return
                last_called = time.time()
            if ctx is not None:
                ctx.run(target_func, *(args or ()), **(kwargs or {}))
            else:
                target_func(*(args or ()), **(kwargs or {}))

        @functools.wraps(target_func)
        def wrapped(*args: Any, **kwargs: Any) -> None:
            nonlocal last_called, timer, trailing_args, trailing_kwargs, trailing_ctx
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
                    trailing_ctx = None
                    execute_now = True
                elif self.trailing:
                    trailing_args = args
                    trailing_kwargs = kwargs
                    trailing_ctx = contextvars.copy_context()
                    if timer is None:
                        remaining = (
                            max(0.0, self.wait_time - elapsed)
                            if last_called > 0
                            else self.wait_time
                        )
                        timer = threading.Timer(remaining, _fire)
                        timer.daemon = True
                        timer.start()
            if execute_now:
                target_func(*args, **kwargs)

        def cancel() -> None:
            nonlocal timer, trailing_args, trailing_kwargs, trailing_ctx
            with lock:
                if timer is not None:
                    timer.cancel()
                    timer = None
                trailing_args = None
                trailing_kwargs = None
                trailing_ctx = None

        wrapped.cancel = cancel  # type: ignore[attr-defined]
        return cast(F, wrapped)

    def cancel(self) -> None:
        if hasattr(self._default_wrapper, "cancel"):
            self._default_wrapper.cancel()

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self._default_wrapper(*args, **kwargs)

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self
        if hasattr(instance, "__dict__"):
            cache = instance.__dict__.setdefault("_marimo_debounce_cache", {})
            wrapper = cache.get(self.func.__name__)
            if wrapper is None:
                bound_func = self.func.__get__(instance, owner)  # type: ignore[attr-defined]
                wrapper = self._create_wrapper(cast(F, bound_func))
                cache[self.func.__name__] = wrapper
            return wrapper

        with self._instance_lock:
            try:
                wrapper = self._slots_wrappers.get(instance)
                if wrapper is None:
                    bound_func = self.func.__get__(instance, owner)  # type: ignore[attr-defined]
                    wrapper = self._create_wrapper(cast(F, bound_func))
                    self._slots_wrappers[instance] = wrapper
                return wrapper
            except TypeError:
                wrapper = self._id_wrappers.get(id(instance))
                if wrapper is None:
                    bound_func = self.func.__get__(instance, owner)  # type: ignore[attr-defined]
                    wrapper = self._create_wrapper(cast(F, bound_func))
                    self._id_wrappers[id(instance)] = wrapper
                return wrapper


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
