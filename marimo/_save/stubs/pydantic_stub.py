# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._save.stubs.base import CustomStub

__all__ = ["PydanticStub"]


class PydanticStub(CustomStub):
    """Stub for pydantic BaseModel instances.

    Pydantic models have non-deterministic pickling due to __pydantic_fields_set__
    being a set. This stub ensures deterministic serialization by sorting fields.
    """

    def __init__(self, model: Any) -> None:
        """Initialize stub with pydantic model data.

        Args:
            model: A pydantic BaseModel instance
        """
        self.model_class = model.__class__
        # Use model_dump to get a serializable representation
        self.data = model.model_dump()
        # Sort fields_set for deterministic serialization
        self.fields_set = sorted(model.model_fields_set)

    def load(self, glbls: dict[str, Any]) -> Any:
        """Reconstruct the pydantic model.

        Args:
            glbls: Global namespace (unused for pydantic models)

        Returns:
            Reconstructed pydantic model instance
        """
        del glbls  # Unused for pydantic models
        # Reconstruct using model_validate
        instance = self.model_class.model_validate(self.data)
        # Restore the fields_set using the private attribute
        instance.__pydantic_fields_set__ = set(self.fields_set)
        return instance

    @staticmethod
    def get_type() -> type:
        """Get the pydantic BaseModel type."""
        from pydantic import BaseModel

        return BaseModel
