# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import sys
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    NoReturn,
    Optional,
    Union,
)

if TYPE_CHECKING:
    from types import FrameType

    from _typeshed import TraceFunction
    from typing_extensions import Self


class SkipContext(ABC):
    def __init__(self) -> None:
        # For an implementation sibling regarding the block skipping, see
        # `withhacks` in pypi.
        self._entered_trace = False
        self._sys_trace: Optional[TraceFunction] = None
        self._old_trace: Optional[TraceFunction] = None
        self._frame: Optional[FrameType] = None
        self._skipped = True

    def __enter__(self) -> Self:
        self._sys_trace = sys.gettrace()
        if maybe_frame := inspect.currentframe():
            frame = maybe_frame.f_back
        else:
            raise RuntimeError("Unable to establish current frame.")
        assert frame is not None
        # Hold on to the previous trace.
        self._old_trace = frame.f_trace
        # Setting the frametrace, will cause the function to be run on _every_
        # single context call until the trace is cleared.
        frame.f_trace = self._trace
        sys.settrace(self._trace_wrapper)
        return self

    def _trace_wrapper(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunction]:
        """Wrapper function that ensures we do not break existing traces (e.g., code coverage)."""
        result = None
        if self._sys_trace:
            result = self._sys_trace(frame, event, arg)
        # Presumed to be skipped, but hasn't actually entered the frame yet.
        # Call the original trace function
        if self._skipped and not self.entered_trace:
            return self._trace(frame, event, arg)
        return result

    def skip(self) -> NoReturn:
        raise SkipWithBlock()

    def _trace(
        self, with_frame: FrameType, _event: str, _arg: Any
    ) -> Union[TraceFunction, None]:
        self._entered_trace = True

        if not self._skipped:
            return self._old_trace

        self.trace(with_frame)
        self._skipped = False
        self.teardown()
        return self._old_trace

    @abstractmethod
    def trace(self, with_frame: FrameType) -> None:
        pass

    @property
    def entered_trace(self) -> bool:
        return self._entered_trace

    def teardown(self) -> None:
        sys.settrace(self._sys_trace)  # Clear to previous set trace.


class SkipWithBlock(Exception):
    """Special exception to get around executing the with block body."""
