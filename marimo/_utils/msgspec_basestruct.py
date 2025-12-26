# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import msgspec

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema


class BaseStruct(msgspec.Struct):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        # Lazy import pydantic_core
        from pydantic_core import core_schema

        # Build per-field schemas
        tdf: dict[str, core_schema.TypedDictField] = {}
        for f in msgspec.structs.fields(cls):
            tdf[f.name] = core_schema.typed_dict_field(
                schema=handler.generate_schema(f.type),
                required=(
                    f.default is msgspec.UNSET
                    and getattr(f, "default_factory", msgspec.UNSET)
                    is msgspec.UNSET
                ),
            )
        td = core_schema.typed_dict_schema(tdf, total=True)

        # Create a function to convert a msgspec.Struct to a dictionary.
        def to_struct(values: dict[str, Any]) -> Any:
            return msgspec.convert(values, cls, from_attributes=True)

        # Create a chain schema to validate the dictionary and convert to the msgspec.Struct.
        chain = core_schema.chain_schema(
            [td, core_schema.no_info_plain_validator_function(to_struct)]
        )

        # Return the json or python schema.
        return core_schema.json_or_python_schema(
            json_schema=chain,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(cls),  # fast-path
                    chain,
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                msgspec.to_builtins
            ),
        )
