# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import textwrap
from typing import Any, Generator

import pytest

from marimo._ast.cell import CellId_t
from marimo._runtime.context import (
    initialize_context,
    teardown_context,
)
from marimo._runtime.requests import ExecutionRequest
from marimo._runtime.runtime import Kernel


@dataclasses.dataclass
class _MockStream:
    messages: list[tuple[str, dict[Any, Any]]] = dataclasses.field(
        default_factory=list
    )

    def write(self, op: str, data: dict[Any, Any]) -> None:
        self.messages.append((op, data))


@dataclasses.dataclass
class _MockStdStream:
    messages: list[str] = dataclasses.field(default_factory=list)

    def write(self, msg: str) -> None:
        self.messages.append(msg)


@dataclasses.dataclass
class MockedKernel:
    k: Kernel = dataclasses.field(default_factory=Kernel)
    stream: _MockStream = dataclasses.field(default_factory=_MockStream)
    stdout: _MockStdStream = dataclasses.field(default_factory=_MockStdStream)
    stderr: _MockStdStream = dataclasses.field(default_factory=_MockStdStream)

    def __post_init__(self) -> None:
        initialize_context(
            kernel=self.k,
            stream=self.stream,  # type: ignore
            stdout=self.stdout,  # type: ignore
            stderr=self.stderr,  # type: ignore
        )

    def __del__(self) -> None:
        # have to teardown the runtime context because it's a global
        teardown_context()


# fixture that provides a kernel (and tears it down)
@pytest.fixture
def k() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    yield mocked.k


# fixture that wraps a kernel and other mocked objects
@pytest.fixture
def mocked_kernel() -> Generator[MockedKernel, None, None]:
    mocked = MockedKernel()
    yield mocked


# Factory to create ExecutionRequests and abstract away cell ID
class ExecReqProvider:
    def __init__(self) -> None:
        self.counter = 0

    def get(self, code: str) -> ExecutionRequest:
        key = str(self.counter)
        self.counter += 1
        return ExecutionRequest(key, textwrap.dedent(code))

    def get_with_id(self, cell_id: CellId_t, code: str) -> ExecutionRequest:
        return ExecutionRequest(cell_id, textwrap.dedent(code))


# fixture that provides an ExecReqProvider
@pytest.fixture
def exec_req() -> Generator[ExecReqProvider, None, None]:
    yield ExecReqProvider()
