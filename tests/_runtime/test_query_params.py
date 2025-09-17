from __future__ import annotations

import unittest

import pytest

from marimo._runtime.params import CLIArgs, QueryParams
from tests._messaging.mocks import MockStream


class TestQueryParams(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_stream = MockStream()
        self.params = QueryParams(
            {"key1": "value1", "key2": ["value2", "value3"]},
            stream=self.mock_stream,
        )

    def test_get(self) -> None:
        assert self.params.get("key1") == "value1"
        assert self.params.get("key2") == ["value2", "value3"]
        # Test with fallback parameter
        assert self.params.get("non_existent", "fallback") == "fallback"
        assert self.params.get("non_existent", ["fallback"]) == ["fallback"]
        assert self.params.get("non_existent", None) is None
        # Test existing keys with fallback (should return original value)
        assert self.params.get("key1", "fallback") == "value1"
        assert self.params.get("key2", "fallback") == ["value2", "value3"]

    def test_get_all(self) -> None:
        assert self.params.get_all("key1") == ["value1"]
        assert self.params.get_all("key2") == ["value2", "value3"]
        assert self.params.get_all("non_existent_key") == []

    def test_contains(self) -> None:
        assert "key1" in self.params
        assert "non_existent_key" not in self.params

    def test_len(self) -> None:
        assert len(self.params) == 2

    def test_iter(self) -> None:
        keys = [key for key in self.params]
        assert keys, ["key1", "key2"]

    def test_repr(self) -> None:
        assert (
            repr(self.params)
            == "QueryParams({'key1': 'value1', 'key2': ['value2', 'value3']})"
        )

    def test_str(self) -> None:
        assert (
            str(self.params)
            == "{'key1': 'value1', 'key2': ['value2', 'value3']}"
        )

    def test_setitem(self) -> None:
        self.params["key3"] = "value4"
        assert self.params.get("key3") == "value4"

        assert len(self.mock_stream.messages) == 1
        assert self.mock_stream.operations[0] == {
            "op": "query-params-set",
            "key": "key3",
            "value": "value4",
        }

    def test_setitem_null(self) -> None:
        self.params["key1"] = None  # type: ignore
        assert self.params.get("key1") is None

        assert len(self.mock_stream.messages) == 1
        assert self.mock_stream.operations[0] == {
            "op": "query-params-delete",
            "key": "key1",
            "value": None,
        }

    def test_setitem_empty(self) -> None:
        self.params["key1"] = []
        assert self.params.get("key1") is None

        assert len(self.mock_stream.messages) == 1
        assert self.mock_stream.operations[0] == {
            "op": "query-params-delete",
            "key": "key1",
            "value": None,
        }

    def test_set(self) -> None:
        self.params.set("key1", "value5")
        assert self.params.get("key1") == "value5"

        assert len(self.mock_stream.messages) == 1
        assert self.mock_stream.operations[0] == {
            "op": "query-params-set",
            "key": "key1",
            "value": "value5",
        }

    def test_set_null(self) -> None:
        self.params.set("key1", None)  # type: ignore
        assert self.params.get("key1") is None

        assert len(self.mock_stream.messages) == 1
        assert self.mock_stream.operations[0] == {
            "op": "query-params-delete",
            "key": "key1",
            "value": None,
        }

    def test_set_empty(self) -> None:
        self.params.set("key1", [])
        assert self.params.get("key1") is None

        assert len(self.mock_stream.messages) == 1
        assert self.mock_stream.operations[0] == {
            "op": "query-params-delete",
            "key": "key1",
            "value": None,
        }

    def test_append(self) -> None:
        self.params.append("key1", "value5")
        assert self.params.get("key1") == ["value1", "value5"]
        self.params.append("key4", "value6")
        assert self.params.get("key4") == "value6"

        assert len(self.mock_stream.messages) == 2
        assert self.mock_stream.operations[0] == {
            "op": "query-params-append",
            "key": "key1",
            "value": "value5",
        }
        assert self.mock_stream.operations[1] == {
            "op": "query-params-append",
            "key": "key4",
            "value": "value6",
        }

    def test_delete(self) -> None:
        del self.params["key1"]
        assert "key1" not in self.params
        assert len(self.params) == 1
        assert str(self.params) == "{'key2': ['value2', 'value3']}"
        assert (
            repr(self.params) == "QueryParams({'key2': ['value2', 'value3']})"
        )
        self.params.append("key2", "value4")
        assert self.params.get("key2") == ["value2", "value3", "value4"]
        del self.params["key2"]
        assert "key2" not in self.params
        assert len(self.params) == 0
        assert str(self.params) == "{}"
        assert repr(self.params) == "QueryParams({})"

        assert len(self.mock_stream.messages) == 3
        assert self.mock_stream.operations[0] == {
            "op": "query-params-delete",
            "key": "key1",
            "value": None,
        }
        assert self.mock_stream.operations[1] == {
            "op": "query-params-append",
            "key": "key2",
            "value": "value4",
        }
        assert self.mock_stream.operations[2] == {
            "op": "query-params-delete",
            "key": "key2",
            "value": None,
        }

    def test_remove(self) -> None:
        self.params.remove("key2", "value2")
        assert self.params.get("key2") == ["value3"]
        self.params.remove("key2")
        assert self.params.get("key2") is None
        self.params.remove("key2")
        assert self.params.get("key2") is None

        assert len(self.mock_stream.messages) == 2
        assert self.mock_stream.operations[0] == {
            "op": "query-params-delete",
            "key": "key2",
            "value": "value2",
        }
        assert self.mock_stream.operations[1] == {
            "op": "query-params-delete",
            "key": "key2",
            "value": None,
        }

    def test_clear(self) -> None:
        self.params.clear()
        assert len(self.params) == 0
        assert str(self.params) == "{}"
        assert repr(self.params) == "QueryParams({})"

        assert len(self.mock_stream.messages) == 1
        assert self.mock_stream.operations[0] == {"op": "query-params-clear"}


class TestCLIArgs(unittest.TestCase):
    def setUp(self):
        self.params = CLIArgs(
            {"key1": "value1", "key2": ["value2", "value3"]},
        )

    def test_get(self):
        assert self.params.get("key1") == "value1"
        assert self.params.get("key2") == ["value2", "value3"]
        # Test with fallback parameter
        assert self.params.get("non_existent", "fallback") == "fallback"
        assert self.params.get("non_existent", ["fallback"]) == ["fallback"]
        assert self.params.get("non_existent", None) is None
        # Test existing keys with fallback (should return original value)
        assert self.params.get("key1", "fallback") == "value1"
        assert self.params.get("key2", "fallback") == ["value2", "value3"]

    def test_get_all(self):
        assert self.params.get_all("key1") == ["value1"]
        assert self.params.get_all("key2") == ["value2", "value3"]
        assert self.params.get_all("non_existent_key") == []

    def test_contains(self):
        assert "key1" in self.params
        assert "non_existent_key" not in self.params

    def test_len(self):
        assert len(self.params) == 2

    def test_iter(self):
        keys = [key for key in self.params]
        assert keys, ["key1", "key2"]

    def test_repr(self):
        assert (
            repr(self.params)
            == "CLIArgs({'key1': 'value1', 'key2': ['value2', 'value3']})"
        )

    def test_str(self):
        assert (
            str(self.params)
            == "{'key1': 'value1', 'key2': ['value2', 'value3']}"
        )

    def test_setitem(self):
        with pytest.raises(TypeError):
            self.params["key3"] = "value4"

    def test_delete(self):
        with pytest.raises(TypeError):
            del self.params["key1"]
