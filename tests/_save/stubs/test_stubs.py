# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from typing import Any

import pytest

from marimo._save.stubs import (
    CUSTOM_STUBS,
    STUB_REGISTRATIONS,
    CustomStub,
    maybe_register_stub,
    register_stub,
)


class TestStubRegistration:
    """Tests for stub registration mechanism."""

    @staticmethod
    def test_stub_registrations_dict() -> None:
        """Test that STUB_REGISTRATIONS contains expected entries."""
        # Should have pydantic.main.BaseModel
        assert "pydantic.main.BaseModel" in STUB_REGISTRATIONS

    @staticmethod
    @pytest.mark.skipif(
        not pytest.importorskip("pydantic", reason="pydantic not installed"),
        reason="pydantic required",
    )
    def test_maybe_register_stub_pydantic() -> None:
        """Test registering a pydantic model."""
        from pydantic import BaseModel

        from marimo._save.stubs import _REGISTERED_NAMES
        from marimo._save.stubs.pydantic_stub import PydanticStub

        class TestModel(BaseModel):
            value: int

        # Clear any existing registration
        if BaseModel in CUSTOM_STUBS:
            del CUSTOM_STUBS[BaseModel]
        if TestModel in CUSTOM_STUBS:
            del CUSTOM_STUBS[TestModel]
        # Also clear registered names
        _REGISTERED_NAMES.discard("pydantic.main.BaseModel")

        model = TestModel(value=42)

        # Register the stub
        result = maybe_register_stub(model)

        # Should return True (registered)
        assert result is True

        # BaseModel should now be in CUSTOM_STUBS
        assert BaseModel in CUSTOM_STUBS
        assert CUSTOM_STUBS[BaseModel] is PydanticStub

        # Subclass should also be registered
        assert TestModel in CUSTOM_STUBS
        assert CUSTOM_STUBS[TestModel] is PydanticStub

    @staticmethod
    @pytest.mark.skipif(
        not pytest.importorskip("pydantic", reason="pydantic not installed"),
        reason="pydantic required",
    )
    def test_maybe_register_stub_already_registered() -> None:
        """Test that already registered stubs return True immediately."""
        from pydantic import BaseModel

        from marimo._save.stubs import _REGISTERED_NAMES

        class TestModel(BaseModel):
            value: int

        # Ensure clean state
        if BaseModel in CUSTOM_STUBS:
            del CUSTOM_STUBS[BaseModel]
        if TestModel in CUSTOM_STUBS:
            del CUSTOM_STUBS[TestModel]
        _REGISTERED_NAMES.discard("pydantic.main.BaseModel")

        model = TestModel(value=42)

        # First registration
        result1 = maybe_register_stub(model)
        assert result1 is True

        # Verify it's registered
        assert BaseModel in CUSTOM_STUBS
        assert TestModel in CUSTOM_STUBS

        # Second call should return True immediately (already in CUSTOM_STUBS)
        result2 = maybe_register_stub(model)
        assert result2 is True

    @staticmethod
    def test_maybe_register_stub_no_match() -> None:
        """Test that non-matching types return False."""

        class PlainClass:
            pass

        obj = PlainClass()

        # Should return False (no registration)
        result = maybe_register_stub(obj)
        assert result is False

        # Should not be in CUSTOM_STUBS
        assert PlainClass not in CUSTOM_STUBS

    @staticmethod
    @pytest.mark.skipif(
        not pytest.importorskip("pydantic", reason="pydantic not installed"),
        reason="pydantic required",
    )
    def test_mro_traversal() -> None:
        """Test that MRO traversal finds base class registration."""
        from pydantic import BaseModel

        from marimo._save.stubs import _REGISTERED_NAMES

        # Clear registrations
        if BaseModel in CUSTOM_STUBS:
            del CUSTOM_STUBS[BaseModel]
        _REGISTERED_NAMES.discard("pydantic.main.BaseModel")

        class Parent(BaseModel):
            x: int

        class Child(Parent):
            y: int

        if Child in CUSTOM_STUBS:
            del CUSTOM_STUBS[Child]

        child = Child(x=1, y=2)

        # Should register via MRO (finds BaseModel in parent chain)
        result = maybe_register_stub(child)
        assert result is True

        # Both BaseModel and Child should be registered
        assert BaseModel in CUSTOM_STUBS
        assert Child in CUSTOM_STUBS


class TestCustomStubBase:
    """Tests for CustomStub base class."""

    @staticmethod
    def test_abstract_methods() -> None:
        """Test that CustomStub has required abstract methods."""
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            CustomStub()  # type: ignore

    @staticmethod
    def test_register_classmethod() -> None:
        """Test that register is a classmethod."""
        assert hasattr(CustomStub, "register")
        assert callable(CustomStub.register)

    @staticmethod
    def test_get_type_staticmethod() -> None:
        """Test that get_type is a static method."""
        assert hasattr(CustomStub, "get_type")

    @staticmethod
    def test_slots() -> None:
        """Test that CustomStub has __slots__ defined."""
        assert hasattr(CustomStub, "__slots__")
        assert CustomStub.__slots__ == ()


class TestRegisterStub:
    """Tests for register_stub function."""

    @staticmethod
    def test_register_stub_basic() -> None:
        """Test basic stub registration."""

        class DummyType:
            pass

        class DummyStub(CustomStub):
            __slots__ = ("obj",)

            def __init__(self, obj: Any) -> None:
                self.obj = obj

            def load(self, glbls: dict[str, Any]) -> Any:
                del glbls  # Unused
                return self.obj

            @staticmethod
            def get_type() -> type:
                return DummyType

        # Register
        register_stub(DummyType, DummyStub)

        # Should be in CUSTOM_STUBS
        assert DummyType in CUSTOM_STUBS
        assert CUSTOM_STUBS[DummyType] is DummyStub

        # Clean up
        del CUSTOM_STUBS[DummyType]

    @staticmethod
    def test_register_stub_none() -> None:
        """Test registering with None type does nothing."""

        class DummyStub(CustomStub):
            __slots__ = ()

            def __init__(self, obj: Any) -> None:
                pass

            def load(self, glbls: dict[str, Any]) -> Any:
                del glbls  # Unused
                return None

            @staticmethod
            def get_type() -> type:
                return object

        # Register with None
        register_stub(None, DummyStub)

        # Should not add None to CUSTOM_STUBS
        assert None not in CUSTOM_STUBS


class TestStubIntegration:
    """Integration tests for stub system."""

    @staticmethod
    @pytest.mark.skipif(
        not pytest.importorskip("pydantic", reason="pydantic not installed"),
        reason="pydantic required",
    )
    def test_cache_integration() -> None:
        """Test stub integration with cache system."""
        from pydantic import BaseModel

        from marimo._save.cache import Cache
        from marimo._save.stubs import _REGISTERED_NAMES
        from marimo._save.stubs.pydantic_stub import PydanticStub

        class TestModel(BaseModel):
            name: str
            value: int

        # Clear any existing registration to ensure clean test
        if BaseModel in CUSTOM_STUBS:
            del CUSTOM_STUBS[BaseModel]
        if TestModel in CUSTOM_STUBS:
            del CUSTOM_STUBS[TestModel]
        _REGISTERED_NAMES.discard("pydantic.main.BaseModel")

        model = TestModel(name="test", value=42)

        # Create cache
        cache = Cache.empty(
            key=type("HashKey", (), {"hash": "test", "cache_type": "Pure"})(),
            defs={"x"},
            stateful_refs=set(),
        )

        # Convert to stub (should trigger registration and conversion)
        converted = cache._convert_to_stub_if_needed(model, {})

        # Should be a PydanticStub
        assert isinstance(converted, PydanticStub)

        # Restore from stub
        restored = cache._restore_from_stub_if_needed(converted, {}, {})

        # Should match original
        assert isinstance(restored, TestModel)
        assert restored.name == model.name
        assert restored.value == model.value
        assert restored.model_fields_set == model.model_fields_set
