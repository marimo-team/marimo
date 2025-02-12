# Copyright 2024 Marimo. All rights reserved.
import pytest
from marimo._runtime.secrets import SecretManager


def test_secret_manager():
    manager = SecretManager("test-app")
    
    # Test setting and getting secrets
    manager.set_secret("test-key", "test-value")
    assert manager.get_secret("test-key") == "test-value"
    
    # Test deleting secrets
    manager.delete_secret("test-key")
    assert manager.get_secret("test-key") is None
    
    # Test empty key/value validation
    with pytest.raises(ValueError):
        manager.set_secret("", "value")
    
    with pytest.raises(ValueError):
        manager.set_secret("key", "")
    
    with pytest.raises(ValueError):
        manager.get_secret("")
    
    with pytest.raises(ValueError):
        manager.delete_secret("")


def test_secret_manager_nonexistent_key():
    manager = SecretManager("test-app")
    assert manager.get_secret("nonexistent-key") is None 