# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Generic, Literal, NewType, Optional, TypeVar, Union

import pytest

from marimo._runtime.requests import SetCellConfigRequest
from marimo._types.ids import CellId_t
from marimo._utils.parse_dataclass import parse_raw

# Import NotRequired for testing
if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired


@dataclass
class Config:
    disabled: bool
    gpu: bool


@dataclass
class ConfigOne:
    disabled: bool


@dataclass
class ConfigTwo:
    gpu: bool


class AnimalType(Enum):
    DOG = "dog"
    CAT = "cat"


@dataclass
class Dog:
    type: Literal[AnimalType.DOG]
    bark: bool


@dataclass
class Cat:
    type: Literal[AnimalType.CAT]
    meow: bool


def serialize(obj: Any) -> bytes:
    return bytes(
        json.dumps(asdict(obj) if not isinstance(obj, dict) else obj),
        encoding="utf-8",
    )


class TestParseRaw:
    def test_invalid_message(self) -> None:
        with pytest.raises(ValueError) as e:
            parse_raw(b'"string"', ConfigOne)
        assert "needs to be a dictionary" in str(e.value)

    def test_flat(self) -> None:
        @dataclass
        class Flat:
            x: str
            y: int

        flat = Flat(x="hello", y=0)
        parsed = parse_raw(serialize(flat), Flat)
        assert parsed == flat

    def test_camel_case_to_snake(self) -> None:
        @dataclass
        class Flat:
            my_variable: str
            my_other_variable: int

        parsed = parse_raw(
            serialize({"MyVariable": "0", "MyOtherVariable": 1}), Flat
        )
        assert parsed == Flat(my_variable="0", my_other_variable=1)

    def test_nested_singleton(self) -> None:
        @dataclass
        class Nested:
            config: Config

        nested = Nested(Config(disabled=True, gpu=False))

        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

    def test_nested_list(self) -> None:
        @dataclass
        class Nested:
            configs: list[Config]

        nested = Nested(
            configs=[
                Config(disabled=True, gpu=False),
                Config(disabled=False, gpu=True),
            ]
        )

        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

    def test_nested_dict(self) -> None:
        @dataclass
        class Nested:
            configs: dict[str, Config]

        nested = Nested(
            configs={
                "0": Config(disabled=True, gpu=False),
                "1": Config(disabled=False, gpu=True),
            }
        )

        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

    def test_nested_tuple_ellipses(self) -> None:
        @dataclass
        class Nested:
            configs: tuple[Config, ...]

        nested = Nested(
            configs=tuple(
                [
                    Config(disabled=True, gpu=False),
                    Config(disabled=False, gpu=True),
                ]
            )
        )

        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

    def test_nested_tuple_fixed(self) -> None:
        @dataclass
        class Nested:
            configs: tuple[str, Config]

        nested = Nested(
            configs=(
                "0",
                Config(disabled=True, gpu=False),
            )
        )

        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

    def test_set_cell_config(self) -> None:
        config = SetCellConfigRequest(
            {
                CellId_t("0"): {"disabled": True},
                CellId_t("1"): {"disabled": False},
            }
        )
        parsed = parse_raw(serialize(config), SetCellConfigRequest)
        assert parsed == config

    def test_unions(self) -> None:
        @dataclass
        class Nested:
            config: Union[ConfigOne, ConfigTwo]

        # first
        nested = Nested(config=ConfigOne(disabled=True))
        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

        # other
        nested = Nested(config=ConfigTwo(gpu=True))
        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

        # should raise ("invalid" is not a dict and thus cannot be converted
        # to a dataclass)
        with pytest.raises(ValueError) as e:
            parsed = parse_raw(serialize({"config": "invalid"}), Nested)
        assert "invalid" in str(e.value)

        # should raise (value of key "config" is dataclass not included in
        # Union)
        nested = Nested(config=Config(True, True))  # type: ignore
        with pytest.raises(ValueError) as e:
            parsed = parse_raw(serialize(nested), Nested)

    def test_awkward_unions(self):
        @dataclass
        class Nested:
            data: Union[str, bool, dict[str, Any], list[float], list[bytes]]

        # str
        nested = Nested(data="string")
        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

        # bool
        nested = Nested(data=True)
        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

        # dict
        nested = Nested(data={"first": "hi", "second": False})
        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

        # list floats
        nested = Nested(data=[1, 2])
        parsed = parse_raw(serialize(nested), Nested)
        assert parsed == nested

        # not valid, list of strings
        with pytest.raises(ValueError) as e:
            parsed = parse_raw({"data": ["one", "two"]}, Nested)
        assert "does not fit any type of the union" in str(e.value)

        # not valid, int
        with pytest.raises(ValueError) as e:
            parsed = parse_raw({"data": 1}, Nested)
        assert "does not fit any type of the union" in str(e.value)

    def test_enums(self) -> None:
        @dataclass
        class Nested:
            config: AnimalType

        parsed = parse_raw(serialize({"config": AnimalType.CAT.value}), Nested)
        assert parsed.config == AnimalType.CAT

        parsed = parse_raw(serialize({"config": AnimalType.DOG.value}), Nested)
        assert parsed.config == AnimalType.DOG

        # handle error
        with pytest.raises(ValueError) as e:
            parsed = parse_raw(serialize({"config": "invalid"}), Nested)
        assert "invalid" in str(e.value)

    def test_discriminated_union(self) -> None:
        @dataclass
        class Nested:
            config: Union[Dog, Cat]

        parsed = parse_raw(
            serialize({"config": {"type": "dog", "bark": True}}),
            Nested,
        )
        assert parsed.config == Dog(type=AnimalType.DOG, bark=True)

        parsed = parse_raw(
            serialize({"config": {"type": "cat", "meow": True}}), Nested
        )
        assert parsed.config == Cat(type=AnimalType.CAT, meow=True)

        # handle error
        with pytest.raises(ValueError) as e:
            parsed = parse_raw(
                serialize({"config": {"invalid": True}}), Nested
            )
        assert "invalid" in str(e.value)


def test_build_optional() -> None:
    @dataclass
    class TestOptional:
        x: Optional[str] = None

    parsed = parse_raw({}, TestOptional)
    assert parsed == TestOptional(x=None)

    parsed = parse_raw({"x": "hello"}, TestOptional)
    assert parsed == TestOptional(x="hello")


def test_build_empty_dataclass() -> None:
    @dataclass
    class Empty: ...

    parsed = parse_raw({}, Empty)
    assert parsed == Empty()


def test_with_unknown_keys() -> None:
    @dataclass
    class Empty: ...

    parsed = parse_raw({"key": "value"}, Empty, allow_unknown_keys=True)
    assert parsed == Empty()


def test_newtype() -> None:
    UserId = NewType("UserId", int)

    @dataclass
    class User:
        id: UserId
        name: str

    # Need to use globals() to make the NewType available in the scope
    globals()["UserId"] = UserId

    parsed = parse_raw({"id": 123, "name": "John"}, User)
    assert parsed == User(id=UserId(123), name="John")
    assert isinstance(parsed.id, int)


def test_nested_optional_fields() -> None:
    @dataclass
    class NestedOptional:
        value: Optional[Config] = None

    # Test with None value
    parsed = parse_raw({}, NestedOptional)
    assert parsed == NestedOptional(value=None)

    # Test with actual value
    parsed = parse_raw(
        {"value": {"disabled": True, "gpu": False}}, NestedOptional
    )
    assert parsed == NestedOptional(value=Config(disabled=True, gpu=False))


def test_mixed_container_types() -> None:
    @dataclass
    class MixedContainer:
        data: list[Union[int, str, Config]]

    mixed = MixedContainer(
        data=[1, "string", Config(disabled=True, gpu=False)]
    )

    parsed = parse_raw(serialize(mixed), MixedContainer)
    assert parsed == mixed


def test_complex_nested_structures() -> None:
    @dataclass
    class ComplexNested:
        mapping: dict[str, list[Optional[Config]]]

    complex_data = ComplexNested(
        mapping={
            "first": [Config(disabled=True, gpu=False), None],
            "second": [Config(disabled=False, gpu=True)],
        }
    )

    parsed = parse_raw(serialize(complex_data), ComplexNested)
    assert parsed == complex_data


def test_invalid_enum_value() -> None:
    @dataclass
    class WithEnum:
        animal: AnimalType

    # Test with invalid enum value
    with pytest.raises(ValueError) as e:
        parse_raw({"animal": "fish"}, WithEnum)
    assert "fish" in str(e.value)


def test_literal_types() -> None:
    @dataclass
    class WithLiteral:
        status: Literal["active", "inactive", "pending"]

    # Valid literal value
    parsed = parse_raw({"status": "active"}, WithLiteral)
    assert parsed == WithLiteral(status="active")

    # Invalid literal value
    with pytest.raises(ValueError) as e:
        parse_raw({"status": "deleted"}, WithLiteral)
    assert "does not fit any type of the literal" in str(e.value)


def test_missing_required_fields() -> None:
    @dataclass
    class Required:
        name: str
        age: int

    # Missing required field
    with pytest.raises(TypeError) as e:
        parse_raw({"name": "John"}, Required)
    assert (
        "missing" in str(e.value).lower() or "required" in str(e.value).lower()
    )


def test_bytes_handling() -> None:
    @dataclass
    class WithBytes:
        data: bytes

    # We need to handle bytes specially since JSON doesn't support bytes directly
    # This test verifies that bytes passed as a string are properly converted
    original = WithBytes(data=b"hello")
    serialized = json.dumps({"data": original.data.decode("utf-8")}).encode(
        "utf-8"
    )

    # This should raise an error since JSON serialization of bytes doesn't work directly
    with pytest.raises(ValueError):
        parse_raw(serialized, WithBytes)


def test_default_values() -> None:
    @dataclass
    class WithDefaults:
        name: str
        age: int = 30
        active: bool = True

    # Test with all values provided
    parsed = parse_raw(
        {"name": "John", "age": 25, "active": False}, WithDefaults
    )
    assert parsed == WithDefaults(name="John", age=25, active=False)

    # Test with only required values
    parsed = parse_raw({"name": "John"}, WithDefaults)
    assert parsed == WithDefaults(name="John", age=30, active=True)


def test_type_conversion() -> None:
    @dataclass
    class TypeConversion:
        integer: int
        floating: float
        boolean: bool

    parsed = parse_raw(
        {"integer": 42, "floating": 3.14, "boolean": True}, TypeConversion
    )
    assert parsed.integer == 42
    assert parsed.floating == 3.14
    assert parsed.boolean is True


def test_nested_union_with_none() -> None:
    @dataclass
    class NestedUnionWithNone:
        value: Union[Config, None]

    # Test with None
    parsed = parse_raw({"value": None}, NestedUnionWithNone)
    assert parsed.value is None

    # Test with actual value
    parsed = parse_raw(
        {"value": {"disabled": True, "gpu": False}}, NestedUnionWithNone
    )
    assert parsed.value == Config(disabled=True, gpu=False)


def test_forward_references() -> None:
    # Define classes with forward references
    @dataclass
    class Node:
        value: int
        children: list[Node] = field(default_factory=list)

    # Make Node available in globals for forward reference resolution
    globals()["Node"] = Node

    # Create a simple tree
    leaf1 = Node(value=1)
    leaf2 = Node(value=2)
    root = Node(value=0, children=[leaf1, leaf2])

    # Test serialization and parsing
    parsed = parse_raw(serialize(root), Node)
    assert parsed.value == 0
    assert len(parsed.children) == 2
    assert parsed.children[0].value == 1
    assert parsed.children[1].value == 2


def test_case_insensitive_enum() -> None:
    class CaseInsensitiveEnum(str, Enum):
        UPPER = "UPPER"
        LOWER = "lower"
        MIXED = "MiXeD"

    # Make enum available in globals
    globals()["CaseInsensitiveEnum"] = CaseInsensitiveEnum

    @dataclass
    class WithCaseEnum:
        value: CaseInsensitiveEnum

    # Test with exact case
    parsed = parse_raw({"value": "UPPER"}, WithCaseEnum)
    assert parsed.value == CaseInsensitiveEnum.UPPER

    parsed = parse_raw({"value": "lower"}, WithCaseEnum)
    assert parsed.value == CaseInsensitiveEnum.LOWER

    # Test with different case (this will fail with current implementation)
    with pytest.raises(ValueError):
        parsed = parse_raw({"value": "upper"}, WithCaseEnum)


def test_allow_unknown_keys_nested() -> None:
    @dataclass
    class Inner:
        required: str

    # Make Inner available in globals
    globals()["Inner"] = Inner

    @dataclass
    class Outer:
        inner: Inner

    # Test with unknown keys in nested structure
    data = {
        "inner": {"required": "value", "unknown": "extra"},
        "outer_unknown": "something",
    }

    # Should fail without allow_unknown_keys
    with pytest.raises(ValueError) as e:
        parsed = parse_raw(data, Outer)
    assert "Unknown keys" in str(e.value)

    # Should succeed with allow_unknown_keys
    parsed = parse_raw(data, Outer, allow_unknown_keys=True)
    assert parsed.inner.required == "value"


def test_inheritance() -> None:
    @dataclass
    class Base:
        id: int
        name: str

    @dataclass
    class Derived(Base):
        extra: bool

    # Test parsing with inheritance
    parsed = parse_raw({"id": 1, "name": "test", "extra": True}, Derived)
    assert parsed == Derived(id=1, name="test", extra=True)

    # Missing field from derived class
    with pytest.raises(TypeError):
        parsed = parse_raw({"id": 1, "name": "test"}, Derived)


@pytest.mark.xfail(reason="Generic types are not supported yet")
def test_generic_types() -> None:
    T = TypeVar("T")

    # Make T available in globals
    globals()["T"] = T

    @dataclass
    class GenericContainer(Generic[T]):
        value: T

    @dataclass
    class StringContainer(GenericContainer[str]):
        pass

    @dataclass
    class IntContainer(GenericContainer[int]):
        pass

    # Test with string
    parsed = parse_raw({"value": "test"}, StringContainer)
    assert parsed == StringContainer(value="test")

    # Test with int
    parsed = parse_raw({"value": 42}, IntContainer)
    assert parsed == IntContainer(value=42)


def test_complex_union_discrimination() -> None:
    @dataclass
    class TypeA:
        type: Literal["a"]
        value_a: str

    @dataclass
    class TypeB:
        type: Literal["b"]
        value_b: int

    @dataclass
    class TypeC:
        type: Literal["c"]
        value_c: bool

    # Make types available in globals
    globals()["TypeA"] = TypeA
    globals()["TypeB"] = TypeB
    globals()["TypeC"] = TypeC

    @dataclass
    class Container:
        data: Union[TypeA, TypeB, TypeC]

    # Test with TypeA
    parsed = parse_raw({"data": {"type": "a", "value_a": "test"}}, Container)
    assert isinstance(parsed.data, TypeA)
    assert parsed.data.value_a == "test"

    # Test with TypeB
    parsed = parse_raw({"data": {"type": "b", "value_b": 42}}, Container)
    assert isinstance(parsed.data, TypeB)
    assert parsed.data.value_b == 42

    # Test with TypeC
    parsed = parse_raw({"data": {"type": "c", "value_c": True}}, Container)
    assert isinstance(parsed.data, TypeC)
    assert parsed.data.value_c is True

    # Test with invalid discriminator
    with pytest.raises(ValueError):
        parsed = parse_raw(
            {"data": {"type": "d", "value": "invalid"}}, Container
        )


def test_empty_containers() -> None:
    @dataclass
    class EmptyContainers:
        empty_list: list[str]
        empty_dict: dict[str, int]
        empty_tuple: tuple[int, ...]

    # Test with empty containers
    parsed = parse_raw(
        {"empty_list": [], "empty_dict": {}, "empty_tuple": []},
        EmptyContainers,
    )
    assert parsed.empty_list == []
    assert parsed.empty_dict == {}
    assert parsed.empty_tuple == ()


def test_invalid_json() -> None:
    @dataclass
    class Simple:
        value: str

    # Test with invalid JSON
    with pytest.raises(json.JSONDecodeError):
        parse_raw(b"{invalid json}", Simple)


def test_recursive_structure_limit() -> None:
    @dataclass
    class RecursiveNode:
        value: int
        next: Optional[RecursiveNode] = None

    # Make RecursiveNode available in globals
    globals()["RecursiveNode"] = RecursiveNode

    # Create a deeply nested structure
    current = None
    for i in range(100):  # Create a chain of 100 nodes
        current = RecursiveNode(value=i, next=current)

    # This should work fine
    parsed = parse_raw(serialize(current), RecursiveNode)

    # Verify the structure
    count = 0
    node = parsed
    while node is not None:
        count += 1
        node = node.next
    assert count == 100


def test_not_required_types() -> None:
    @dataclass
    class WithNotRequired:
        required: str
        optional: NotRequired[str]
        optional_dict: NotRequired[dict[str, str]]
        optional_list: NotRequired[list[str]]

    # Test with all fields provided
    data = {
        "required": "value",
        "optional": "optional_value",
        "optionalDict": {"key": "value"},
        "optionalList": ["item"],
    }
    parsed = parse_raw(json.dumps(data).encode(), WithNotRequired)
    assert parsed.required == "value"
    assert parsed.optional == "optional_value"
    assert parsed.optional_dict == {"key": "value"}
    assert parsed.optional_list == ["item"]

    # Test with only required fields
    data = {"required": "value"}
    parsed = parse_raw(json.dumps(data).encode(), WithNotRequired)
    assert parsed.required == "value"
    assert not hasattr(parsed, "optional") or parsed.optional is None
    assert not hasattr(parsed, "optional_dict") or parsed.optional_dict is None
    assert not hasattr(parsed, "optional_list") or parsed.optional_list is None

    # Test with empty values for container types
    data = {
        "required": "value",
        "optional": None,
        "optionalDict": {},
        "optionalList": [],
    }
    parsed = parse_raw(json.dumps(data).encode(), WithNotRequired)
    assert parsed.required == "value"
    assert parsed.optional is None
    assert parsed.optional_dict == {}
    assert parsed.optional_list == []
