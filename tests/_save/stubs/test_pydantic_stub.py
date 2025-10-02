# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from marimo._save.stubs.pydantic_stub import PydanticStub


class TestPydanticStub:
    """Tests for PydanticStub serialization and deserialization."""

    @staticmethod
    def test_basic_model() -> None:
        """Test stub with basic pydantic model."""
        from pydantic import BaseModel

        class BasicModel(BaseModel):
            name: str
            value: int

        model = BasicModel(name="test", value=42)

        # Create stub
        stub = PydanticStub(model)

        # Verify stub attributes
        assert stub.model_class == BasicModel
        assert stub.pydantic_dict == {"name": "test", "value": 42}
        assert stub.pydantic_fields_set == ["name", "value"]
        assert stub.pydantic_extra is None
        assert stub.pydantic_private is None

        # Restore and verify
        restored = stub.load({})
        assert isinstance(restored, BasicModel)
        assert restored.name == model.name
        assert restored.value == model.value
        assert restored.model_fields_set == model.model_fields_set

    @staticmethod
    def test_model_with_private_fields() -> None:
        """Test stub with model containing private fields."""
        from pydantic import BaseModel, PrivateAttr

        class ModelWithPrivate(BaseModel):
            name: str
            _private: int = PrivateAttr(default=0)
            _secret: str = PrivateAttr(default="secret")

        model = ModelWithPrivate(name="test")
        model._private = 99
        model._secret = "my_secret"

        # Create stub
        stub = PydanticStub(model)

        # Verify private fields captured
        assert stub.pydantic_private is not None
        assert "_private" in stub.pydantic_private
        assert "_secret" in stub.pydantic_private
        assert stub.pydantic_private["_private"] == 99
        assert stub.pydantic_private["_secret"] == "my_secret"

        # Restore and verify private fields
        restored = stub.load({})
        assert restored._private == model._private
        assert restored._secret == model._secret

    @staticmethod
    def test_model_with_extra_fields() -> None:
        """Test stub with model allowing extra fields."""
        from pydantic import BaseModel, ConfigDict

        class ModelWithExtra(BaseModel):
            model_config = ConfigDict(extra="allow")
            name: str

        model = ModelWithExtra(name="test", extra_field="bonus", another=123)

        # Create stub
        stub = PydanticStub(model)

        # Verify extra fields captured
        assert stub.pydantic_extra is not None
        assert "extra_field" in stub.pydantic_extra
        assert "another" in stub.pydantic_extra
        assert stub.pydantic_extra["extra_field"] == "bonus"
        assert stub.pydantic_extra["another"] == 123

        # Restore and verify extra fields
        restored = stub.load({})
        assert restored.__pydantic_extra__ == model.__pydantic_extra__
        # Access extra fields via __pydantic_extra__
        assert restored.__pydantic_extra__["extra_field"] == "bonus"
        assert restored.__pydantic_extra__["another"] == 123

    @staticmethod
    def test_complex_model() -> None:
        """Test stub with model having all features."""
        from pydantic import BaseModel, ConfigDict, PrivateAttr

        class ComplexModel(BaseModel):
            model_config = ConfigDict(extra="allow")
            name: str
            value: int
            _private: str = PrivateAttr(default="secret")

        model = ComplexModel(name="test", value=42, extra="bonus")
        model._private = "my_secret"

        # Create stub
        stub = PydanticStub(model)

        # Verify all state captured
        assert stub.pydantic_dict == {"name": "test", "value": 42}
        assert "extra" in stub.pydantic_extra
        assert stub.pydantic_private["_private"] == "my_secret"
        assert "extra" in stub.pydantic_fields_set
        assert "name" in stub.pydantic_fields_set
        assert "value" in stub.pydantic_fields_set

        # Restore and verify everything
        restored = stub.load({})
        assert restored.name == model.name
        assert restored.value == model.value
        assert restored._private == model._private
        assert restored.__pydantic_extra__ == model.__pydantic_extra__
        assert restored.model_fields_set == model.model_fields_set

    @staticmethod
    def test_deterministic_fields_set() -> None:
        """Test that fields_set is sorted for deterministic serialization."""
        from pydantic import BaseModel

        class Model(BaseModel):
            a: int
            z: int
            m: int

        # Create multiple instances with different field order
        model1 = Model(z=1, a=2, m=3)
        model2 = Model(a=2, m=3, z=1)

        stub1 = PydanticStub(model1)
        stub2 = PydanticStub(model2)

        # fields_set should be sorted and identical
        assert stub1.pydantic_fields_set == stub2.pydantic_fields_set
        assert stub1.pydantic_fields_set == ["a", "m", "z"]

    @staticmethod
    def test_nested_models() -> None:
        """Test stub with nested pydantic models."""
        from pydantic import BaseModel

        class InnerModel(BaseModel):
            inner_value: int

        class OuterModel(BaseModel):
            name: str
            inner: InnerModel

        inner = InnerModel(inner_value=99)
        outer = OuterModel(name="test", inner=inner)

        # Create stub
        stub = PydanticStub(outer)

        # Restore and verify nested structure
        restored = stub.load({})
        assert restored.name == outer.name
        assert isinstance(restored.inner, InnerModel)
        assert restored.inner.inner_value == outer.inner.inner_value

    @staticmethod
    def test_partial_fields_set() -> None:
        """Test model where not all fields are set."""
        from pydantic import BaseModel

        class Model(BaseModel):
            required: str
            optional: int = 42

        # Only set required field
        model = Model(required="test")

        stub = PydanticStub(model)

        # Only required field should be in fields_set
        assert stub.pydantic_fields_set == ["required"]

        # Restore and verify
        restored = stub.load({})
        assert restored.required == model.required
        assert restored.optional == model.optional
        assert restored.model_fields_set == {"required"}
