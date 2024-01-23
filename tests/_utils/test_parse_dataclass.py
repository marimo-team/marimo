# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import pytest

from marimo._runtime.requests import SetCellConfigRequest
from marimo._utils.parse_dataclass import build_dataclass, parse_raw


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
            configs: List[Config]

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
            configs: Dict[str, Config]

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
            configs: Tuple[Config, ...]

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
            configs: Tuple[str, Config]

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
            {"0": {"disabled": True}, "1": {"disabled": False}}
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

        # handle error
        with pytest.raises(ValueError) as e:
            parsed = parse_raw(serialize({"config": "invalid"}), Nested)
            assert "invalid" in str(e.value)

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

    def test_build_optional(self) -> None:
        @dataclass
        class TestOptional:
            x: Optional[str] = None

        parsed = build_dataclass({}, TestOptional)
        assert parsed == TestOptional(x=None)

        parsed = build_dataclass({"x": "hello"}, TestOptional)
        assert parsed == TestOptional(x="hello")


def test_build_empty_dataclass() -> None:
    @dataclass
    class Empty:
        ...

    parsed = build_dataclass({}, Empty)
    assert parsed == Empty()
