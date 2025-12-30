# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._session.state.session_view import SessionView
from tests.utils import assert_serialize_roundtrip

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def session_view() -> Generator[SessionView, None, None]:
    sv = SessionView()

    yield sv

    # Test all operations can be serialized/deserialized
    for operation in sv.notifications:
        assert_serialize_roundtrip(operation)
