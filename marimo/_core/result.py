# Copyright 2026 Marimo. All rights reserved.
"""A value, or the error a caller must handle."""

from __future__ import annotations

from typing import (
    ClassVar,
    Generic,
    Literal,
    NoReturn,
    TypeAlias,
    TypeVar,
    final,
)

T_co = TypeVar("T_co", covariant=True)
E_co = TypeVar("E_co", covariant=True)


@final
class Ok(Generic[T_co]):
    """A value."""

    __slots__ = ("_value",)
    __match_args__ = ("value",)
    ok: ClassVar[Literal[True]] = True

    def __init__(self, value: T_co) -> None:
        self._value = value

    @property
    def value(self) -> T_co:
        return self._value

    def unwrap(self) -> T_co:
        """Return the value."""
        return self.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ok) and self.value == other.value

    def __hash__(self) -> int:
        return hash((Ok, self.value))

    def __repr__(self) -> str:
        return f"Ok({self.value!r})"


@final
class Err(Generic[E_co]):
    """An error."""

    __slots__ = ("_error",)
    __match_args__ = ("error",)
    ok: ClassVar[Literal[False]] = False

    def __init__(self, error: E_co) -> None:
        self._error = error

    @property
    def error(self) -> E_co:
        return self._error

    def unwrap(self) -> NoReturn:
        """Raise the error."""
        if isinstance(self.error, BaseException):
            raise self.error
        raise RuntimeError(f"The work failed: {self.error!r}")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Err) and self.error == other.error

    def __hash__(self) -> int:
        return hash((Err, self.error))

    def __repr__(self) -> str:
        return f"Err({self.error!r})"


Result: TypeAlias = Ok[T_co] | Err[E_co]
