import functools
import warnings
from typing import Any, Callable

# Adapted from https://stackoverflow.com/questions/2536307


def deprecated(reason: str) -> Callable[[Any], Any]:
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
        @functools.wraps(func)
        def new_func(*args: Any, **kwargs: Any):
            # get the line number of the stack frame of the caller
            lineno = 0
            try:
                import inspect

                lineno = inspect.currentframe().f_back.f_lineno
            except Exception:
                pass

            warnings.simplefilter(
                "always", DeprecationWarning
            )  # turn off filter
            warnings.showwarning(
                message=reason,
                category=DeprecationWarning,
                filename="",
                lineno=lineno,
            )
            warnings.simplefilter(
                "default", DeprecationWarning
            )  # reset filter
            return func(*args, **kwargs)

        return new_func

    return decorator
