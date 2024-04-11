# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from typing import Any, Generic, TypeVar

import marimo._output.data.data as mo_data
from marimo._plugins.core.web_component import JSONType

T = TypeVar("T")


class TableManager(abc.ABC, Generic[T]):
    def __init__(self, data: T) -> None:
        self.data = data

    def to_data(self) -> JSONType:
        """
        The best way to represent the data in a table as JSON.

        By default, this method calls `to_csv` and returns the result as
        a string.
        """
        return mo_data.csv(self.to_csv()).url

    @abc.abstractmethod
    def to_csv(self) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def to_json(self) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def select_rows(self, indices: list[int]) -> TableManager[T]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_row_headers(self) -> list[tuple[str, list[str | int | float]]]:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def is_type(value: Any) -> bool:
        raise NotImplementedError


class TableManagerFactory(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def package_name() -> str:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def create() -> type[TableManager[Any]]:
        raise NotImplementedError
