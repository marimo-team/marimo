# Copyright 2023 Marimo. All rights reserved.
import textwrap
from typing import Any, Generator

import pytest

from marimo._plugins.ui._core.registry import UIElementRegistry
from marimo._runtime.context import get_context
from marimo._runtime.requests import (
    ExecutionRequest,
)
from marimo._runtime.runtime import Kernel


class _MockStream:
    def write(self, op: str, data: dict[Any, Any]) -> None:
        del op
        del data
        pass


# fixture that provides a kernel (and tears it down)
@pytest.fixture
def k() -> Generator[Kernel, None, None]:
    k = Kernel()
    get_context().initialize(
        kernel=k,
        ui_element_registry=UIElementRegistry(),
        stream=_MockStream(),  # type: ignore
        stdout=None,
        stderr=None,
    )
    yield k
    get_context()._kernel = None
    get_context()._ui_element_registry = None
    get_context()._stream = None
    get_context()._initialized = False


class ExecReqProvider:
    def __init__(self) -> None:
        self.counter = 0

    def get(self, code: str) -> ExecutionRequest:
        key = str(self.counter)
        self.counter += 1
        return ExecutionRequest(key, textwrap.dedent(code))


@pytest.fixture
def exec_req() -> Generator[ExecReqProvider, None, None]:
    yield ExecReqProvider()
