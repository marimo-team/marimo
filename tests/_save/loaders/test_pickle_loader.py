# Copyright 2024 Marimo. All rights reserved.
import os
import pickle
import tempfile
from pathlib import Path

import pytest

from marimo._save.cache import Cache
from marimo._save.loaders.loader import LoaderError
from marimo._save.loaders.pickle import PickleLoader


class TestPickleLoader:
    def setup_method(self) -> None:
        """Set up a temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = self.temp_dir.name

    def teardown_method(self) -> None:
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_init(self) -> None:
        """Test initialization."""
        loader = PickleLoader("test", self.save_path)
        assert loader.name == "test"
        assert loader.suffix == "pickle"
        assert Path(str(loader.save_path)).name == "test"

        # Check that the directory was created
        assert os.path.exists(os.path.join(self.save_path, "test"))

    def test_build_path(self) -> None:
        """Test building the path for a cache file."""
        loader = PickleLoader("test", self.save_path)
        path = loader.build_path("hash1", "Pure")
        assert str(path).endswith("P_hash1.pickle")

        path = loader.build_path("hash2", "Deferred")
        assert str(path).endswith("D_hash2.pickle")

    def test_cache_hit_miss(self) -> None:
        """Test cache hit and miss."""
        loader = PickleLoader("test", self.save_path)

        # No file exists yet
        assert not loader.cache_hit("hash1", "Pure")

        # Create a cache file
        cache_path = loader.build_path("hash1", "Pure")
        cache = Cache(
            {"var1": "value1"},
            "hash1",
            set(),
            "Pure",
            True,
            {}
        )

        with open(cache_path, "wb") as f:
            pickle.dump(cache, f)

        # Now it should hit
        assert loader.cache_hit("hash1", "Pure")

        # Different hash should miss
        assert not loader.cache_hit("hash2", "Pure")

        # Different cache type should miss
        assert not loader.cache_hit("hash1", "Deferred")

        # Empty file should miss
        empty_path = loader.build_path("empty", "Pure")
        with open(empty_path, "wb") as f:
            pass
        assert not loader.cache_hit("empty", "Pure")

    def test_load_persistent_cache(self) -> None:
        """Test loading a persistent cache."""
        loader = PickleLoader("test", self.save_path)

        # Create a cache file
        cache_path = loader.build_path("hash1", "Pure")
        # Use string directly instead of Name constructor
        original_cache = Cache(
            {"var1": "value1"},
            "hash1",
            set(),
            "Pure",
            True,
            {}
        )

        with open(cache_path, "wb") as f:
            pickle.dump(original_cache, f)

        # Load the cache
        loaded_cache = loader.load_persistent_cache("hash1", "Pure")
        assert loaded_cache.hash == "hash1"
        assert loaded_cache.cache_type == "Pure"
        assert loaded_cache.hit is True

        # Should raise for non-existent cache
        with pytest.raises(FileNotFoundError):
            loader.load_persistent_cache("nonexistent", "Pure")

        # Test with invalid cache object
        invalid_path = loader.build_path("invalid", "Pure")
        with open(invalid_path, "wb") as f:
            pickle.dump("not a cache", f)

        with pytest.raises(LoaderError, match="Excepted cache object"):
            loader.load_persistent_cache("invalid", "Pure")

    def test_load_cache(self) -> None:
        """Test the load_cache method."""
        loader = PickleLoader("test", self.save_path)

        # Create a cache file
        cache_path = loader.build_path("hash1", "Pure")
        # Use string directly instead of Name constructor
        original_cache = Cache(
            {"var1": "value1"},
            "hash1",
            set(),
            "Pure",
            True,
            {}
        )

        with open(cache_path, "wb") as f:
            pickle.dump(original_cache, f)

        # Load the cache
        loaded_cache = loader.load_cache("hash1", "Pure")
        assert loaded_cache.hash == "hash1"

        # Should raise for non-existent cache
        with pytest.raises(LoaderError, match="Unexpected cache miss"):
            loader.load_cache("nonexistent", "Pure")

    def test_save_cache(self) -> None:
        """Test saving a cache."""
        loader = PickleLoader("test", self.save_path)

        # Create a cache
        cache = Cache(
            {"var1": "value1"},
            "hash1",
            set(),
            "Pure",
            True,
            {}
        )

        # Save the cache
        loader.save_cache(cache)

        # Verify the file was created
        cache_path = loader.build_path("hash1", "Pure")
        assert os.path.exists(cache_path)

        # Load the cache and verify contents
        with open(cache_path, "rb") as f:
            loaded_cache = pickle.load(f)

        assert loaded_cache.hash == "hash1"
        assert loaded_cache.cache_type == "Pure"

        # Save another cache with different type
        cache2 = Cache(
            {"var2": "value2"},
            "hash2",
            set(),
            "Deferred",
            True,
            {}
        )

        loader.save_cache(cache2)

        # Verify the second file was created
        cache2_path = loader.build_path("hash2", "Deferred")
        assert os.path.exists(cache2_path)
