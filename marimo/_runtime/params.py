# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Union

from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.ops import (
    QueryParamsAppend,
    QueryParamsClear,
    QueryParamsDelete,
    QueryParamsSet,
)
from marimo._messaging.types import Stream
from marimo._output.rich_help import mddoc
from marimo._runtime.requests import (
    ListOrValue,
    Primitive,
    SerializedCLIArgs,
    SerializedQueryParams,
)
from marimo._runtime.state import State, StateRegistry


@mddoc
class QueryParams(State[SerializedQueryParams]):
    """Query parameters for a marimo app."""

    IGNORED_KEYS = {"access_token", "refresh_token", "session_id"}

    def __init__(
        self,
        params: Dict[str, Union[str, List[str]]],
        stream: Optional[Stream] = None,
        _registry: Optional[StateRegistry] = None,
    ):
        super().__init__(params, _registry=_registry)
        self._params = params
        self._stream = stream

    def get(self, key: str) -> Optional[Union[str, List[str]]]:
        """Get the value of the query parameter.

        Returns a str if there is only one item, a list of str otherwise.
        """
        if key not in self._params:
            return None
        return self._params[key]

    def get_all(self, key: str) -> List[str]:
        """Get the value of a query parameter as a list."""
        value = self._params.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def __getitem__(self, key: str) -> Optional[Union[str, List[str]]]:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self._params

    def __len__(self) -> int:
        return len(self._params)

    def __iter__(self) -> Iterator[str]:
        return iter(self._params)

    def __repr__(self) -> str:
        return f"QueryParams({self._params})"

    def __str__(self) -> str:
        return str(self._params)

    def __setitem__(self, key: str, value: Union[str, List[str]]) -> None:
        if value is None or value == []:  # type: ignore
            self.remove(key)
            return
        # We always overwrite the value
        self._params[key] = value
        QueryParamsSet(key, value).broadcast(self._stream)
        self._set_value(self._params)

    def __delitem__(self, key: str) -> None:
        del self._params[key]
        QueryParamsDelete(key, None).broadcast(self._stream)
        self._set_value(self._params)

    def set(self, key: str, value: Union[str, List[str]]) -> None:
        """Set the value of a query parameter."""
        self[key] = value

    def append(self, key: str, value: str) -> None:
        """Append a value to a list of values"""
        if key not in self._params:
            self._params[key] = value
            QueryParamsAppend(key, value).broadcast(self._stream)
            self._set_value(self._params)
            return

        current_value = self._params[key]
        if isinstance(current_value, list):
            current_value.append(value)
        else:
            self._params[key] = [current_value, value]

        QueryParamsAppend(key, value).broadcast(self._stream)
        self._set_value(self._params)

    def remove(self, key: str, value: Optional[str] = None) -> None:
        """Remove a value from a list of values."""
        if key not in self._params:
            return
        # If value is None, remove the key
        if value is None:
            del self._params[key]
            QueryParamsDelete(key, value).broadcast(self._stream)
            self._set_value(self._params)
            return

        current_value = self._params[key]
        if isinstance(current_value, list):
            current_value.remove(value)
        elif current_value == value:
            del self._params[key]

        QueryParamsDelete(key, value).broadcast(self._stream)
        self._set_value(self._params)

    def _mime_(self) -> tuple[KnownMimeType, str]:
        from marimo._plugins.stateless.tree import tree

        return tree(self._params)._mime_()

    def clear(self) -> None:
        """Clear all query params."""
        self._params.clear()
        QueryParamsClear().broadcast(self._stream)
        self._set_value(self._params)

    def to_dict(self) -> Dict[str, Union[str, List[str]]]:
        return self._params


@mddoc
class CLIArgs:
    """CLI args passed to a marimo app."""

    def __init__(
        self,
        params: SerializedCLIArgs,
    ):
        self._params = params

    def get(self, key: str) -> Optional[ListOrValue[Primitive]]:
        """Get the value of the CLI arg.

        Returns a singleton value if there is only one item,
        a list of values otherwise.
        """
        if key not in self._params:
            return None
        return self._params[key]

    def get_all(self, key: str) -> List[Primitive]:
        """Get the value of a CLI arg as a list."""
        value = self._params.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def __getitem__(self, key: str) -> Optional[ListOrValue[Primitive]]:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self._params

    def __len__(self) -> int:
        return len(self._params)

    def __iter__(self) -> Iterator[ListOrValue[Primitive]]:
        return iter(self._params)

    def __repr__(self) -> str:
        return f"CLIArgs({self._params})"

    def __str__(self) -> str:
        return str(self._params)

    def _mime_(self) -> tuple[KnownMimeType, str]:
        from marimo._plugins.stateless.tree import tree

        return tree(self._params)._mime_()

    def to_dict(self) -> SerializedCLIArgs:
        return self._params
