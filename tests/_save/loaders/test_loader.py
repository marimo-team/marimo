# Copyright 2024 Marimo. All rights reserved.

import pytest
import tempfile

from abc import ABC, abstractmethod
import functools
from pathlib import Path
import os
import json
import pickle

from marimo._save.cache import Cache
from marimo._save.loaders.loader import (
    BasePersistenceLoader,
    Loader,
    LoaderError,
    LoaderPartial,
)

from marimo._save.loaders import JsonLoader, PickleLoader, MemoryLoader

from tests._save.loaders.mocks import MockLoader

from marimo._save.hash import HashKey


def key(a, b):
    return HashKey(a, b)


class TestLoaderPartial:
    def test_init(self) -> None:
        """Test initialization."""
        partial = LoaderPartial(MockLoader, config_value="custom")
        assert partial.loader_type == MockLoader
        assert partial.kwargs == {"config_value": "custom"}

    def test_call(self) -> None:
        """Test calling the partial to create a loader."""
        partial = LoaderPartial(MockLoader, config_value="custom")
        loader = partial("test_name")

        assert isinstance(loader, MockLoader)
        assert loader.name == "test_name"
        assert loader.config_value == "custom"

    def test_call_with_invalid_args(self) -> None:
        """Test calling with invalid arguments."""
        partial = LoaderPartial(MockLoader, invalid_arg="value")

        with pytest.raises(TypeError, match="Could not create"):
            partial("test_name")


class ABCTestLoader(ABC):
    save_path = None
    suffix = None

    def setup_method(self, tmp_path) -> None:
        """Set up a temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = self.temp_dir.name

    def teardown_method(self) -> None:
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_init(self) -> None:
        """Test initialization."""
        loader = self.instance()
        assert loader.name == "test"
        if self.suffix:
            assert loader.suffix == self.suffix
        if isinstance(loader, BasePersistenceLoader):
            assert Path(str(loader.save_path)).name == "test"
            # Check that the directory was created
            assert os.path.exists(loader.save_path)

    def test_build_path(self) -> None:
        """Test building the path for a cache file."""
        loader = self.instance()
        path = loader.build_path(key("hash1", "Pure"))
        suffix = f".{self.suffix}" if self.suffix else ""
        assert str(path).endswith(f"P_hash1{suffix}")

        path = loader.build_path(key("hash2", "Deferred"))
        assert str(path).endswith(f"D_hash2{suffix}")

    def test_cache_hit_miss(self) -> None:
        """Test cache hit and miss."""
        loader = self.instance()

        # No file exists yet
        assert not loader.cache_hit(key("hash1", "Pure"))

        # Create a cache file
        cache_path = loader.build_path(key("hash1", "Pure"))

        # Create a valid JSON cache
        self.seed_cache()

        # Now it should hit
        assert (
            loader.cache_attempt({"var1"}, key("hash1", "Pure"), set())
            is not None
        )

        # Different hash should miss
        assert not loader.cache_hit(key("hash2", "Pure"))

        # Different cache type should miss
        assert not loader.cache_hit(key("hash1", "Deferred"))

        # Empty file should miss
        empty_path = loader.build_path(key("empty", "Pure"))
        with open(empty_path, "w") as f:
            pass
        assert not loader.cache_hit(key("empty", "Pure"))

        assert loader.hits == 1

    @abstractmethod
    def instance(self) -> Loader:
        pass

    @abstractmethod
    def seed_cache(self) -> None:
        pass


class TestMemoryLoader(ABCTestLoader):
    @functools.cache
    def instance(self) -> Loader:
        return MemoryLoader("test")

    def seed_cache(self) -> None:
        cache_path = self.instance().build_path(key("hash1", "Pure"))
        self.instance()._cache[cache_path] = Cache(
            {"var1": "value1"},
            key("hash1", "Pure"),
            [],
            True,
            {},
        )


class TestJsonLoader(ABCTestLoader):
    suffix = "json"

    @functools.cache
    def instance(self) -> Loader:
        return JsonLoader("test", self.save_path)

    def seed_cache(self):
        cache_path = self.instance().build_path(key("hash1", "Pure"))
        cache_dict = {
            "defs": {"var1": "value1"},
            "key": {
              "hash": "hash1",
              "cache_type": "Pure",
            },
            "stateful_refs": [],
            "hit": True,
            "meta": {},
        }

        with open(cache_path, "w") as f:
            json.dump(cache_dict, f)


class TestPickleLoader(ABCTestLoader):
    suffix = "pickle"

    @functools.cache
    def instance(self) -> Loader:
        return PickleLoader("test", self.save_path)

    def seed_cache(self) -> None:
        cache_path = self.instance().build_path(key("hash1", "Pure"))
        cache = Cache({"var1": "value1"}, key("hash1", "Pure"), set(), True, {})

        with open(cache_path, "wb") as f:
            pickle.dump(cache, f)
