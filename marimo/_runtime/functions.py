"""Functions associated with a graph.
"""
from __future__ import annotations

import dataclasses
from typing import Callable, Generic, Type, TypeVar

from marimo._server.api.model import parse_raw

S = TypeVar("S")
T = TypeVar("T")


@dataclasses.dataclass
class Function(Generic[S, T]):
    name: str
    arg_cls: Type[S]
    function: Callable[[S], T]

    def call(self, args: bytes) -> T:
        return self.function(parse_raw(args, self.arg_cls))


class FunctionRegistry:
    def __init__(self) -> None:
        self.functions = {}

    def register_function(self, function: Function) -> None:
        self.functions[function.name] = function

    def get_function(self, name: str) -> Function | None:
        return self.functions[name] if name in self.functions else None

    def remove_function(self, name: str) -> None:
        if name in self.functions:
            del self.functions[name]
