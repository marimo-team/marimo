# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import textwrap
from typing import Any, Generator

import pytest

from marimo._ast.cell import CellId_t
from marimo._messaging.streams import Stderr, Stdin, Stdout
from marimo._runtime.context import (
    initialize_context,
    teardown_context,
)
from marimo._runtime.requests import ExecutionRequest
from marimo._runtime.runtime import Kernel


@dataclasses.dataclass
class _MockStream:
    """Captures the ops sent through the stream"""

    messages: list[tuple[str, dict[Any, Any]]] = dataclasses.field(
        default_factory=list
    )

    def write(self, op: str, data: dict[Any, Any]) -> None:
        self.messages.append((op, data))


@dataclasses.dataclass
class MockStdout(Stdout):
    """Captures the output sent through the stream"""

    messages: list[str] = dataclasses.field(default_factory=list)

    def write(self, data: str) -> int:
        self.messages.append(data)
        return len(data)


@dataclasses.dataclass
class MockStderr(Stderr):
    """Captures the output sent through the stream"""

    messages: list[str] = dataclasses.field(default_factory=list)

    def write(self, data: str) -> int:
        self.messages.append(data)
        return len(data)


@dataclasses.dataclass
class MockStdin(Stdin):
    """Echoes the prompt."""

    def _readline_with_prompt(self, prompt: str = "") -> str:
        return prompt


@dataclasses.dataclass
class MockedKernel:
    stream: _MockStream = dataclasses.field(default_factory=_MockStream)
    stdout: MockStdout = dataclasses.field(default_factory=MockStdout)
    stderr: MockStderr = dataclasses.field(default_factory=MockStderr)
    stdin: MockStdin = dataclasses.field(default_factory=MockStdin)

    def __post_init__(self) -> None:
        self.k = Kernel(
            stream=self.stream,
            stdout=self.stdout,
            stderr=self.stderr,
            stdin=self.stdin,
            cell_configs={},
        )

        initialize_context(
            kernel=self.k,
            stream=self.stream,  # type: ignore
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
