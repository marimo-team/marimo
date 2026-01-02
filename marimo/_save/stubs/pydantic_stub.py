# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._save.stubs.stubs import CustomStub

__all__ = ["PydanticStub"]


class PydanticStub(CustomStub):
    """Stub for pydantic BaseModel instances.

    Pydantic models have non-deterministic pickling due to __pydantic_fields_set__
    being a set. This stub ensures deterministic serialization by sorting fields
    and preserves complete pydantic state including private and extra fields.
    """

    __slots__ = (
        "model_class",
        "pydantic_dict",
        "pydantic_extra",
        "pydantic_fields_set",
        "pydantic_private",
    )

    def __init__(self, model: Any) -> None:
        """Initialize stub with pydantic model data.

        Args:
            model: A pydantic BaseModel instance
        """
        from pydantic_core import PydanticUndefined

        self.model_class = model.__class__

        # Store pydantic state as individual attributes
        self.pydantic_dict = model.__dict__
        self.pydantic_extra = getattr(model, "__pydantic_extra__", None)

        # Sort fields_set for deterministic serialization
        self.pydantic_fields_set = sorted(
            getattr(model, "__pydantic_fields_set__", set())
        )

        # Capture private fields, filtering out undefined values
        private = getattr(model, "__pydantic_private__", None)
        if private:
            private = {
                k: v for k, v in private.items() if v is not PydanticUndefined
            }
        self.pydantic_private = private

    def load(self, glbls: dict[str, Any]) -> Any:
        """Reconstruct the pydantic model.

        Args:
            glbls: Global namespace (unused for pydantic models)

        Returns:
            Reconstructed pydantic model instance
        """
        del glbls  # Unused for pydantic models
        # Use model_construct to bypass validation (matches pickle behavior)
        instance = self.model_class.model_construct()

        # Reconstruct the state dict for __setstate__
        state = {
            "__dict__": self.pydantic_dict,
            "__pydantic_extra__": self.pydantic_extra,
            "__pydantic_fields_set__": set(self.pydantic_fields_set),
            "__pydantic_private__": self.pydantic_private,
        }

        # Restore state using pydantic's __setstate__
        if hasattr(instance, "__setstate__"):
            instance.__setstate__(state)
        else:
            # Fallback: manually restore each piece of state
            instance.__dict__.update(state["__dict__"])
            if state.get("__pydantic_extra__"):
                instance.__pydantic_extra__ = state["__pydantic_extra__"]
            instance.__pydantic_fields_set__ = state["__pydantic_fields_set__"]
            if state.get("__pydantic_private__"):
                instance.__pydantic_private__ = state["__pydantic_private__"]
        return instance

    def to_bytes(self) -> bytes:
        """Serialize the stub to bytes.

        Returns:
            Serialized bytes of the stub
        """
        import pickle

        return pickle.dumps(
            (
                self.model_class,
                self.pydantic_dict,
                self.pydantic_extra,
                self.pydantic_fields_set,
                self.pydantic_private,
            )
        )

    @staticmethod
    def get_type() -> type:
        """Get the pydantic BaseModel type."""
        from pydantic import BaseModel

        return BaseModel
