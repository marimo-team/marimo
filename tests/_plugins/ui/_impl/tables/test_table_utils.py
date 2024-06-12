from __future__ import annotations

import pytest

from marimo._plugins.ui._impl.tables.df_protocol_table import (
    DataFrameProtocolTableManager,
)
from marimo._plugins.ui._impl.tables.types import is_dataframe_like


class Fake:
    def __getattr__(self, _):
        return ...


class FakeReturningCallable:
    def __getattr__(self, _):
        return lambda: ...


class Real:
    def __dataframe__(self):
        return ...


def test_is_dataframe_like():
    # Primitives
    assert is_dataframe_like(1) is False
    assert is_dataframe_like("1") is False
    assert is_dataframe_like([]) is False
    assert is_dataframe_like({}) is False
    assert is_dataframe_like(()) is False

    assert is_dataframe_like(Fake()) is False
    assert is_dataframe_like(FakeReturningCallable()) is False
    assert is_dataframe_like(Real()) is True


def test_df_protocol_manager_throws():
    with pytest.raises(ValueError):
        DataFrameProtocolTableManager(Real())
