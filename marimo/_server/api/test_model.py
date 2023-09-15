# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

from marimo._server.api.model import parse_raw


@dataclass
class Config:
    disabled: bool
    gpu: bool


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
