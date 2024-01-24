# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations


class NoIDProviderException(Exception):
    pass


class IDProvider:
    """Provide IDs for UIElements

    Can be used to provide IDs that are stable across sessions.
    """

    def __init__(self, prefix: str):
        """Initialize an ID provider

        `prefix` should be unique across cells
        """
        self._prefix = prefix
        self._counter = 0

    def take_id(self) -> str:
        """Get an ID"""
        this_id = f"{self._prefix}-{self._counter}"
        self._counter += 1
        return this_id
