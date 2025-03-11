# Copyright 2024 Marimo. All rights reserved.
from pathlib import Path
from typing import Any, Dict, Set

import pytest

from marimo._save.cache import Cache
from marimo._save.loaders.loader import (
    BasePersistenceLoader,
    Loader,
    LoaderError,
    LoaderPartial,
)


# Mock loader for testing
class MockLoader(Loader):
    def __init__(self, name: str, config_value: str = "default") -> None:
        super().__init__(name)
        self.config_value = config_value
        self.saved_caches: Dict[str, Cache] = {}

    def cache_hit(self, hashed_context: str, cache_type: str) -> bool:
        key = f"{cache_type}_{hashed_context}"
        return key in self.saved_caches

    def load_cache(self, hashed_context: str, cache_type: str) -> Cache:
        key = f"{cache_type}_{hashed_context}"
        if key not in self.saved_caches:
            raise LoaderError("Unexpected cache miss.")
        return self.saved_caches[key]

    def save_cache(self, cache: Cache) -> None:
        key = f"{cache.cache_type}_{cache.hash}"
        self.saved_caches[key] = cache


# Mock persistence loader for testing
class MockPersistenceLoader(BasePersistenceLoader):
    def __init__(self, name: str, save_path: str) -> None:
        super().__init__(name, "mock", save_path)
        self.saved_caches: Dict[str, Cache] = {}

    def load_persistent_cache(
        self, hashed_context: str, cache_type: str
    ) -> Cache:
        key = f"{cache_type}_{hashed_context}"
        if key not in self.saved_caches:
            raise FileNotFoundError(f"No cache found for {key}")
        return self.saved_caches[key]

    def save_cache(self, cache: Cache) -> None:
        key = f"{cache.cache_type}_{cache.hash}"
        self.saved_caches[key] = cache


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


class TestLoader:
    def test_build_path(self) -> None:
        """Test building a path from hash and cache type."""
        loader = MockLoader("test")

        path = loader.build_path("hash1", "Pure")
        assert str(path) == "P_hash1"

        path = loader.build_path("hash2", "Deferred")
        assert str(path) == "D_hash2"

    def test_cache_attempt_miss(self) -> None:
        """Test cache attempt with a miss."""
        loader = MockLoader("test")
        defs = {"var1"}
        stateful_refs: Set[str] = set()

        cache = loader.cache_attempt(defs, "hash1", stateful_refs, "Pure")

        assert cache.hash == "hash1"
        assert cache.hit is False
        assert cache.cache_type == "Pure"
        assert set(cache.defs.keys()) == defs
        assert all(value is None for value in cache.defs.values())

    def test_cache_attempt_hit(self) -> None:
        """Test cache attempt with a hit."""
        loader = MockLoader("test")
        defs = {"var1"}
        stateful_refs: Set[str] = set()

        # Create and save a cache
        original_cache = Cache(
            {"var1": "value1"},
            "hash1",
            stateful_refs,
            "Pure",
            True,
            {"version": 1},
        )
        loader.saved_caches["Pure_hash1"] = original_cache

        # Attempt to load the cache
        cache = loader.cache_attempt(defs, "hash1", stateful_refs, "Pure")

        assert cache.hash == "hash1"
        assert cache.hit is True
        assert cache.cache_type == "Pure"
        assert cache.defs["var1"] == "value1"
        assert cache.meta == {"version": 1}


class TestBasePersistenceLoader:
    def setup_method(self) -> None:
        """Set up a temporary directory for each test."""
        self.temp_dir = Path("/tmp/marimo_test_loader")
        self.temp_dir.mkdir(exist_ok=True)
        self.save_path = str(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up the temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_init(self) -> None:
        """Test initialization."""
        loader = MockPersistenceLoader("test", self.save_path)
        assert loader.name == "test"
        assert loader.suffix == "mock"
        assert str(loader.save_path).endswith("/test")

        # Check that the directory was created
        assert (Path(self.save_path) / "test").exists()

    def test_cache_hit(self) -> None:
        """Test cache hit detection."""
        loader = MockPersistenceLoader("test", self.save_path)

        # No cache exists yet
        assert not loader.cache_hit("hash1", "Pure")

        # Create a cache file (just a placeholder file)
        cache_path = loader.build_path("hash1", "Pure")
        with open(cache_path, "w") as f:
            f.write("placeholder")

        # Now it should hit
        assert loader.cache_hit("hash1", "Pure")

        # Different hash should miss
        assert not loader.cache_hit("hash2", "Pure")

        # Different cache type should miss
        assert not loader.cache_hit("hash1", "Deferred")

    def test_load_cache(self) -> None:
        """Test the load_cache method."""
        loader = MockPersistenceLoader("test", self.save_path)

        # Create and save a cache
        cache = Cache({"var1": "value1"}, "hash1", set(), "Pure", True, {})
        loader.saved_caches["Pure_hash1"] = cache

        # Create a placeholder file to trigger cache_hit
        cache_path = loader.build_path("hash1", "Pure")
        with open(cache_path, "w") as f:
            f.write("placeholder")

        # Load the cache
        loaded_cache = loader.load_cache("hash1", "Pure")
        assert loaded_cache.hash == "hash1"

        # Should raise for non-existent cache
        with pytest.raises(LoaderError, match="Unexpected cache miss"):
            loader.load_cache("nonexistent", "Pure")
