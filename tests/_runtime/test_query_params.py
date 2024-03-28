import unittest
from unittest.mock import MagicMock

from marimo._messaging.types import Stream
from marimo._runtime.query_params import QueryParams


class TestQueryParams(unittest.TestCase):
    def setUp(self):
        self.mock_stream = MagicMock(spec=Stream)
        self.params = QueryParams(
            {"key1": "value1", "key2": ["value2", "value3"]},
            stream=self.mock_stream,
        )

    def test_get(self):
        assert self.params.get("key1") == "value1"
        assert self.params.get("key2") == ["value2", "value3"]

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
            == "QueryParams({'key1': 'value1', 'key2': ['value2', 'value3']})"
        )

    def test_str(self):
        assert (
            str(self.params)
            == "{'key1': 'value1', 'key2': ['value2', 'value3']}"
        )

    def test_setitem(self):
        self.params["key3"] = "value4"
        assert self.params.get("key3") == "value4"

        assert self.mock_stream.write.call_count == 1
        assert self.mock_stream.write.call_args[1] == {
            "op": "query-params-set",
            "data": {"key": "key3", "value": "value4"},
        }

    def test_set(self):
        self.params.set("key1", "value5")
        assert self.params.get("key1") == "value5"

        assert self.mock_stream.write.call_count == 1
        assert self.mock_stream.write.call_args[1] == {
            "op": "query-params-set",
            "data": {"key": "key1", "value": "value5"},
        }

    def test_append(self):
        self.params.append("key1", "value5")
        assert self.params.get("key1") == ["value1", "value5"]
        self.params.append("key4", "value6")
        assert self.params.get("key4") == "value6"

        assert self.mock_stream.write.call_count == 2
        assert self.mock_stream.write.call_args_list[0][1] == {
            "op": "query-params-append",
            "data": {"key": "key1", "value": "value5"},
        }
        assert self.mock_stream.write.call_args_list[1][1] == {
            "op": "query-params-append",
            "data": {"key": "key4", "value": "value6"},
        }

    def test_delete(self):
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

        assert self.mock_stream.write.call_count == 3
        assert self.mock_stream.write.call_args_list[0][1] == {
            "op": "query-params-delete",
            "data": {"key": "key1", "value": None},
        }
        assert self.mock_stream.write.call_args_list[1][1] == {
            "op": "query-params-append",
            "data": {"key": "key2", "value": "value4"},
        }
        assert self.mock_stream.write.call_args_list[2][1] == {
            "op": "query-params-delete",
            "data": {"key": "key2", "value": None},
        }

    def test_remove(self):
        self.params.remove("key2", "value2")
        assert self.params.get("key2") == ["value3"]
        self.params.remove("key2")
        assert self.params.get("key2") is None
        self.params.remove("key2")
        assert self.params.get("key2") is None

        assert self.mock_stream.write.call_count == 2
        assert self.mock_stream.write.call_args_list[0][1] == {
            "op": "query-params-delete",
            "data": {"key": "key2", "value": "value2"},
        }
        assert self.mock_stream.write.call_args_list[1][1] == {
            "op": "query-params-delete",
            "data": {"key": "key2", "value": None},
        }

    def test_clear(self):
        self.params.clear()
        assert len(self.params) == 0
        assert str(self.params) == "{}"
        assert repr(self.params) == "QueryParams({})"

        assert self.mock_stream.write.call_count == 1
        assert self.mock_stream.write.call_args_list[0][1] == {
            "op": "query-params-clear",
            "data": {},
        }
