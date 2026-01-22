# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.deep_merge import deep_merge


def test_deep_merge_basic() -> None:
    """Test basic deep merge functionality."""
    original = {"a": 1, "b": {"c": 2, "d": 3}}
    update = {"b": {"c": 10, "e": 4}, "f": 5}

    result = deep_merge(original, update)

    assert result == {"a": 1, "b": {"c": 10, "d": 3, "e": 4}, "f": 5}


def test_deep_merge_keeps_original_keys_not_in_update() -> None:
    """Test that keys in original but not in update are preserved."""
    original = {"a": 1, "b": 2, "c": 3}
    update = {"b": 20}

    result = deep_merge(original, update)

    assert result == {"a": 1, "b": 20, "c": 3}


def test_deep_merge_adds_new_keys_from_update() -> None:
    """Test that new keys in update are added."""
    original = {"a": 1}
    update = {"b": 2}

    result = deep_merge(original, update)

    assert result == {"a": 1, "b": 2}


def test_deep_merge_nested_dicts() -> None:
    """Test deep merge with nested dictionaries."""
    original = {
        "level1": {
            "level2": {
                "keep": "original",
                "override": "original",
            }
        }
    }
    update = {
        "level1": {
            "level2": {
                "override": "updated",
                "new": "added",
            }
        }
    }

    result = deep_merge(original, update)

    assert result == {
        "level1": {
            "level2": {
                "keep": "original",
                "override": "updated",
                "new": "added",
            }
        }
    }


def test_deep_merge_replace_paths_deletes_missing_keys() -> None:
    """Test that replace_paths deletes keys not in update."""
    original = {
        "ai": {
            "custom_providers": {
                "provider1": {"api_key": "key1", "base_url": "url1"},
                "provider2": {"api_key": "key2", "base_url": "url2"},
            }
        }
    }
    update = {
        "ai": {
            "custom_providers": {
                "provider1": {"api_key": "key1_updated", "base_url": "url1"},
                # provider2 is removed
            }
        }
    }

    # Without replace_paths, provider2 would be kept
    result_merged = deep_merge(original, update)
    assert "provider2" in result_merged["ai"]["custom_providers"]

    # With replace_paths, provider2 should be removed
    result_replaced = deep_merge(
        original, update, replace_paths=frozenset({"ai.custom_providers"})
    )
    assert "provider2" not in result_replaced["ai"]["custom_providers"]
    assert result_replaced["ai"]["custom_providers"] == {
        "provider1": {"api_key": "key1_updated", "base_url": "url1"}
    }


def test_deep_merge_replace_paths_preserves_unmodified_fields() -> None:
    """Test that replace_paths preserves fields not in update.

    This is the key use case: editing base_url should preserve api_key
    (which is filtered out as masked placeholder).
    """
    original = {
        "ai": {
            "custom_providers": {
                "provider1": {"api_key": "secret", "base_url": "old_url"},
                "provider2": {"api_key": "key2", "base_url": "url2"},
            }
        }
    }
    # Frontend sends all providers, but api_key filtered as placeholder
    update = {
        "ai": {
            "custom_providers": {
                "provider1": {"base_url": "new_url"},  # api_key missing
                "provider2": {"api_key": "key2", "base_url": "url2"},
            }
        }
    }

    result = deep_merge(
        original, update, replace_paths=frozenset({"ai.custom_providers"})
    )

    # api_key should be preserved from original
    assert result["ai"]["custom_providers"]["provider1"] == {
        "api_key": "secret",
        "base_url": "new_url",
    }
    assert result["ai"]["custom_providers"]["provider2"] == {
        "api_key": "key2",
        "base_url": "url2",
    }


def test_deep_merge_replace_paths_with_empty_dict() -> None:
    """Test that replace_paths works when update has empty dict."""
    original = {
        "ai": {
            "custom_providers": {
                "provider1": {"api_key": "key1"},
            }
        }
    }
    update = {
        "ai": {
            "custom_providers": {}  # Remove all providers
        }
    }

    result = deep_merge(
        original, update, replace_paths=frozenset({"ai.custom_providers"})
    )

    assert result["ai"]["custom_providers"] == {}


def test_deep_merge_replace_paths_does_not_affect_other_paths() -> None:
    """Test that replace_paths only affects specified paths."""
    original = {
        "ai": {
            "custom_providers": {"p1": {"key": "v1"}},
            "models": {"m1": "model1", "m2": "model2"},
        }
    }
    update = {
        "ai": {
            "custom_providers": {"p2": {"key": "v2"}},
            "models": {"m1": "updated"},
            # m2 not in update
        }
    }

    result = deep_merge(
        original, update, replace_paths=frozenset({"ai.custom_providers"})
    )

    # custom_providers should be replaced (p1 gone, only p2)
    assert result["ai"]["custom_providers"] == {"p2": {"key": "v2"}}
    # models should be merged (m2 kept, m1 updated)
    assert result["ai"]["models"] == {"m1": "updated", "m2": "model2"}


def test_deep_merge_replace_paths_nested_path() -> None:
    """Test replace_paths with deeply nested paths."""
    original = {
        "a": {
            "b": {
                "c": {
                    "keep": "original",
                    "replace_me": {"x": 1, "y": 2},
                }
            }
        }
    }
    update = {
        "a": {
            "b": {
                "c": {
                    "replace_me": {"z": 3},
                }
            }
        }
    }

    result = deep_merge(
        original, update, replace_paths=frozenset({"a.b.c.replace_me"})
    )

    # replace_me should be replaced entirely
    assert result["a"]["b"]["c"]["replace_me"] == {"z": 3}
    # keep should be preserved (it's not in update, and parent is not replaced)
    assert result["a"]["b"]["c"]["keep"] == "original"


def test_deep_merge_replace_paths_when_key_not_in_original() -> None:
    """Test replace_paths when the key doesn't exist in original."""
    original = {"a": {"other": "value"}}
    update = {"a": {"custom_providers": {"p1": {"key": "v1"}}}}

    result = deep_merge(
        original, update, replace_paths=frozenset({"a.custom_providers"})
    )

    assert result == {
        "a": {"other": "value", "custom_providers": {"p1": {"key": "v1"}}}
    }


def test_deep_merge_replace_paths_when_key_not_in_update() -> None:
    """Test replace_paths when the key doesn't exist in update."""
    original = {"a": {"custom_providers": {"p1": {"key": "v1"}}}}
    update = {"a": {"other": "new_value"}}

    result = deep_merge(
        original, update, replace_paths=frozenset({"a.custom_providers"})
    )

    # custom_providers should be kept since it's not in update
    assert result == {
        "a": {
            "custom_providers": {"p1": {"key": "v1"}},
            "other": "new_value",
        }
    }
