# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from marimo._utils.with_skip import SkipContext

if TYPE_CHECKING:
    from types import FrameType


class _SkipContext(SkipContext):
    def trace(self, with_frame: FrameType) -> None:
        pass


@pytest.mark.parametrize("frame_available", [False, True])
def test_skip_context_requires_calling_frame(frame_available: bool) -> None:
    frame = Mock(f_back=None) if frame_available else None
    with patch("inspect.currentframe", return_value=frame):
        with pytest.raises(
            RuntimeError, match="calling Python frame"
        ) as exc_info:
            _SkipContext().__enter__()
    assert exc_info.type is RuntimeError
