from __future__ import annotations

from marimo._plugins.ui._impl.tables.types import is_dataframe_like


class Fake:
    def __getattr__(self, _):
        return ...


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
    assert is_dataframe_like(Real()) is True
