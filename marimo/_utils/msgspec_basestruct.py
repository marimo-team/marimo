from typing import Any
import msgspec
from msgspec import structs as msf

class BaseStruct(msgspec.Struct):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> dict:
        # 1) build per-field schemas via Pydantic’s handler (we don’t import its type)
        tdf: dict[str, dict] = {}
        for f in msf.fields(cls):
            field_schema = handler.generate_schema(f.type)
            required = (f.default is msgspec.UNSET and getattr(f, 'default_factory', msgspec.UNSET) is msgspec.UNSET)
            tdf[f.name] = typed_dict_field(schema=field_schema, required=required)

        td = typed_dict_schema(tdf, total=True)

        # 2) convert dict -> struct using msgspec (single source of truth for defaults & validation)
        def to_struct(values: dict[str, Any]) -> Any:
            return msgspec.convert(values, cls, from_attributes=True)

        chain = chain_schema([td, no_info_plain_validator_function(to_struct)])

        # 3) accept either an instance (fast-path) or dict/JSON
        return json_or_python_schema(
            json_schema=chain,
            python_schema=union_schema([is_instance_schema(cls), chain]),
            serialization=plain_serializer_function_ser_schema(msgspec.to_builtins),
        )


# Tiny helpers that build CoreSchema dicts without importing pydantic_core
# WARNING: these could break if pydantic_core changes its API

from typing import Any, Iterable

def typed_dict_field(*, schema: dict, required: bool | None = None,
                     validation_alias: Any = None, serialization_alias: str | None = None,
                     serialization_exclude: bool | None = None, metadata: dict | None = None) -> dict:
    out = {
        'type': 'typed-dict-field',
        'schema': schema,
    }
    if required is not None:
        out['required'] = required
    if validation_alias is not None:
        out['validation_alias'] = validation_alias
    if serialization_alias is not None:
        out['serialization_alias'] = serialization_alias
    if serialization_exclude is not None:
        out['serialization_exclude'] = serialization_exclude
    if metadata is not None:
        out['metadata'] = metadata
    return out

def typed_dict_schema(
    fields: dict[str, dict],
    *,
    cls: type | None = None,
    cls_name: str | None = None,
    computed_fields: list | None = None,
    strict: bool | None = None,
    extras_schema: dict | None = None,
    extra_behavior: str | None = None,
    total: bool | None = None,
    ref: str | None = None,
    metadata: dict | None = None,
    serialization: dict | None = None,
    config: dict | None = None,
) -> dict:
    out = {
        "type": "typed-dict",
        "fields": fields,
    }
    if cls is not None:
        out["cls"] = cls
    if cls_name is not None:
        out["cls_name"] = cls_name
    if computed_fields is not None:
        out["computed_fields"] = computed_fields
    if strict is not None:
        out["strict"] = strict
    if extras_schema is not None:
        out["extras_schema"] = extras_schema
    if extra_behavior is not None:
        out["extra_behavior"] = extra_behavior
    if total is not None:
        out["total"] = total
    if ref is not None:
        out["ref"] = ref
    if metadata is not None:
        out["metadata"] = metadata
    if serialization is not None:
        out["serialization"] = serialization
    if config is not None:
        out["config"] = config
    return out


def is_instance_schema(cls: Any, *, cls_repr: str | None = None,
                       ref: str | None = None, metadata: dict | None = None,
                       serialization: dict | None = None) -> dict:
    out = {
        'type': 'is-instance',
        'cls': cls,
    }
    if cls_repr is not None:
        out['cls_repr'] = cls_repr
    if ref is not None:
        out['ref'] = ref
    if metadata is not None:
        out['metadata'] = metadata
    if serialization is not None:
        out['serialization'] = serialization
    return out

def union_schema(choices: list[dict] | list[tuple[dict, str]], *,
                 auto_collapse: bool | None = None, custom_error_type: str | None = None,
                 custom_error_message: str | None = None, custom_error_context: dict[str, str | int] | None = None,
                 mode: str | None = None, ref: str | None = None,
                 metadata: dict | None = None, serialization: dict | None = None) -> dict:
    out = {
        'type': 'union',
        'choices': choices,
    }
    if auto_collapse is not None:
        out['auto_collapse'] = auto_collapse
    if custom_error_type is not None:
        out['custom_error_type'] = custom_error_type
    if custom_error_message is not None:
        out['custom_error_message'] = custom_error_message
    if custom_error_context is not None:
        out['custom_error_context'] = custom_error_context
    if mode is not None:
        out['mode'] = mode
    if ref is not None:
        out['ref'] = ref
    if metadata is not None:
        out['metadata'] = metadata
    if serialization is not None:
        out['serialization'] = serialization
    return out

def chain_schema(steps: Iterable[dict], *, ref: str | None = None,
                 metadata: dict | None = None, serialization: dict | None = None) -> dict:
    out = {
        'type': 'chain',
        'steps': list(steps),
    }
    if ref is not None:
        out['ref'] = ref
    if metadata is not None:
        out['metadata'] = metadata
    if serialization is not None:
        out['serialization'] = serialization
    return out

def no_info_plain_validator_function(function, *, ref: str | None = None,
        json_schema_input_schema: dict | None = None,
        metadata: dict | None = None, serialization: dict | None = None) -> dict:
    out = {
        'type': 'function-plain',
        'function': {'type': 'no-info', 'function': function},
    }
    if ref is not None:
        out['ref'] = ref
    if json_schema_input_schema is not None:
        out['json_schema_input_schema'] = json_schema_input_schema
    if metadata is not None:
        out['metadata'] = metadata
    if serialization is not None:
        out['serialization'] = serialization
    return out

def no_info_after_validator_function(function, schema: dict, *, ref: str | None = None,
    json_schema_input_schema: dict | None = None,
    metadata: dict | None = None, serialization: dict | None = None) -> dict:
    out = {
        'type': 'function-after',
        'function': {'type': 'no-info', 'function': function},
        'schema': schema,
    }
    if ref is not None:
        out['ref'] = ref
    if json_schema_input_schema is not None:
        out['json_schema_input_schema'] = json_schema_input_schema
    if metadata is not None:
        out['metadata'] = metadata
    if serialization is not None:
        out['serialization'] = serialization
    return out

def json_or_python_schema(*, json_schema: dict, python_schema: dict,
    ref: str | None = None, metadata: dict | None = None,
    serialization: dict | None = None) -> dict:
    out = {
        'type': 'json-or-python',
        'json_schema': json_schema,
        'python_schema': python_schema,
    }
    if ref is not None:
        out['ref'] = ref
    if metadata is not None:
        out['metadata'] = metadata
    if serialization is not None:
        out['serialization'] = serialization
    return out

def plain_serializer_function_ser_schema(function,
    *, is_field_serializer: bool | None = None,
    info_arg: bool | None = None,
    return_schema: dict | None = None,
    when_used: str = 'always') -> dict:
    out = {
        'type': 'function-plain',
        'function': function,
    }
    if is_field_serializer is not None:
        out['is_field_serializer'] = is_field_serializer
    if info_arg is not None:
        out['info_arg'] = info_arg
    if return_schema is not None:
        out['return_schema'] = return_schema
    # Only include when_used if not the default ('always')
    if when_used != 'always':
        out['when_used'] = when_used
    return out
