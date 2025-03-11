# Copyright 2024 Marimo. All rights reserved.
import json
import os
import tempfile
from pathlib import Path

import pytest

from marimo._save.cache import Cache
from marimo._save.loaders.json import JsonLoader
from marimo._save.loaders.loader import LoaderError


class TestJsonLoader:
    def setup_method(self) -> None:
        """Set up a temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = self.temp_dir.name

    def teardown_method(self) -> None:
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_init(self) -> None:
        """Test initialization."""
        loader = JsonLoader("test", self.save_path)
        assert loader.name == "test"
        assert loader.suffix == "json"
        assert Path(str(loader.save_path)).name == "test"

        # Check that the directory was created
        assert os.path.exists(os.path.join(self.save_path, "test"))

    def test_build_path(self) -> None:
        """Test building the path for a cache file."""
        loader = JsonLoader("test", self.save_path)
        path = loader.build_path("hash1", "Pure")
        assert str(path).endswith("P_hash1.json")

        path = loader.build_path("hash2", "Deferred")
        assert str(path).endswith("D_hash2.json")

    def test_cache_hit_miss(self) -> None:
        """Test cache hit and miss."""
        loader = JsonLoader("test", self.save_path)

        # No file exists yet
        assert not loader.cache_hit("hash1", "Pure")

        # Create a cache file
        cache_path = loader.build_path("hash1", "Pure")

        # Create a valid JSON cache
        cache_dict = {
            "defs": {"var1": "value1"},
            "hash": "hash1",
            "stateful_refs": [],
            "cache_type": "Pure",
            "hit": True,
            "meta": {}
        }

        with open(cache_path, "w") as f:
            json.dump(cache_dict, f)

        # Now it should hit
        assert loader.cache_hit("hash1", "Pure")

        # Different hash should miss
        assert not loader.cache_hit("hash2", "Pure")

        # Different cache type should miss
        assert not loader.cache_hit("hash1", "Deferred")

        # Empty file should miss
        empty_path = loader.build_path("empty", "Pure")
        with open(empty_path, "w") as f:
            pass
        assert not loader.cache_hit("empty", "Pure")

    def test_load_persistent_cache(self) -> None:
        """Test loading a persistent cache."""
        loader = JsonLoader("test", self.save_path)

        # Create a cache file
        cache_path = loader.build_path("hash1", "Pure")

        # Create a valid JSON cache
        cache_dict = {
            "defs": {"var1": "value1"},
            "hash": "hash1",
            "stateful_refs": [],
            "cache_type": "Pure",
            "hit": True,
            "meta": {}
        }

        with open(cache_path, "w") as f:
            json.dump(cache_dict, f)

        # Load the cache
        loaded_cache = loader.load_persistent_cache("hash1", "Pure")
        assert loaded_cache.hash == "hash1"
        assert loaded_cache.cache_type == "Pure"
        assert loaded_cache.hit is True
        assert isinstance(loaded_cache.stateful_refs, set)

        # Should raise for non-existent cache
        with pytest.raises(FileNotFoundError):
            loader.load_persistent_cache("nonexistent", "Pure")

        # Test with invalid JSON
        invalid_path = loader.build_path("invalid", "Pure")
        with open(invalid_path, "w") as f:
            f.write("not valid json")

        with pytest.raises(json.JSONDecodeError):
            loader.load_persistent_cache("invalid", "Pure")

        # Test with missing required fields
        missing_fields_path = loader.build_path("missing", "Pure")
        with open(missing_fields_path, "w") as f:
            json.dump({"hash": "missing", "stateful_refs": []}, f)

        with pytest.raises(LoaderError, match="Invalid json object"):
            loader.load_persistent_cache("missing", "Pure")

    def test_load_cache(self) -> None:
        """Test the load_cache method."""
        loader = JsonLoader("test", self.save_path)

        # Create a cache file
        cache_path = loader.build_path("hash1", "Pure")

        # Create a valid JSON cache
        cache_dict = {
            "defs": {"var1": "value1"},
            "hash": "hash1",
            "stateful_refs": [],
            "cache_type": "Pure",
            "hit": True,
            "meta": {}
        }

        with open(cache_path, "w") as f:
            json.dump(cache_dict, f)

        # Load the cache
        loaded_cache = loader.load_cache("hash1", "Pure")
        assert loaded_cache.hash == "hash1"

        # Should raise for non-existent cache
        with pytest.raises(LoaderError, match="Unexpected cache miss"):
            loader.load_cache("nonexistent", "Pure")

    def test_save_cache(self) -> None:
        """Test saving a cache."""
        loader = JsonLoader("test", self.save_path)

        # Create a cache with a stateful reference
        cache = Cache(
            {"var1": "value1"},
            "hash1",
            {"stateful"},
            "Pure",
            True,
            {"version": 1}
        )

        # Save the cache
        loader.save_cache(cache)

        # Verify the file was created
        cache_path = loader.build_path("hash1", "Pure")
        assert os.path.exists(cache_path)

        # Load the JSON and verify contents
        with open(cache_path) as f:
            loaded_json = json.load(f)

        assert loaded_json["hash"] == "hash1"
        assert loaded_json["cache_type"] == "Pure"
        assert loaded_json["hit"] is True
        assert isinstance(loaded_json["stateful_refs"], list)  # Should be converted to list
        assert loaded_json["meta"] == {"version": 1}

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

        # Load the second JSON and verify contents
        with open(cache2_path) as f:
            loaded_json2 = json.load(f)

        assert loaded_json2["hash"] == "hash2"
        assert loaded_json2["cache_type"] == "Deferred"
